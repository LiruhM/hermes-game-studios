"""
Knowledge Compounding Pipeline v1.0 — Cron Jobs
Unified cron scheduling for all pipeline stages.
"""

import schedule
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field


@dataclass
class CronJob:
    """Represents a scheduled cron job."""
    name: str
    schedule_str: str  # cron expression or schedule string
    func: Callable
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    errors: List[str] = field(default_factory=list)


class CronScheduler:
    """
    Unified cron scheduler for Knowledge Pipeline.
    
    Jobs:
    - capture_external: Every 30 minutes - scan external sources
    - organize_inbox: Hourly - process inbox to PARA
    - detect_drift: Daily 9am - find loose files
    - distill_pending: Daily 2am - progressive summarization
    - express_scheduled: Weekly Monday 6am - generate outputs
    - review_weekly: Weekly Monday 8am - weekly review
    - review_monthly: Monthly 1st 9am - monthly review
    - index_update: Every 30 min - update vector indices
    """
    
    def __init__(self, pipeline_orchestrator=None):
        self.pipeline = pipeline_orchestrator
        self._jobs: Dict[str, CronJob] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # Register default jobs
        if self.pipeline:
            self._register_default_jobs()
    
    def _register_default_jobs(self):
        """Register default pipeline cron jobs."""
        jobs = [
            CronJob(
                name="capture_external",
                schedule_str="every 30 minutes",
                func=lambda: self.pipeline.capture_engine.scan_external_sources(dry_run=False)
            ),
            CronJob(
                name="organize_inbox",
                schedule_str="every hour",
                func=lambda: self.pipeline.organize_engine.process_inbox(auto=True, dry_run=False)
            ),
            CronJob(
                name="detect_drift",
                schedule_str="every day at 09:00",
                func=lambda: self.pipeline.organize_engine.detect_drift(dry_run=False)
            ),
            CronJob(
                name="distill_pending",
                schedule_str="every day at 02:00",
                func=self._run_distill_job
            ),
            CronJob(
                name="express_scheduled",
                schedule_str="every monday at 06:00",
                func=self._run_express_job
            ),
            CronJob(
                name="review_weekly",
                schedule_str="every monday at 08:00",
                func=self._run_review_weekly
            ),
            CronJob(
                name="review_monthly",
                schedule_str="every month at 09:00",
                func=self._run_review_monthly
            ),
            CronJob(
                name="index_update",
                schedule_str="every 30 minutes",
                func=self._run_index_update
            )
        ]
        
        for job in jobs:
            self.add_job(job)
    
    def _run_distill_job(self):
        """Run distillation of pending notes."""
        try:
            pending = self.pipeline.distill_engine.get_pending_distill(max_layer=3)
            if pending:
                self.pipeline.distill_engine.batch_distill(pending, target_layer=4)
        except Exception as e:
            raise RuntimeError(f"Distill job failed: {e}")
    
    def _run_express_job(self):
        """Run scheduled express generation."""
        # This would generate outputs for active projects
        # For now, placeholder - could integrate with project tracking
        pass
    
    def _run_review_weekly(self):
        """Run weekly review."""
        # Would integrate with second-brain-pipeline review
        pass
    
    def _run_review_monthly(self):
        """Run monthly review."""
        # Would integrate with second-brain-pipeline review
        pass
    
    def _run_index_update(self):
        """Update vector indices for semantic search."""
        # Would trigger memory-substrate indexing
        pass
    
    def add_job(self, job: CronJob):
        """Add a cron job."""
        with self._lock:
            self._jobs[job.name] = job
            self._schedule_job(job)
    
    def remove_job(self, name: str):
        """Remove a cron job."""
        with self._lock:
            if name in self._jobs:
                schedule.cancel_job(self._jobs[name])
                del self._jobs[name]
    
    def enable_job(self, name: str):
        """Enable a cron job."""
        with self._lock:
            if name in self._jobs:
                self._jobs[name].enabled = True
                self._schedule_job(self._jobs[name])
    
    def disable_job(self, name: str):
        """Disable a cron job."""
        with self._lock:
            if name in self._jobs:
                self._jobs[name].enabled = False
                schedule.cancel_job(self._jobs[name])
    
    def _schedule_job(self, job: CronJob):
        """Schedule a job using the schedule library."""
        if not job.enabled:
            return
        
        # Parse schedule string and create schedule
        sched_str = job.schedule_str.lower()
        
        try:
            if sched_str.startswith("every "):
                parts = sched_str.split()
                if "minute" in sched_str:
                    interval = int(parts[1])
                    schedule.every(interval).minutes.do(job.func).tag(job.name)
                elif "hour" in sched_str:
                    if "at" in sched_str:
                        # every hour at XX:YY
                        time_str = parts[parts.index("at") + 1]
                        schedule.every().hour.at(time_str).do(job.func).tag(job.name)
                    else:
                        schedule.every().hour.do(job.func).tag(job.name)
                elif "day" in sched_str:
                    if "at" in sched_str:
                        time_str = parts[parts.index("at") + 1]
                        schedule.every().day.at(time_str).do(job.func).tag(job.name)
                    else:
                        schedule.every().day.do(job.func).tag(job.name)
                elif "monday" in sched_str:
                    if "at" in sched_str:
                        time_str = parts[parts.index("at") + 1]
                        schedule.every().monday.at(time_str).do(job.func).tag(job.name)
                    else:
                        schedule.every().monday.do(job.func).tag(job.name)
                elif "month" in sched_str:
                    if "at" in sched_str:
                        time_str = parts[parts.index("at") + 1]
                        schedule.every().month.at(time_str).do(job.func).tag(job.name)
                    else:
                        schedule.every().month.do(job.func).tag(job.name)
        except Exception as e:
            job.errors.append(f"Scheduling error: {e}")
    
    def start(self):
        """Start the scheduler thread."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
    
    def stop(self):
        """Stop the scheduler."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        schedule.clear()
    
    def _run_loop(self):
        """Main scheduler loop."""
        while self._running:
            try:
                schedule.run_pending()
            except Exception as e:
                print(f"[CronScheduler] Error in scheduler loop: {e}")
            time.sleep(60)  # Check every minute
    
    def run_job_now(self, name: str) -> bool:
        """Run a job immediately."""
        with self._lock:
            if name in self._jobs:
                job = self._jobs[name]
                try:
                    job.func()
                    job.last_run = datetime.now()
                    job.run_count += 1
                    return True
                except Exception as e:
                    job.errors.append(f"{datetime.now().isoformat()}: {e}")
                    return False
        return False
    
    def get_job_status(self, name: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific job."""
        with self._lock:
            if name in self._jobs:
                job = self._jobs[name]
                return {
                    "name": job.name,
                    "enabled": job.enabled,
                    "schedule": job.schedule_str,
                    "last_run": job.last_run.isoformat() if job.last_run else None,
                    "run_count": job.run_count,
                    "errors": job.errors[-5:] if job.errors else []
                }
        return None
    
    def get_all_status(self) -> Dict[str, Any]:
        """Get status of all jobs."""
        with self._lock:
            return {
                name: {
                    "enabled": job.enabled,
                    "schedule": job.schedule_str,
                    "last_run": job.last_run.isoformat() if job.last_run else None,
                    "run_count": job.run_count,
                    "errors": job.errors[-5:] if job.errors else []
                }
                for name, job in self._jobs.items()
            }
    
    def get_next_runs(self) -> List[Dict[str, Any]]:
        """Get next scheduled runs."""
        # This is a simplified version - schedule library doesn't expose next run easily
        return []


def create_cron_scheduler(pipeline_orchestrator=None) -> CronScheduler:
    """Factory function to create cron scheduler."""
    return CronScheduler(pipeline_orchestrator)


__all__ = [
    "CronScheduler",
    "CronJob",
    "create_cron_scheduler"
]