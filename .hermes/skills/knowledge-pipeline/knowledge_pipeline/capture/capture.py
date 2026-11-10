"""
Knowledge Compounding Pipeline v1.0 — Capture Stage
Unified capture from vault, MemPalace, external sources, and user input.
"""

import os
import re
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from enum import Enum


class CaptureSource(str, Enum):
    USER_INPUT = "user_input"
    VAULT_INBOX = "vault_inbox"
    MEMPALACE = "mempalace"
    EXTERNAL_FILE = "external_file"
    WEB_CLIP = "web_clip"
    API_RESPONSE = "api_response"
    HOOK_EVENT = "hook_event"


class CaptureType(str, Enum):
    IDEA = "ideia"
    TASK = "tarefa"
    REFERENCE = "referencia"
    FLEETING = "fleeting"
    PROBLEM = "problema"
    INSIGHT = "insight"
    DECISION = "decisao"
    MEETING_NOTE = "reuniao"


@dataclass
class CaptureConfig:
    """Configuration for capture stage."""
    vault_path: str = "C:/Users/mathe/Hermes_Brain"
    inbox_paths: List[str] = field(default_factory=lambda: ["00-Inbox", "50-Meta/00-Inbox"])
    external_scan_paths: List[str] = field(default_factory=lambda: [
        "C:/Users/mathe/Downloads",
        "C:/Users/mathe/Desktop",
        "C:/Users/mathe/Documents"
    ])
    exclude_patterns: List[str] = field(default_factory=lambda: [
        "*.tmp", "*.log", "*.dll", "*.exe", "*.pdb", "*.bin", "*.dat", "*.pak", "*.json",
        ".git/", "*/.git/", "**/.git/", "node_modules/", "__pycache__/", ".obsidian/"
    ])
    template: str = """[[{{date}}]] | #{{type}} #{{context}}
{{content}}
#revisar"""
    default_tags: List[str] = field(default_factory=lambda: ["#revisar"])
    auto_tag_types: List[str] = field(default_factory=lambda: [
        "ideia", "tarefa", "referencia", "fleeting", "problema", "insight", "decisao"
    ])
    default_type: str = "fleeting"
    default_context: str = "geral"
    max_content_length: int = 50000
    deduplicate: bool = True
    similarity_threshold: float = 0.85


@dataclass
class CapturedItem:
    """A captured knowledge item."""
    id: str
    content: str
    type: CaptureType
    context: str
    source: CaptureSource
    source_path: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    vault_path: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "type": self.type.value,
            "context": self.context,
            "source": self.source.value,
            "source_path": self.source_path,
            "tags": self.tags,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "vault_path": self.vault_path
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CapturedItem":
        item = cls(
            id=data["id"],
            content=data["content"],
            type=CaptureType(data["type"]),
            context=data["context"],
            source=CaptureSource(data["source"]),
            source_path=data.get("source_path"),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            vault_path=data.get("vault_path")
        )
        return item


class CaptureEngine:
    """
    Unified capture engine for all knowledge inputs.
    
    Sources:
    - Direct user input (via /capture command)
    - Vault inbox files (00-Inbox, 50-Meta/00-Inbox)
    - MemPalace drawers (auto-sync)
    - External files (Downloads, Desktop, Documents)
    - Web clippings (via API)
    - Hook events (from other skills)
    """
    
    def __init__(self, config: Optional[CaptureConfig] = None):
        self.config = config or CaptureConfig()
        self._vault_path = Path(self.config.vault_path)
        self._state_path = self._vault_path / "90-Sistema" / "_state" / "capture_seen.json"
        self._seen_hashes: set = self._load_seen_hashes()

    def _load_seen_hashes(self) -> set:
        """Load persisted content hashes (survives cron restarts)."""
        try:
            if self._state_path.exists():
                data = json.loads(self._state_path.read_text(encoding="utf-8"))
                return set(data.get("hashes", []))
        except Exception:
            pass
        return set()

    def _save_seen_hashes(self) -> None:
        """Persist seen hashes to disk so future runs skip captured content."""
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            self._state_path.write_text(
                json.dumps({"hashes": sorted(self._seen_hashes)}, indent=0),
                encoding="utf-8"
            )
        except Exception:
            pass
    
    def _generate_id(self, prefix: str = "cap") -> str:
        """Generate unique capture ID."""
        import uuid
        return f"{prefix}-{uuid.uuid4().hex[:8]}"
    
    def _compute_hash(self, content: str) -> str:
        """Compute content hash for deduplication."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _is_duplicate(self, content: str) -> bool:
        """Check if content is duplicate."""
        if not self.config.deduplicate:
            return False
        h = self._compute_hash(content)
        if h in self._seen_hashes:
            return True
        self._seen_hashes.add(h)
        return False
    
    def _render_template(self, content: str, type_: CaptureType, context: str) -> str:
        """Render capture template."""
        return self.config.template.replace(
            "{{date}}", datetime.now().strftime("%Y-%m-%d")
        ).replace(
            "{{type}}", type_.value
        ).replace(
            "{{context}}", context
        ).replace(
            "{{content}}", content
        )
    
    def _get_inbox_path(self, type_: CaptureType) -> Path:
        """Get inbox path for capture type."""
        # Use first inbox path
        inbox = self.config.inbox_paths[0] if self.config.inbox_paths else "00-Inbox"
        return self._vault_path / inbox
    
    def _get_filename(self, item: CapturedItem) -> str:
        """Generate filename for captured item."""
        date_str = item.timestamp.strftime("%Y-%m-%d")
        # Clean content for filename: remove newlines, special chars
        clean_content = re.sub(r'[\n\r]+', ' ', item.content[:50])
        slug = re.sub(r'[^\w\s-]', '', clean_content).strip().replace(' ', '-')
        return f"{date_str}-{item.type.value}-{slug[:40]}.md"
    
    def _build_frontmatter(self, item: CapturedItem) -> Dict[str, Any]:
        """Build frontmatter for vault note."""
        return {
            "id": item.id,
            "type": item.type.value,
            "source": item.source.value,
            "context": item.context,
            "tags": item.tags + self.config.default_tags,
            "para_destination": self._infer_para_destination(item),
            "created": item.timestamp.strftime("%Y-%m-%d"),
            "modified": item.timestamp.strftime("%Y-%m-%d"),
            **item.metadata
        }
    
    def _infer_para_destination(self, item: CapturedItem) -> str:
        """Infer PARA destination from capture type."""
        mapping = {
            CaptureType.IDEA: "projects",
            CaptureType.TASK: "projects",
            CaptureType.PROBLEM: "projects",
            CaptureType.INSIGHT: "resources",
            CaptureType.REFERENCE: "resources",
            CaptureType.DECISION: "meta",
            CaptureType.MEETING_NOTE: "meta",
            CaptureType.FLEETING: "inbox"
        }
        return mapping.get(item.type, "inbox")
    
    def capture(
        self,
        content: str,
        type_: Union[str, CaptureType] = CaptureType.FLEETING,
        context: str = "geral",
        source: CaptureSource = CaptureSource.USER_INPUT,
        source_path: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        write_to_vault: bool = True
    ) -> CapturedItem:
        """
        Capture a knowledge item.
        
        Args:
            content: The content to capture
            type_: Type of capture (ideia, tarefa, etc.)
            context: Context/topic tag
            source: Source of capture
            source_path: Original file/path if from file
            tags: Additional tags
            metadata: Extra metadata
            write_to_vault: Whether to write to Obsidian vault
            
        Returns:
            CapturedItem with vault_path if written
        """
        # Normalize type
        if isinstance(type_, str):
            try:
                type_ = CaptureType(type_)
            except ValueError:
                type_ = CaptureType.FLEETING
        
        # Check duplicate
        if self._is_duplicate(content):
            return CapturedItem(
                id="duplicate",
                content=content,
                type=type_,
                context=context,
                source=source,
                metadata={"duplicate": True}
            )
        
        # Create item
        item = CapturedItem(
            id=self._generate_id(),
            content=content.strip(),
            type=type_,
            context=context,
            source=source,
            source_path=source_path,
            tags=tags or [],
            metadata=metadata or {}
        )
        
        # Write to vault
        if write_to_vault:
            vault_path = self._write_to_vault(item)
            item.vault_path = vault_path
        
        # Persist dedup state after successful capture
        self._save_seen_hashes()
        
        return item
    
    def _write_to_vault(self, item: CapturedItem) -> str:
        """Write captured item to Obsidian vault."""
        inbox_path = self._get_inbox_path(item.type)
        inbox_path.mkdir(parents=True, exist_ok=True)
        
        filename = self._get_filename(item)
        file_path = inbox_path / filename
        
        # Build content with frontmatter
        frontmatter = self._build_frontmatter(item)
        
        # Render body
        body = self._render_template(item.content, item.type, item.context)
        
        # Write file
        import yaml
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("---\n")
            f.write(yaml.dump(frontmatter, allow_unicode=True, sort_keys=False))
            f.write("---\n\n")
            f.write(body)
        
        return str(file_path.relative_to(self._vault_path))
    
    def scan_external_sources(self, dry_run: bool = True) -> List[CapturedItem]:
            """Scan external directories for loose files."""
            captured = []

            for scan_path in self.config.external_scan_paths:
                path = Path(scan_path)
                if not path.exists():
                    continue

                try:
                    for file_path in path.rglob("*"):
                        if file_path.is_file():
                            # Check exclude patterns
                            import fnmatch
                            rel_path = str(file_path)
                            skip = False
                            for pat in self.config.exclude_patterns:
                                if fnmatch.fnmatch(rel_path, pat) or fnmatch.fnmatch(file_path.name, pat):
                                    skip = True
                                    break
                                for part in file_path.parts:
                                    if fnmatch.fnmatch(part, pat.replace("**/", "").replace("**", "")):
                                        skip = True
                                        break
                            if skip:
                                continue

                            # Read file content (text files only)
                            if file_path.suffix.lower() in [".md", ".txt", ".py", ".js", ".json", ".yaml", ".yml"]:
                                try:
                                    content = file_path.read_text(encoding="utf-8")
                                    if len(content) > self.config.max_content_length:
                                        content = content[:self.config.max_content_length]

                                    # Infer type from path/name
                                    type_ = self._infer_type_from_path(file_path)

                                    item = self.capture(
                                        content=content,
                                        type_=type_,
                                        context=file_path.parent.name,
                                        source=CaptureSource.EXTERNAL_FILE,
                                        source_path=str(file_path),
                                        tags=["#external", f"#source:{file_path.parent.name}"],
                                        write_to_vault=not dry_run
                                    )
                                    # Skip duplicates (already captured in a previous run)
                                    if item.id == "duplicate":
                                        continue
                                    captured.append(item)
                                except Exception:
                                    pass
                except (OSError, PermissionError, FileNotFoundError):
                    continue

            return captured
    
    def _infer_type_from_path(self, path: Path) -> CaptureType:
        """Infer capture type from file path."""
        name = path.name.lower()
        parent = path.parent.name.lower()
        
        if any(kw in name for kw in ["todo", "task", "tarefa"]):
            return CaptureType.TASK
        if any(kw in name for kw in ["idea", "ideia", "conceito"]):
            return CaptureType.IDEA
        if any(kw in name for kw in ["problem", "problema", "bug", "issue"]):
            return CaptureType.PROBLEM
        if any(kw in name for kw in ["meeting", "reuniao", "call", "sync"]):
            return CaptureType.MEETING_NOTE
        if any(kw in parent for kw in ["project", "projeto"]):
            return CaptureType.TASK
        if any(kw in parent for kw in ["reference", "referencia", "docs"]):
            return CaptureType.REFERENCE
        
        return CaptureType.FLEETING
    
    def capture_from_mempalace(self, drawer_ids: List[str]) -> List[CapturedItem]:
        """Capture items from MemPalace drawers (placeholder for MCP integration)."""
        # This would integrate with MemPalace MCP
        # For now, return empty
        return []
    
    def batch_capture(
        self,
        items: List[Dict[str, Any]],
        write_to_vault: bool = True
    ) -> List[CapturedItem]:
        """Capture multiple items at once."""
        captured = []
        for item_data in items:
            item = self.capture(
                content=item_data.get("content", ""),
                type_=item_data.get("type", CaptureType.FLEETING),
                context=item_data.get("context", "geral"),
                source=item_data.get("source", CaptureSource.USER_INPUT),
                source_path=item_data.get("source_path"),
                tags=item_data.get("tags"),
                metadata=item_data.get("metadata"),
                write_to_vault=write_to_vault
            )
            captured.append(item)
        return captured


def create_capture_engine(config: Optional[CaptureConfig] = None) -> CaptureEngine:
    """Factory function to create capture engine."""
    return CaptureEngine(config)


__all__ = [
    "CaptureEngine",
    "CaptureConfig",
    "CapturedItem",
    "CaptureSource",
    "CaptureType",
    "create_capture_engine"
]