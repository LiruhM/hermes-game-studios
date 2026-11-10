"""
Memory Substrate v1.0 — Vault Adapter
Obsidian Vault operations: read, write, search, dataview, wikilinks.
"""

import os
import re
import yaml
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from dataclasses import dataclass

from ..models import (
    MemoryChunk, VaultFile, SourceType, PARALayer, PARACategory,
    SearchResult
)


@dataclass
class VaultAdapterConfig:
    vault_path: str
    watch_enabled: bool = True
    excluded_patterns: List[str] = None
    max_content_length: int = 50000
    search_limit: int = 50
    context_lines: int = 3
    
    def __post_init__(self):
        if self.excluded_patterns is None:
            self.excluded_patterns = [
                ".obsidian/**",
                ".trash/**",
                "**/*.tmp",
                "**/.git/**",
                "node_modules/**",
                "__pycache__/**"
            ]


class VaultAdapter:
    """
    Adapter for Obsidian Vault operations.
    Provides read/write/search/dataview/wikilink functionality.
    """
    
    def __init__(self, config: VaultAdapterConfig):
        self.config = config
        self.vault_path = Path(config.vault_path).resolve()
        self._watcher = None
        self._watch_callback = None
        
        if not self.vault_path.exists():
            raise ValueError(f"Vault path does not exist: {self.vault_path}")
    
    # ============================================================
    # FILE OPERATIONS
    # ============================================================
    
    def list_files(self, pattern: str = "**/*.md") -> List[VaultFile]:
        """List all markdown files in vault matching pattern."""
        files = []
        for path in self.vault_path.glob(pattern):
            if self._is_excluded(path):
                continue
            
            try:
                vault_file = self.read_file(path)
                files.append(vault_file)
            except Exception as e:
                # Skip files that can't be read
                continue
        
        return files
    
    def read_file(self, path: str) -> VaultFile:
        """Read a vault file with frontmatter parsing."""
        full_path = Path(path)
        if not full_path.is_absolute():
            full_path = self.vault_path / path
        
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {full_path}")
        
        stat = full_path.stat()
        content = full_path.read_text(encoding="utf-8", errors="replace")
        
        # Parse frontmatter
        frontmatter, body = self._parse_frontmatter(content)
        
        # Extract wikilinks
        wikilinks = self._extract_wikilinks(body)
        
        vault_file = VaultFile(
            path=str(full_path),
            relative_path=str(full_path.relative_to(self.vault_path)),
            content=body,
            frontmatter=frontmatter,
            stat=stat,
            wikilinks=wikilinks,
            backlinks=[]  # Computed separately
        )
        
        return vault_file
    
    def write_file(self, path: str, content: str, frontmatter: Dict = None) -> bool:
        """Write file to vault with frontmatter."""
        full_path = self.vault_path / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Build content with frontmatter
        if frontmatter:
            fm_yaml = yaml.dump(frontmatter, allow_unicode=True, sort_keys=False)
            full_content = f"---\n{fm_yaml}---\n\n{content}"
        else:
            full_content = content
        
        full_path.write_text(full_content, encoding="utf-8")
        return True
    
    def delete_file(self, path: str) -> bool:
        """Delete file (move to .trash)."""
        full_path = self.vault_path / path
        if not full_path.exists():
            return False
        
        # Move to .trash
        trash_dir = self.vault_path / ".trash"
        trash_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        trash_path = trash_dir / f"{timestamp}_{full_path.name}"
        full_path.rename(trash_path)
        
        return True
    
    def move_file(self, source: str, destination: str) -> bool:
        """Move file within vault."""
        src = self.vault_path / source
        dst = self.vault_path / destination
        
        if not src.exists():
            return False
        
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
        return True
    
    # ============================================================
    # SEARCH OPERATIONS
    # ============================================================
    
    def search(
        self, 
        query: str, 
        folders: List[str] = None,
        tags: List[str] = None,
        limit: int = None,
        context_lines: int = None
    ) -> List[SearchResult]:
        """
        Search vault content with optional filters.
        Returns SearchResult with highlights.
        """
        limit = limit or self.config.search_limit
        context = context_lines or self.config.context_lines
        
        # Build search pattern
        is_regex = self._looks_like_regex(query)
        
        results = []
        seen = set()
        
        for vault_file in self.list_files():
            # Folder filter
            if folders:
                rel_path = vault_file.relative_path
                if not any(rel_path.startswith(f) for f in folders):
                    continue
            
            # Tag filter
            if tags:
                file_tags = vault_file.frontmatter.get("tags", [])
                if isinstance(file_tags, str):
                    file_tags = [t.strip().lstrip("#") for t in file_tags.split(",")]
                elif isinstance(file_tags, list):
                    file_tags = [str(t).lstrip("#") for t in file_tags]
                
                if not any(tag in file_tags for tag in tags):
                    continue
            
            # Search in content
            matches = self._search_in_content(
                vault_file.content, query, is_regex, context
            )
            
            for match in matches:
                # Create chunk for this match
                chunk = vault_file.to_chunk()
                chunk.content = match["context"]
                
                result = SearchResult(
                    chunk=chunk,
                    score=match["score"],
                    match_type="lexical",
                    highlights=[match["line"]]
                )
                
                # Deduplicate by chunk id
                if result.chunk.id not in seen:
                    seen.add(result.chunk.id)
                    results.append(result)
                
                if len(results) >= limit:
                    break
            
            if len(results) >= limit:
                break
        
        # Sort by score descending
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]
    
    def search_by_frontmatter(
        self, 
        key: str, 
        value: Any,
        limit: int = 50
    ) -> List[VaultFile]:
        """Search files by frontmatter key/value."""
        results = []
        for vault_file in self.list_files():
            fm_value = vault_file.frontmatter.get(key)
            if fm_value == value:
                results.append(vault_file)
                if len(results) >= limit:
                    break
        return results
    
    # ============================================================
    # DATAVIEW QUERIES
    # ============================================================
    
    def dataview_query(self, dql: str) -> List[Dict]:
        """
        Execute a Dataview query.
        Note: This is a simplified implementation. Full Dataview
        requires the Obsidian plugin runtime.
        """
        # For now, return empty - would need Dataview JS engine
        # In production, this could call a Node.js subprocess running Dataview
        return []
    
    # ============================================================
    # WIKILINKS & BACKLINKS
    # ============================================================
    
    def resolve_wikilinks(self, content: str) -> List[str]:
        """Resolve [[wikilinks]] to actual file paths."""
        links = self._extract_wikilinks(content)
        resolved = []
        
        for link in links:
            # Try exact match first
            target = self._resolve_wikilink(link)
            if target:
                resolved.append(target)
            else:
                resolved.append(link)  # Keep unresolved
        
        return resolved
    
    def get_backlinks(self, path: str) -> List[str]:
        """Get all files that link to the given path."""
        target_name = Path(path).stem
        backlinks = []
        
        for vault_file in self.list_files():
            if target_name in vault_file.wikilinks:
                backlinks.append(vault_file.relative_path)
        
        return backlinks
    
    def link_notes(self, source: str, target: str, link_type: str = "references") -> bool:
        """Create a wikilink from source to target."""
        src_file = self.read_file(source)
        target_name = Path(target).stem
        
        link_text = f"[[{target_name}]]"
        if link_text not in src_file.content:
            # Append link at end or in a links section
            src_file.content += f"\n\n--- \n{link_type}: {link_text}"
            self.write_file(source, src_file.content, src_file.frontmatter)
            return True
        return False
    
    # ============================================================
    # FILE WATCHER
    # ============================================================
    
    def watch_changes(self, callback: Callable[[str, str], None]) -> bool:
        """
        Watch for file changes in vault.
        Callback receives (event_type, relative_path).
        event_type: "created" | "modified" | "deleted"
        """
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
            
            class VaultEventHandler(FileSystemEventHandler):
                def __init__(self, adapter, cb):
                    self.adapter = adapter
                    self.callback = cb
                
                def on_created(self, event):
                    if not event.is_directory and event.src_path.endswith(".md"):
                        rel = Path(event.src_path).relative_to(self.adapter.vault_path)
                        self.callback("created", str(rel))
                
                def on_modified(self, event):
                    if not event.is_directory and event.src_path.endswith(".md"):
                        rel = Path(event.src_path).relative_to(self.adapter.vault_path)
                        self.callback("modified", str(rel))
                
                def on_deleted(self, event):
                    if not event.is_directory and event.src_path.endswith(".md"):
                        rel = Path(event.src_path).relative_to(self.adapter.vault_path)
                        self.callback("deleted", str(rel))
            
            handler = VaultEventHandler(self, callback)
            self._watcher = Observer()
            self._watcher.schedule(handler, str(self.vault_path), recursive=True)
            self._watcher.start()
            return True
            
        except ImportError:
            # watchdog not available
            return False
    
    def stop_watcher(self):
        """Stop the file watcher."""
        if self._watcher:
            self._watcher.stop()
            self._watcher.join()
            self._watcher = None
    
    # ============================================================
    # HELPER METHODS
    # ============================================================
    
    def _is_excluded(self, path: Path) -> bool:
        """Check if path matches excluded patterns."""
        rel_path = str(path.relative_to(self.vault_path))
        for pattern in self.config.excluded_patterns:
            if self._match_pattern(rel_path, pattern):
                return True
        return False
    
    def _match_pattern(self, path: str, pattern: str) -> bool:
        """Simple glob pattern matching."""
        import fnmatch
        return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, pattern.replace("**/", ""))
    
    def _parse_frontmatter(self, content: str) -> tuple:
        """Parse YAML frontmatter from content."""
        frontmatter = {}
        body = content
        
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    frontmatter = yaml.safe_load(parts[1]) or {}
                    body = parts[2].lstrip("\n")
                except yaml.YAMLError:
                    pass
        
        return frontmatter, body
    
    def _extract_wikilinks(self, content: str) -> List[str]:
        """Extract [[wikilinks]] from content."""
        # Match [[link]] or [[link|alias]]
        pattern = r"\[\[([^\]]+)\]\]"
        matches = re.findall(pattern, content)
        # Remove aliases (after |)
        links = [m.split("|")[0].strip() for m in matches]
        return links
    
    def _resolve_wikilink(self, link: str) -> Optional[str]:
        """Resolve a wikilink to a file path."""
        # Try exact match
        for ext in [".md", ""]:
            test_path = self.vault_path / f"{link}{ext}"
            if test_path.exists():
                return str(test_path.relative_to(self.vault_path))
        
        # Try case-insensitive search
        link_lower = link.lower()
        for path in self.vault_path.rglob("*.md"):
            if path.stem.lower() == link_lower:
                return str(path.relative_to(self.vault_path))
        
        return None
    
    def _search_in_content(
        self, 
        content: str, 
        query: str, 
        is_regex: bool,
        context_lines: int
    ) -> List[Dict]:
        """Search query in content, return matches with context."""
        matches = []
        lines = content.split("\n")
        
        if is_regex:
            pattern = re.compile(query, re.IGNORECASE)
            for i, line in enumerate(lines):
                if pattern.search(line):
                    start = max(0, i - context_lines)
                    end = min(len(lines), i + context_lines + 1)
                    context = "\n".join(lines[start:end])
                    matches.append({
                        "line": line,
                        "context": context,
                        "line_num": i + 1,
                        "score": 1.0
                    })
        else:
            # Simple substring search
            query_lower = query.lower()
            for i, line in enumerate(lines):
                if query_lower in line.lower():
                    start = max(0, i - context_lines)
                    end = min(len(lines), i + context_lines + 1)
                    context = "\n".join(lines[start:end])
                    matches.append({
                        "line": line,
                        "context": context,
                        "line_num": i + 1,
                        "score": 1.0
                    })
        
        return matches
    
    def _looks_like_regex(self, query: str) -> bool:
        """Heuristic to detect if query is a regex."""
        regex_chars = r".*+?^$[]{}|()\\"
        return any(c in query for c in regex_chars) and len(query) > 2


# ============================================================
# FACTORY FUNCTION
# ============================================================

def create_vault_adapter(vault_path: str, **kwargs) -> VaultAdapter:
    """Create vault adapter with default config."""
    config = VaultAdapterConfig(vault_path=vault_path, **kwargs)
    return VaultAdapter(config)