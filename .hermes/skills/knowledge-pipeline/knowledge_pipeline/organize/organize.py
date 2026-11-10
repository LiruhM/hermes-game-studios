"""
Knowledge Compounding Pipeline v1.0 — Organize Stage
PARA routing, drift detection, auto-tagging, and inbox processing.
"""

import os
import re
import shutil
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum


class PARADestination(str, Enum):
    INBOX = "inbox"
    PROJECTS = "projects"
    AREAS = "areas"
    RESOURCES = "resources"
    ARCHIVE = "archive"
    META = "meta"
    SYSTEM = "system"


@dataclass
class OrganizeConfig:
    """Configuration for organize stage."""
    vault_path: str = "C:/Users/mathe/Hermes_Brain"
    para_mapping: Dict[str, str] = field(default_factory=lambda: {
        "projects": "10-Projetos",
        "areas": "20-Areas",
        "resources": "30-Recursos",
        "archive": "40-Arquivo",
        "meta": "50-Meta",
        "system": "90-Sistema",
        "projeto": "10-Projetos",
        "area": "20-Areas",
        "recurso": "30-Recursos",
        "arquivo": "40-Arquivo",
        "sistema": "90-Sistema"
    })
    inbox_paths: List[str] = field(default_factory=lambda: ["00-Inbox", "50-Meta/00-Inbox"])
    
    # Routing rules (type/context -> destination)
    routing_rules: Dict[str, str] = field(default_factory=lambda: {
        "ideia": "projects",
        "tarefa": "projects",
        "problema": "projects",
        "insight": "resources",
        "referencia": "resources",
        "decisao": "meta",
        "reuniao": "meta",
        "fleeting": "inbox"
    })
    
    # Drift detection
    drift_detection: Dict[str, Any] = field(default_factory=lambda: {
        "enabled": True,
        "scan_paths": [
            "C:/Users/mathe/Downloads",
            "C:/Users/mathe/Desktop",
            "C:/Users/mathe/Documents"
        ],
        "exclude_patterns": [
                    "*.tmp", "*.log", "*.dll", "*.exe", "*.pdb", "*.bin", "*.dat", "*.pak", "*.json",
                    ".git/**", "*/.git/**", "**/.git/**", "node_modules/**", "__pycache__/**", ".obsidian/**",
                    "*.pdf", "*.pptx", "*.docx", "*.xlsx", "*.zip", "*.rar", "*.7z",
                    "*.apk", "*.exe", "*.dll", "*.so", "*.dylib", "*.bin", "*.dat", "*.pak"
                ],
        "dry_run_default": True,
        "max_loose_files_alert": 10
    })
    
    # Auto-tagging
    auto_tagging: Dict[str, Any] = field(default_factory=lambda: {
        "enabled": True,
        "tag_taxonomy_path": "30-Recursos/_taxonomy/tags.md",
        "suggest_new_tags": True
    })
    
    # Processing
    process_recursive: bool = True
    max_files_per_run: int = 100


@dataclass
class OrganizeResult:
    """Result of organize operation."""
    moved: List[Dict[str, str]] = field(default_factory=list)
    tagged: List[Dict[str, Any]] = field(default_factory=list)
    drifted: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    dry_run: bool = False


class OrganizeEngine:
    """
    PARA organization engine.
    
    Functions:
    - Route inbox items to correct PARA folders
    - Detect drift (loose files outside PARA)
    - Auto-tag based on content/type
    - Update frontmatter with PARA destination
    """
    
    def __init__(self, config: Optional[OrganizeConfig] = None):
        self.config = config or OrganizeConfig()
        self._vault_path = Path(self.config.vault_path)
    
    def _get_para_path(self, destination: str) -> Path:
        """Get full path for PARA destination."""
        folder = self.config.para_mapping.get(destination, destination)
        return self._vault_path / folder
    
    def _get_destination(self, item_type: str, context: str, content: str) -> str:
        """Determine PARA destination for an item."""
        # Check context keywords FIRST - these are more specific
        context_lower = context.lower()
        if any(kw in context_lower for kw in ["projeto", "project", "sprint", "feature", "tasks", "tarefa", "problema"]):
            return "projects"
        if any(kw in context_lower for kw in ["area", "responsabilidade", "health", "finance"]):
            return "areas"
        if any(kw in context_lower for kw in ["reference", "referencia", "doc", "tutorial", "docs", "checklist", "workflow", "data", "agent", "agents", "squad", "mod", "mods", "plugin", "plugins", "game", "streaming", "backend", "locales", "settings", "scripts", "config", "estudo", "learning", "reference", "vuplex", "xoutput", "bepinex", "hollow", "silksong", "research", "src", "memory", "shared", "template", "templates", "action", "actions", "dbee", "core", "server", "voice", "integration", "integrations", "windows", "claude", "copy", "cyber", "prompt", "managed", "movement", "story", "traffic", "public", "dump", "x86", "dist", "hermes", "assistant", "second", "brain", "aa"]):
            return "resources"
        if any(kw in context_lower for kw in ["meeting", "reuniao", "decisao", "decision", "advisory", "board", "atualizacoes"]):
            return "meta"
        
        # Then check routing rules by type
        if item_type in self.config.routing_rules:
            return self.config.routing_rules[item_type]
        
        return "inbox"
    
    def _parse_frontmatter(self, file_path: Path) -> Tuple[Dict[str, Any], str]:
        """Parse frontmatter from vault file."""
        content = file_path.read_text(encoding="utf-8")
        
        if content.startswith("---"):
            try:
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    frontmatter = yaml.safe_load(parts[1]) or {}
                    body = parts[2].strip()
                    return frontmatter, body
            except Exception:
                pass
        
        return {}, content
    
    def _write_frontmatter(self, file_path: Path, frontmatter: Dict[str, Any], body: str):
        """Write frontmatter and body to file."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("---\n")
            f.write(yaml.dump(frontmatter, allow_unicode=True, sort_keys=False))
            f.write("---\n\n")
            f.write(body)
    
    def _ensure_unique_path(self, dest_path: Path) -> Path:
        """Ensure destination path is unique by adding suffix if needed."""
        if not dest_path.exists():
            return dest_path
        
        stem = dest_path.stem
        suffix = dest_path.suffix
        parent = dest_path.parent
        counter = 1
        
        while True:
            new_path = parent / f"{stem}-{counter}{suffix}"
            if not new_path.exists():
                return new_path
            counter += 1
    
    def process_inbox(
        self,
        auto: bool = True,
        dry_run: bool = False,
        max_files: Optional[int] = None
    ) -> OrganizeResult:
        """
        Process inbox items and route to PARA.
        
        Args:
            auto: Automatically determine destination
            dry_run: Don't actually move files
            max_files: Maximum files to process
            
        Returns:
            OrganizeResult with details
        """
        result = OrganizeResult(dry_run=dry_run)
        max_files = max_files or self.config.max_files_per_run
        
        for inbox_rel in self.config.inbox_paths:
            inbox_path = self._vault_path / inbox_rel
            if not inbox_path.exists():
                continue
            
            files = list(inbox_path.glob("*.md"))
            if self.config.process_recursive:
                files.extend(inbox_path.rglob("*.md"))
            
            for file_path in files[:max_files]:
                try:
                    # Parse frontmatter
                    frontmatter, body = self._parse_frontmatter(file_path)
                    
                    # Determine destination
                    item_type = frontmatter.get("type", "fleeting")
                    context = frontmatter.get("context", "geral")
                    content = frontmatter.get("content", body)
                    
                    if auto:
                        destination = self._get_destination(item_type, context, content)
                    else:
                        destination = "inbox"
                    
                    # Skip if destination is inbox
                    if destination == "inbox":
                        continue
                    
                    # Check if file is already in correct destination folder
                    # (avoid re-moving already organized files)
                    current_folder = file_path.parent.name
                    para_folders = set(self.config.para_mapping.values())
                    if destination in ["projects", "areas", "resources", "archive", "meta", "system"]:
                        expected_folder = self.config.para_mapping.get(destination, destination)
                        if current_folder == expected_folder:
                            continue  # Already in correct folder
                    elif current_folder in para_folders:
                        continue  # Already in some PARA folder
                    
                    # Get destination path
                    dest_folder = self._get_para_path(destination)
                    
                    # Create project/area folder from context if projects/areas
                    if destination in ["projects", "areas"]:
                        # Sanitize context for folder name
                        folder_name = re.sub(r'[^\w\s-]', '', context).strip().replace(' ', '-')
                        if folder_name:
                            dest_folder = dest_folder / folder_name
                    
                    dest_file = self._ensure_unique_path(dest_folder / file_path.name)
                    
                    if not dry_run:
                        # Update frontmatter
                        frontmatter["para_destination"] = destination
                        frontmatter["organized_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        frontmatter["modified"] = datetime.now().strftime("%Y-%m-%d")
                        
                        # Move file
                        dest_folder.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(file_path), str(dest_file))
                        
                        # Write updated frontmatter
                        self._write_frontmatter(dest_file, frontmatter, body)
                    
                    result.moved.append({
                        "source": str(file_path.relative_to(self._vault_path)),
                        "destination": str(dest_file.relative_to(self._vault_path)),
                        "para_destination": destination
                    })
                    
                except Exception as e:
                    result.errors.append(f"{file_path}: {str(e)}")
        
        return result
    
    def detect_drift(self, dry_run: bool = True) -> OrganizeResult:
            """
            Detect files outside PARA structure (drift detection).

            Args:
                dry_run: If True, only report; if False, move to inbox
            
            Returns:
                OrganizeResult with drifted files
            """
            result = OrganizeResult(dry_run=dry_run)

            if not self.config.drift_detection.get("enabled", True):
                return result

            scan_paths = self.config.drift_detection.get("scan_paths", [])
            exclude = self.config.drift_detection.get("exclude_patterns", [])
            max_alert = self.config.drift_detection.get("max_loose_files_alert", 10)

            # Valid PARA folders
            para_folders = set(self.config.para_mapping.values())
            para_folders.add("00-Inbox")
            para_folders.add("50-Meta/00-Inbox")

            # Determine inbox destination
            inbox_path = self._vault_path / "00-Inbox"
            inbox_path.mkdir(parents=True, exist_ok=True)

            for scan_path in scan_paths:
                path = Path(scan_path)
                if not path.exists():
                    continue

                try:
                    # Find files not in PARA
                    for file_path in path.rglob("*"):
                        if not file_path.is_file():
                            continue

                        # Check exclude patterns
                        rel_path = str(file_path)
                        # Use fnmatch for proper pattern matching on full path
                        import fnmatch
                        skip = False
                        for pat in exclude:
                            if fnmatch.fnmatch(rel_path, pat) or fnmatch.fnmatch(file_path.name, pat):
                                skip = True
                                break
                            # Also check if any parent directory matches
                            for part in file_path.parts:
                                if fnmatch.fnmatch(part, pat.replace("**/", "").replace("**", "")):
                                    skip = True
                                    break
                        if skip:
                            continue

                        # Check if already in vault
                        try:
                            file_path.relative_to(self._vault_path)
                            continue  # Already in vault
                        except ValueError:
                            pass  # Outside vault - drift!

                        drift_info = {
                            "file": str(file_path),
                            "size": file_path.stat().st_size,
                            "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
                            "suggested_action": "move_to_inbox"
                        }

                        result.drifted.append(drift_info)

                        # Actually move to inbox if not dry_run
                        if not dry_run:
                            try:
                                dest_file = self._ensure_unique_path(inbox_path / file_path.name)
                                shutil.move(str(file_path), str(dest_file))
                                result.moved.append({
                                    "source": str(file_path),
                                    "destination": str(dest_file.relative_to(self._vault_path)),
                                    "para_destination": "inbox"
                                })
                            except Exception as e:
                                result.errors.append(f"Failed to move {file_path}: {str(e)}")

                        if len(result.drifted) >= max_alert:
                            break
                except (OSError, FileNotFoundError, PermissionError):
                    continue  # Skip inaccessible directories

            return result
    
    def auto_tag(self, file_path: Path) -> List[str]:
        """Auto-generate tags for a file based on content."""
        if not self.config.auto_tagging.get("enabled", True):
            return []
        
        frontmatter, body = self._parse_frontmatter(file_path)
        existing_tags = frontmatter.get("tags", [])
        
        # Extract potential tags from content
        new_tags = []
        content = body.lower()
        
        # Common tag patterns
        tag_patterns = {
            "#python": ["python", "py"],
            "#javascript": ["javascript", "js", "node"],
            "#api": ["api", "rest", "endpoint"],
            "#database": ["sql", "database", "postgres", "mysql"],
            "#docker": ["docker", "container"],
            "#kubernetes": ["kubernetes", "k8s"],
            "#ml": ["machine learning", "ml", "model", "training"],
            "#llm": ["llm", "gpt", "transformer", "token"],
            "#rag": ["rag", "retrieval", "embedding"],
            "#security": ["security", "auth", "encryption", "vulnerability"]
        }
        
        for tag, keywords in tag_patterns.items():
            if any(kw in content for kw in keywords) and tag not in existing_tags:
                new_tags.append(tag)
        
        return new_tags
    
    def apply_tags(self, file_path: Path, tags: List[str], dry_run: bool = False) -> bool:
        """Apply tags to a file's frontmatter."""
        try:
            frontmatter, body = self._parse_frontmatter(file_path)
            existing = set(frontmatter.get("tags", []))
            existing.update(tags)
            frontmatter["tags"] = sorted(list(existing))
            frontmatter["modified"] = datetime.now().strftime("%Y-%m-%d")
            
            if not dry_run:
                self._write_frontmatter(file_path, frontmatter, body)
            
            return True
        except Exception:
            return False


def create_organize_engine(config: Optional[OrganizeConfig] = None) -> OrganizeEngine:
    """Factory function to create organize engine."""
    return OrganizeEngine(config)


__all__ = [
    "OrganizeEngine",
    "OrganizeConfig",
    "OrganizeResult",
    "PARADestination",
    "create_organize_engine"
]