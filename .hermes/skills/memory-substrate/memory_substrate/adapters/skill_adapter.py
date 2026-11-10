"""
Memory Substrate v1.0 — Skill Adapter
Skill operations: manifest parsing, dependency resolution, loading, validation.
"""

import os
import yaml
import json
import importlib.util
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

from ..models import (
    MemoryChunk, SourceType, PARALayer, PARACategory, SkillManifest,
    SearchResult
)


@dataclass
class SkillAdapterConfig:
    skills_dir: str
    manifest_version: int = 2
    auto_discover: bool = True
    validate_on_load: bool = True
    cache_ttl_seconds: int = 300


class SkillAdapter:
    """
    Adapter for Hermes Skills.
    Provides manifest parsing, dependency resolution, skill loading, and validation.
    """
    
    def __init__(self, config: SkillAdapterConfig):
        self.config = config
        self.skills_dir = Path(config.skills_dir).resolve()
        self._manifest_cache: Dict[str, SkillManifest] = {}
        self._module_cache: Dict[str, Any] = {}
        self._dependency_graph: Dict[str, List[str]] = {}
        self._cache_timestamp: Optional[float] = None
    
    # ============================================================
    # MANIFEST OPERATIONS
    # ============================================================
    
    def list_skills(self, enabled_only: bool = True) -> List[SkillManifest]:
        """List all discovered skills with parsed manifests."""
        self._refresh_cache_if_needed()
        return list(self._manifest_cache.values())
    
    def get_skill(self, name: str) -> Optional[SkillManifest]:
        """Get manifest for a specific skill."""
        self._refresh_cache_if_needed()
        return self._manifest_cache.get(name)
    
    def get_skill_path(self, name: str) -> Optional[Path]:
        """Get the filesystem path for a skill."""
        self._refresh_cache_if_needed()
        skill_dir = self.skills_dir / name
        if skill_dir.exists() and skill_dir.is_dir():
            return skill_dir
        return None
    
    def _refresh_cache_if_needed(self):
        """Refresh manifest cache if stale."""
        import time
        now = time.time()
        if self._cache_timestamp is None or (now - self._cache_timestamp) > self.config.cache_ttl_seconds:
            self._discover_skills()
            self._cache_timestamp = now
    
    def _discover_skills(self):
        """Discover and parse all skill manifests."""
        self._manifest_cache = {}
        self._dependency_graph = {}
        
        if not self.skills_dir.exists():
            return
        
        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            
            # Skip special directories
            if skill_dir.name.startswith(".") or skill_dir.name in ["__pycache__", "30-Recursos", "90-Sistema"]:
                continue
            
            manifest = self._parse_skill_manifest(skill_dir)
            if manifest:
                self._manifest_cache[manifest.name] = manifest
                self._dependency_graph[manifest.name] = manifest.dependencies.get("required", [])
    
    def _parse_skill_manifest(self, skill_dir: Path) -> Optional[SkillManifest]:
        """Parse SKILL.md frontmatter as SkillManifest."""
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            return None
        
        try:
            content = skill_md.read_text(encoding="utf-8", errors="replace")
            
            # Extract frontmatter
            frontmatter, _ = self._parse_frontmatter(content)
            if not frontmatter:
                return None
            
            # Parse dependencies
            deps = frontmatter.get("dependencies", {})
            if isinstance(deps, dict):
                required = deps.get("required", [])
                optional = deps.get("optional", [])
            else:
                # Legacy format: list of strings
                required = deps if isinstance(deps, list) else []
                optional = []
            
            # Parse capabilities
            caps = frontmatter.get("capabilities", {})
            provides = caps.get("provides", []) if isinstance(caps, dict) else []
            consumes = caps.get("consumes", []) if isinstance(caps, dict) else []
            
            # Parse entry points
            entry_points = frontmatter.get("entry_points", {})
            if not isinstance(entry_points, dict):
                entry_points = {}
            
            # Ensure required fields
            name = frontmatter.get("name", skill_dir.name)
            version = frontmatter.get("version", "1.0.0")
            description = frontmatter.get("description", "")
            category = frontmatter.get("category", "general")
            
            manifest = SkillManifest(
                name=name,
                version=version,
                description=description,
                category=category,
                author=frontmatter.get("author", "Hermes Agent"),
                license=frontmatter.get("license", "MIT"),
                min_hermes_version=frontmatter.get("min_hermes_version", "0.20.0"),
                tags=frontmatter.get("tags", []),
                dependencies={"required": required, "optional": optional},
                capabilities={"provides": provides, "consumes": consumes},
                config_schema=frontmatter.get("config_schema", {}),
                entry_points=entry_points,
                metadata=frontmatter.get("metadata", {})
            )
            
            return manifest
            
        except Exception as e:
            print(f"Failed to parse manifest for {skill_dir.name}: {e}")
            return None
    
    def _parse_frontmatter(self, content: str) -> tuple:
        """Parse YAML frontmatter from content."""
        import yaml
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
    
    # ============================================================
    # DEPENDENCY RESOLUTION
    # ============================================================
    
    def get_dependency_graph(self) -> Dict[str, List[str]]:
        """Get the full dependency graph."""
        self._refresh_cache_if_needed()
        return dict(self._dependency_graph)
    
    def resolve_dependencies(self, skill_name: str) -> List[str]:
        """Resolve all dependencies for a skill (transitive closure)."""
        self._refresh_cache_if_needed()
        
        if skill_name not in self._dependency_graph:
            return []
        
        resolved = set()
        to_process = list(self._dependency_graph.get(skill_name, []))
        
        while to_process:
            dep = to_process.pop()
            if dep not in resolved:
                resolved.add(dep)
                # Add transitive dependencies
                to_process.extend(self._dependency_graph.get(dep, []))
        
        return sorted(resolved)
    
    def get_load_order(self, skill_names: List[str]) -> List[str]:
        """Determine load order respecting dependencies (topological sort)."""
        self._refresh_cache_if_needed()
        
        # Build subgraph for requested skills
        subgraph = {}
        all_deps = set()
        
        for skill in skill_names:
            deps = self.resolve_dependencies(skill)
            subgraph[skill] = [d for d in deps if d in skill_names]
            all_deps.update(deps)
        
        # Add dependencies that are also in the requested set
        for dep in all_deps:
            if dep in skill_names and dep not in subgraph:
                subgraph[dep] = [d for d in self.resolve_dependencies(dep) if d in skill_names]
        
        # Topological sort (Kahn's algorithm)
        in_degree = {skill: 0 for skill in subgraph}
        for skill, deps in subgraph.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[dep] += 1
        
        queue = [skill for skill, degree in in_degree.items() if degree == 0]
        result = []
        
        while queue:
            skill = queue.pop(0)
            result.append(skill)
            
            for dependent, deps in subgraph.items():
                if skill in deps:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)
        
        if len(result) != len(subgraph):
            # Cycle detected - return best effort
            return skill_names
        
        return result
    
    def check_circular_dependencies(self) -> List[List[str]]:
        """Detect circular dependencies in the skill graph."""
        self._refresh_cache_if_needed()
        
        visited = set()
        rec_stack = set()
        cycles = []
        
        def dfs(node, path):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in self._dependency_graph.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor, path.copy())
                elif neighbor in rec_stack:
                    # Found cycle
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    if cycle not in cycles:
                        cycles.append(cycle)
            
            rec_stack.remove(node)
        
        for node in self._dependency_graph:
            if node not in visited:
                dfs(node, [])
        
        return cycles
    
    # ============================================================
    # SKILL LOADING
    # ============================================================
    
    def load_skill(self, name: str) -> Optional[Any]:
        """Load a skill as a Python module."""
        if name in self._module_cache:
            return self._module_cache[name]
        
        skill_path = self.get_skill_path(name)
        if not skill_path:
            return None
        
        # Check for __init__.py
        init_file = skill_path / "__init__.py"
        if not init_file.exists():
            # Try to find any Python file
            py_files = list(skill_path.glob("*.py"))
            if not py_files:
                return None
            init_file = py_files[0]
        
        try:
            # Load module
            spec = importlib.util.spec_from_file_location(name, init_file)
            if spec is None or spec.loader is None:
                return None
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            
            self._module_cache[name] = module
            return module
            
        except Exception as e:
            print(f"Failed to load skill {name}: {e}")
            return None
    
    def get_entry_point(self, name: str, entry_type: str = "main") -> Optional[Callable]:
        """Get entry point function from skill."""
        module = self.load_skill(name)
        if not module:
            return None
        
        manifest = self.get_skill(name)
        if not manifest:
            return None
        
        entry_point_name = manifest.entry_points.get(entry_type, "")
        if not entry_point_name:
            # Try common patterns
            if entry_type == "main":
                entry_point_name = "main"
            elif entry_type == "cli":
                entry_point_name = "cli"
            elif entry_type == "api":
                entry_point_name = "router"
        
        if hasattr(module, entry_point_name):
            return getattr(module, entry_point_name)
        
        return None
    
    def validate_skill(self, name: str) -> Dict[str, Any]:
        """Validate a skill's structure and manifest."""
        result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "checks": {}
        }
        
        skill_path = self.get_skill_path(name)
        if not skill_path:
            result["valid"] = False
            result["errors"].append(f"Skill directory not found: {name}")
            return result
        
        # Check SKILL.md exists
        skill_md = skill_path / "SKILL.md"
        result["checks"]["skill_md_exists"] = skill_md.exists()
        if not skill_md.exists():
            result["valid"] = False
            result["errors"].append("SKILL.md not found")
        
        # Check __init__.py exists
        init_file = skill_path / "__init__.py"
        result["checks"]["init_py_exists"] = init_file.exists()
        if not init_file.exists():
            result["warnings"].append("__init__.py not found (skill may not be loadable)")
        
        # Validate manifest
        manifest = self.get_skill(name)
        if manifest:
            result["checks"]["manifest_parsed"] = True
            
            # Check required fields
            if not manifest.name:
                result["valid"] = False
                result["errors"].append("Missing 'name' in manifest")
            
            if not manifest.version:
                result["warnings"].append("Missing 'version' in manifest")
            
            if not manifest.description:
                result["warnings"].append("Missing 'description' in manifest")
            
            # Validate dependencies exist
            for dep in manifest.dependencies.get("required", []):
                if dep not in self._manifest_cache:
                    result["warnings"].append(f"Required dependency not found: {dep}")
            
            # Validate entry points
            for ep_type, ep_name in manifest.entry_points.items():
                if ep_name and not hasattr(self.load_skill(name), ep_name):
                    result["warnings"].append(f"Entry point '{ep_name}' ({ep_type}) not found in module")
        else:
            result["valid"] = False
            result["errors"].append("Failed to parse manifest")
        
        return result
    
    # ============================================================
    # SKILL MANAGEMENT
    # ============================================================
    
    def install_skill(self, source: str, name: str) -> Optional[SkillManifest]:
        """Install a skill from a source (git repo, zip, local path)."""
        import shutil
        import tempfile
        import subprocess
        
        target_dir = self.skills_dir / name
        
        if target_dir.exists():
            raise ValueError(f"Skill already exists: {name}")
        
        # Handle different source types
        if source.startswith("http://") or source.startswith("https://"):
            # Git repository
            with tempfile.TemporaryDirectory() as tmpdir:
                repo_dir = Path(tmpdir) / "repo"
                subprocess.run(["git", "clone", source, str(repo_dir)], check=True)
                
                # Find SKILL.md
                skill_md = list(repo_dir.rglob("SKILL.md"))
                if not skill_md:
                    raise ValueError("No SKILL.md found in repository")
                
                skill_root = skill_md[0].parent
                shutil.copytree(skill_root, target_dir)
        
        elif source.endswith(".zip"):
            # Zip file
            with tempfile.TemporaryDirectory() as tmpdir:
                import zipfile
                with zipfile.ZipFile(source, 'r') as zf:
                    zf.extractall(tmpdir)
                
                extracted = Path(tmpdir)
                skill_md = list(extracted.rglob("SKILL.md"))
                if not skill_md:
                    raise ValueError("No SKILL.md found in zip")
                
                skill_root = skill_md[0].parent
                shutil.copytree(skill_root, target_dir)
        
        else:
            # Local path
            source_path = Path(source)
            if not source_path.exists():
                raise ValueError(f"Source not found: {source}")
            
            skill_md = list(source_path.rglob("SKILL.md"))
            if not skill_md:
                raise ValueError("No SKILL.md found in source")
            
            skill_root = skill_md[0].parent
            shutil.copytree(skill_root, target_dir)
        
        # Validate and refresh
        self._discover_skills()
        manifest = self.get_skill(name)
        
        if not manifest:
            # Cleanup on failure
            shutil.rmtree(target_dir, ignore_errors=True)
            raise ValueError(f"Installed skill failed validation: {name}")
        
        return manifest
    
    def remove_skill(self, name: str) -> bool:
        """Remove a skill."""
        import shutil
        
        skill_path = self.get_skill_path(name)
        if not skill_path:
            return False
        
        # Check if other skills depend on it
        dependents = []
        for skill_name, deps in self._dependency_graph.items():
            if name in deps:
                dependents.append(skill_name)
        
        if dependents:
            raise ValueError(f"Cannot remove {name}: required by {dependents}")
        
        shutil.rmtree(skill_path)
        self._discover_skills()
        return True
    
    # ============================================================
    # CONVERSION TO MEMORY CHUNKS
    # ============================================================
    
    def skill_to_chunk(self, manifest: SkillManifest) -> MemoryChunk:
        """Convert a SkillManifest to a MemoryChunk."""
        chunk = MemoryChunk(
            source=SourceType.SKILL,
            source_id=manifest.name,
            content=f"{manifest.description}\n\nCapabilities: {manifest.capabilities}",
            title=manifest.name,
            skill_name=manifest.name,
            skill_version=manifest.version,
            tags=manifest.tags,
            metadata={
                "version": manifest.version,
                "category": manifest.category,
                "dependencies": manifest.dependencies,
                "capabilities": manifest.capabilities,
                "entry_points": manifest.entry_points
            }
        )
        chunk.para_category = PARACategory.SYSTEM
        chunk.para_layer = PARALayer.RESOURCE
        return chunk
    
    def get_all_skills_as_chunks(self) -> List[MemoryChunk]:
        """Get all skills as MemoryChunks."""
        chunks = []
        for manifest in self._manifest_cache.values():
            chunks.append(self.skill_to_chunk(manifest))
        return chunks


# ============================================================
# FACTORY FUNCTION
# ============================================================

def create_skill_adapter(skills_dir: str, **kwargs) -> SkillAdapter:
    """Create skill adapter with default config."""
    config = SkillAdapterConfig(skills_dir=skills_dir, **kwargs)
    return SkillAdapter(config)