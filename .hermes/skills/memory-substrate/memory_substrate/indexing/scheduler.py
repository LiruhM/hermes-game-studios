"""
Memory Substrate v1.0 — Index Scheduler
Cron-based incremental and full re-indexing with file watchers.
"""

import os
import time
import threading
import schedule
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3


@dataclass
class SchedulerConfig:
    incremental_schedule: str = "*/30 * * * *"  # Every 30 minutes
    full_reindex_schedule: str = "0 3 * * 0"    # Weekly Sunday 3AM
    watch_enabled: bool = True
    watch_debounce_seconds: float = 2.0
    max_batch_size: int = 100
    vault_path: str = "C:/Users/mathe/Hermes_Brain"
    mempalace_poll_interval: int = 300  # 5 minutes
    skills_poll_interval: int = 600   # 10 minutes
    log_level: str = "INFO"
    db_path: str = "90-Sistema/_embeddings/scheduler.db"
    
    def __post_init__(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)


class IndexScheduler:
    """
    Scheduler for incremental and full re-indexing.
    Supports cron schedules, file watchers, and manual triggers.
    """
    
    def __init__(self, config: SchedulerConfig):
        self.config = config
        self.running = False
        self._scheduler_thread: Optional[threading.Thread] = None
        self._watchers: Dict[str, Any] = {}
        self._callbacks: Dict[str, Callable] = {}
        self._last_incremental: Optional[datetime] = None
        self._last_full: Optional[datetime] = None
        self._stats = {
            "incremental_runs": 0,
            "full_reindex_runs": 0,
            "files_processed": 0,
            "chunks_created": 0,
            "errors": 0,
            "last_error": None
        }
        self._init_db()
    
    def _init_db(self):
        """Initialize scheduler state database."""
        Path(self.config.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.config.db_path, check_same_thread=False)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS scheduler_state (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS file_state (
                path TEXT PRIMARY KEY,
                source TEXT,
                mtime REAL,
                size INTEGER,
                hash TEXT,
                last_indexed TEXT,
                status TEXT
            )
        """)
        self.conn.commit()
    
    # ============================================================
    # CALLBACK REGISTRATION
    # ============================================================
    
    def register_callback(self, event: str, callback: Callable):
        """Register callback for scheduler events.
        
        Events:
        - 'file_changed': (path, event_type) - vault file changed
        - 'mempalace_changed': (drawer_id, event_type) - palace drawer changed
        - 'skill_changed': (skill_name, event_type) - skill manifest changed
        - 'incremental_start': () - incremental indexing started
        - 'incremental_complete': (stats) - incremental indexing done
        - 'full_reindex_start': () - full reindex started
        - 'full_reindex_complete': (stats) - full reindex done
        - 'error': (error, context) - error occurred
        """
        self._callbacks[event] = callback
    
    def _emit(self, event: str, *args, **kwargs):
        """Emit event to registered callback."""
        if event in self._callbacks:
            try:
                self._callbacks[event](*args, **kwargs)
            except Exception as e:
                self._log(f"Callback error for {event}: {e}")
    
    # ============================================================
    # SCHEDULER CONTROL
    # ============================================================
    
    def start(self):
        """Start the scheduler."""
        if self.running:
            return
        
        self.running = True
        
        # Schedule jobs
        self._setup_schedules()
        
        # Start file watchers
        if self.config.watch_enabled:
            self._start_watchers()
        
        # Start scheduler thread
        self._scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self._scheduler_thread.start()
        
        self._log("Scheduler started")
    
    def stop(self):
        """Stop the scheduler."""
        self.running = False
        
        # Clear schedules
        schedule.clear()
        
        # Stop watchers
        self._stop_watchers()
        
        # Wait for thread
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._scheduler_thread.join(timeout=5)
        
        self._log("Scheduler stopped")
    
    def _setup_schedules(self):
        """Setup cron schedules."""
        # Parse incremental schedule
        if self.config.incremental_schedule:
            schedule.every(30).minutes.do(self._run_incremental)
            # More precise: use croniter for full cron support
        
        # Parse full reindex schedule
        if self.config.full_reindex_schedule:
            # For simplicity, run daily at 3AM and check if Sunday
            schedule.every().day.at("03:00").do(self._check_full_reindex)
        
        # MemPalace poll
        schedule.every(self.config.mempalace_poll_interval).seconds.do(
            self._poll_mempalace
        )
        
        # Skills poll
        schedule.every(self.config.skills_poll_interval).seconds.do(
            self._poll_skills
        )
    
    def _run_scheduler(self):
        """Main scheduler loop."""
        while self.running:
            try:
                schedule.run_pending()
            except Exception as e:
                self._emit('error', e, {'context': 'scheduler_loop'})
                self._stats['errors'] += 1
                self._stats['last_error'] = str(e)
            
            time.sleep(1)
    
    def _check_full_reindex(self):
        """Check if today is the day for full reindex (Sunday)."""
        if datetime.now().weekday() == 6:  # Sunday
            self._run_full_reindex()
    
    # ============================================================
    # INDEXING OPERATIONS
    # ============================================================
    
    def _run_incremental(self):
        """Run incremental indexing."""
        self._emit('incremental_start')
        start_time = time.time()
        
        stats = {
            'files_processed': 0,
            'chunks_created': 0,
            'updated': 0,
            'deleted': 0,
            'errors': 0
        }
        
        try:
            # 1. Vault incremental
            vault_stats = self._incremental_vault()
            stats['files_processed'] += vault_stats.get('files_processed', 0)
            stats['chunks_created'] += vault_stats.get('chunks_created', 0)
            stats['updated'] += vault_stats.get('updated', 0)
            stats['deleted'] += vault_stats.get('deleted', 0)
            
            # 2. MemPalace incremental (handled by poll)
            
            # 3. Skills incremental (handled by poll)
            
            self._last_incremental = datetime.now()
            self._stats['incremental_runs'] += 1
            self._stats['files_processed'] += stats['files_processed']
            self._stats['chunks_created'] += stats['chunks_created']
            
            duration = time.time() - start_time
            self._log(f"Incremental indexing completed in {duration:.1f}s: {stats}")
            
        except Exception as e:
            self._stats['errors'] += 1
            self._stats['last_error'] = str(e)
            self._emit('error', e, {'context': 'incremental_indexing'})
        
        self._emit('incremental_complete', stats)
        return stats
    
    def _run_full_reindex(self):
        """Run full re-indexing of all sources."""
        self._emit('full_reindex_start')
        start_time = time.time()
        
        stats = {
            'total_files': 0,
            'total_chunks': 0,
            'vault_chunks': 0,
            'mempalace_chunks': 0,
            'skill_chunks': 0,
            'errors': 0
        }
        
        try:
            # Clear all indexes (would be called by the indexing pipeline)
            self._emit('full_reindex_clear')
            
            # 1. Full vault reindex
            vault_stats = self._full_reindex_vault()
            stats['vault_chunks'] = vault_stats.get('chunks', 0)
            stats['total_files'] += vault_stats.get('files', 0)
            
            # 2. Full MemPalace reindex
            palace_stats = self._full_reindex_mempalace()
            stats['mempalace_chunks'] = palace_stats.get('chunks', 0)
            
            # 3. Full Skills reindex
            skill_stats = self._full_reindex_skills()
            stats['skill_chunks'] = skill_stats.get('chunks', 0)
            
            stats['total_chunks'] = (
                stats['vault_chunks'] + 
                stats['mempalace_chunks'] + 
                stats['skill_chunks']
            )
            
            self._last_full = datetime.now()
            self._stats['full_reindex_runs'] += 1
            
            duration = time.time() - start_time
            self._log(f"Full reindex completed in {duration:.1f}s: {stats}")
            
        except Exception as e:
            self._stats['errors'] += 1
            self._stats['last_error'] = str(e)
            self._emit('error', e, {'context': 'full_reindex'})
        
        self._emit('full_reindex_complete', stats)
        return stats
    
    # ============================================================
    # VAULT OPERATIONS
    # ============================================================
    
    def _incremental_vault(self) -> Dict:
        """Incremental vault indexing using file state tracking."""
        stats = {'files_processed': 0, 'chunks_created': 0, 'updated': 0, 'deleted': 0}
        
        vault_path = Path(self.config.vault_path)
        if not vault_path.exists():
            return stats
        
        # Get current file states
        current_files = {}
        for md_file in vault_path.rglob("*.md"):
            if self._is_excluded(md_file):
                continue
            
            rel_path = str(md_file.relative_to(vault_path))
            stat = md_file.stat()
            current_files[rel_path] = {
                'mtime': stat.st_mtime,
                'size': stat.st_size,
                'full_path': str(md_file)
            }
        
        # Get stored states
        stored = self._get_stored_file_states()
        
        # Find new/modified files
        for rel_path, info in current_files.items():
            stored_info = stored.get(rel_path)
            
            if not stored_info:
                # New file
                self._emit('file_changed', rel_path, 'created')
                # Process file (callback will handle)
                self._process_vault_file(rel_path, info['full_path'])
                self._update_file_state(rel_path, info)
                stats['files_processed'] += 1
                
            elif stored_info['mtime'] != info['mtime'] or stored_info['size'] != info['size']:
                # Modified file
                self._emit('file_changed', rel_path, 'modified')
                self._process_vault_file(rel_path, info['full_path'])
                self._update_file_state(rel_path, info)
                stats['files_processed'] += 1
        
        # Find deleted files
        for rel_path in stored:
            if rel_path not in current_files:
                self._emit('file_changed', rel_path, 'deleted')
                self._delete_file_state(rel_path)
                # Trigger deletion in indexes
                self._emit('file_deleted', rel_path)
                stats['deleted'] += 1
        
        return stats
    
    def _full_reindex_vault(self) -> Dict:
        """Full vault reindex."""
        stats = {'files': 0, 'chunks': 0}
        
        vault_path = Path(self.config.vault_path)
        if not vault_path.exists():
            return stats
        
        for md_file in vault_path.rglob("*.md"):
            if self._is_excluded(md_file):
                continue
            
            rel_path = str(md_file.relative_to(vault_path))
            stat = md_file.stat()
            info = {'mtime': stat.st_mtime, 'size': stat.st_size, 'full_path': str(md_file)}
            
            self._process_vault_file(rel_path, info['full_path'])
            self._update_file_state(rel_path, info)
            
            stats['files'] += 1
            stats['chunks'] += 1  # Approximate
        
        return stats
    
    def _process_vault_file(self, rel_path: str, full_path: str):
        """Process a single vault file - emits event for indexer to handle."""
        self._emit('index_vault_file', rel_path, 'modified')
    
    def _is_excluded(self, path: Path) -> bool:
        """Check if path should be excluded."""
        rel = str(path.relative_to(Path(self.config.vault_path)))
        excluded = [
            ".obsidian/", ".trash/", ".git/", "node_modules/",
            "__pycache__/", "*.tmp"
        ]
        for pattern in excluded:
            if pattern in rel or rel.startswith(pattern.rstrip('*')):
                return True
        return False
    
    # ============================================================
    # MEMPALACE OPERATIONS
    # ============================================================
    
    def _poll_mempalace(self):
        """Poll MemPalace for changes."""
        # This would call the MemPalace adapter to check for changes
        # and emit events for changed drawers
        self._emit('poll_mempalace')
    
    def _full_reindex_mempalace(self) -> Dict:
        """Full MemPalace reindex."""
        stats = {'chunks': 0}
        self._emit('full_reindex_mempalace')
        # The callback would handle the actual reindexing
        return stats
    
    # ============================================================
    # SKILLS OPERATIONS
    # ============================================================
    
    def _poll_skills(self):
        """Poll skills directory for manifest changes."""
        self._emit('poll_skills')
    
    def _full_reindex_skills(self) -> Dict:
        """Full skills reindex."""
        stats = {'chunks': 0}
        self._emit('full_reindex_skills')
        return stats
    
    # ============================================================
    # FILE STATE MANAGEMENT
    # ============================================================
    
    def _get_stored_file_states(self) -> Dict:
        """Get stored file states from database."""
        cursor = self.conn.execute(
            "SELECT path, source, mtime, size, hash, last_indexed, status FROM file_state"
        )
        return {
            row['path']: {
                'source': row['source'],
                'mtime': row['mtime'],
                'size': row['size'],
                'hash': row['hash'],
                'last_indexed': row['last_indexed'],
                'status': row['status']
            }
            for row in cursor.fetchall()
        }
    
    def _update_file_state(self, path: str, info: Dict, source: str = "vault"):
        """Update stored file state."""
        self.conn.execute("""
            INSERT OR REPLACE INTO file_state 
            (path, source, mtime, size, hash, last_indexed, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            path, source, info['mtime'], info['size'],
            info.get('hash', ''),
            datetime.now().isoformat(),
            'indexed'
        ))
        self.conn.commit()
    
    def _delete_file_state(self, path: str):
        """Delete file state."""
        self.conn.execute("DELETE FROM file_state WHERE path = ?", (path,))
        self.conn.commit()
    
    # ============================================================
    # FILE WATCHERS
    # ============================================================
    
    def _start_watchers(self):
        """Start file system watchers."""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
            
            class VaultEventHandler(FileSystemEventHandler):
                def __init__(self, scheduler):
                    self.scheduler = scheduler
                    self._debounce = {}
                
                def on_created(self, event):
                    if not event.is_directory and event.src_path.endswith(".md"):
                        self._debounced_emit('created', event.src_path)
                
                def on_modified(self, event):
                    if not event.is_directory and event.src_path.endswith(".md"):
                        self._debounced_emit('modified', event.src_path)
                
                def on_deleted(self, event):
                    if not event.is_directory and event.src_path.endswith(".md"):
                        self._debounced_emit('deleted', event.src_path)
                
                def _debounced_emit(self, event_type, path):
                    import time
                    now = time.time()
                    key = (event_type, path)
                    last = self._debounce.get(key, 0)
                    if now - last > self.scheduler.config.watch_debounce_seconds:
                        self._debounce[key] = now
                        # Get relative path
                        try:
                            rel = Path(path).relative_to(self.scheduler.config.vault_path)
                            self.scheduler._emit('file_changed', str(rel), event_type)
                        except ValueError:
                            pass
            
            handler = VaultEventHandler(self)
            observer = Observer()
            observer.schedule(handler, self.config.vault_path, recursive=True)
            observer.start()
            
            self._watchers['vault'] = observer
            self._log("Vault watcher started")
            
        except ImportError:
            self._log("watchdog not available, file watching disabled")
    
    def _stop_watchers(self):
        """Stop all file watchers."""
        for name, observer in self._watchers.items():
            try:
                observer.stop()
                observer.join(timeout=2)
            except Exception:
                pass
        self._watchers.clear()
        self._log("Watchers stopped")
    
    # ============================================================
    # MANUAL TRIGGERS
    # ============================================================
    
    def trigger_incremental(self) -> Dict:
        """Manually trigger incremental indexing."""
        return self._run_incremental()
    
    def trigger_full_reindex(self) -> Dict:
        """Manually trigger full reindex."""
        return self._run_full_reindex()
    
    def trigger_vault_reindex(self, full: bool = False) -> Dict:
        """Trigger vault-specific reindex."""
        if full:
            return self._full_reindex_vault()
        return self._incremental_vault()
    
    def trigger_mempalace_reindex(self, full: bool = False) -> Dict:
        """Trigger MemPalace reindex."""
        if full:
            return self._full_reindex_mempalace()
        self._poll_mempalace()
        return {}
    
    def trigger_skills_reindex(self, full: bool = False) -> Dict:
        """Trigger skills reindex."""
        if full:
            return self._full_reindex_skills()
        self._poll_skills()
        return {}
    
    # ============================================================
    # STATUS & STATS
    # ============================================================
    
    def get_status(self) -> Dict:
        """Get scheduler status."""
        return {
            "running": self.running,
            "last_incremental": self._last_incremental.isoformat() if self._last_incremental else None,
            "last_full": self._last_full.isoformat() if self._last_full else None,
            "next_incremental": self._get_next_run("incremental"),
            "next_full": self._get_next_run("full"),
            "stats": self._stats,
            "watchers": list(self._watchers.keys()),
            "config": {
                "incremental_schedule": self.config.incremental_schedule,
                "full_reindex_schedule": self.config.full_reindex_schedule,
                "watch_enabled": self.config.watch_enabled
            }
        }
    
    def _get_next_run(self, job_type: str) -> Optional[str]:
        """Get next scheduled run time."""
        jobs = schedule.get_jobs()
        for job in jobs:
            if job_type == "incremental" and job.interval == 30:
                return job.next_run.isoformat() if job.next_run else None
            elif job_type == "full" and job.next_run:
                # Check if it's the Sunday 3AM job
                if job.next_run.weekday() == 6 and job.next_run.hour == 3:
                    return job.next_run.isoformat()
        return None
    
    def get_file_states(self, limit: int = 100) -> List[Dict]:
        """Get recent file states."""
        cursor = self.conn.execute("""
            SELECT * FROM file_state ORDER BY last_indexed DESC LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]
    
    # ============================================================
    # UTILITIES
    # ============================================================
    
    def _log(self, message: str):
        """Log message."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [Scheduler] {message}")
    
    def close(self):
        """Clean shutdown."""
        self.stop()
        if self.conn:
            self.conn.close()


# ============================================================
# FACTORY
# ============================================================

def create_scheduler(config: SchedulerConfig = None) -> IndexScheduler:
    """Create scheduler with default or custom config."""
    if config is None:
        config = SchedulerConfig()
    return IndexScheduler(config)