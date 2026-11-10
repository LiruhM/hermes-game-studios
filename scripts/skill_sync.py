#!/usr/bin/env python3
"""
Skill Sync Script
Syncs local skills with the Hermes skills registry and remote sources.
"""

import json
import os
import sys
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional


def get_skills_dirs() -> Dict[str, Path]:
    """Get all skill directories."""
    localappdata = os.environ.get("LOCALAPPDATA", "")
    if not localappdata:
        raise RuntimeError("LOCALAPPDATA not set")
    
    base = Path(localappdata) / "hermes" / "skills"
    project_skills = Path.cwd() / ".hermes" / "skills"
    
    return {
        "global": base,
        "project": project_skills,
    }


def load_skill_registry() -> Dict[str, Any]:
    """Load the skill registry."""
    registry_path = Path.cwd() / ".hermes" / "skills" / "registry.yaml"
    if registry_path.exists():
        try:
            import yaml
            return yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
        except Exception:
            pass
    return {}


def scan_skills_dir(skills_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Scan a skills directory for skill metadata."""
    skills = {}
    if not skills_dir.exists():
        return skills
    
    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        
        try:
            import yaml
            content = skill_md.read_text(encoding="utf-8")
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    frontmatter = yaml.safe_load(parts[1])
                    frontmatter["path"] = str(skill_dir)
                    frontmatter["source"] = "global" if "AppData" in str(skill_dir) else "project"
                    skills[skill_dir.name] = frontmatter
        except Exception as e:
            print(f"Error reading {skill_md}: {e}", file=sys.stderr)
    
    return skills


def sync_skills(dry_run: bool = False) -> Dict[str, Any]:
    """Sync skills between global and project directories."""
    dirs = get_skills_dirs()
    global_skills = scan_skills_dir(dirs["global"])
    project_skills = scan_skills_dir(dirs["project"])
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "global_count": len(global_skills),
        "project_count": len(project_skills),
        "synced": [],
        "conflicts": [],
        "errors": [],
    }
    
    # Ensure project skills dir exists
    dirs["project"].mkdir(parents=True, exist_ok=True)
    
    # Sync global skills to project (if not present)
    for name, skill in global_skills.items():
        if name not in project_skills:
            src = Path(skill["path"])
            dst = dirs["project"] / name
            if not dry_run:
                try:
                    if dst.exists():
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                    results["synced"].append({"name": name, "action": "copied_global_to_project"})
                except Exception as e:
                    results["errors"].append({"name": name, "error": str(e)})
            else:
                results["synced"].append({"name": name, "action": "would_copy_global_to_project"})
        else:
            # Check for version differences
            global_ver = skill.get("version", "0.0.0")
            project_ver = project_skills[name].get("version", "0.0.0")
            if global_ver != project_ver:
                results["conflicts"].append({
                    "name": name,
                    "global_version": global_ver,
                    "project_version": project_ver,
                })
    
    return results


def validate_skills() -> Dict[str, Any]:
    """Validate all skills have required fields."""
    dirs = get_skills_dirs()
    all_skills = {}
    all_skills.update(scan_skills_dir(dirs["global"]))
    all_skills.update(scan_skills_dir(dirs["project"]))
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "total": len(all_skills),
        "valid": [],
        "invalid": [],
        "warnings": [],
    }
    
    required_fields = ["name", "description", "trigger", "version"]
    
    for name, skill in all_skills.items():
        missing = [f for f in required_fields if f not in skill or not skill[f]]
        if missing:
            results["invalid"].append({"name": name, "missing": missing, "path": skill.get("path", "unknown")})
        else:
            results["valid"].append(name)
            # Check for common issues
            if len(skill.get("description", "")) < 20:
                results["warnings"].append({"name": name, "warning": "Description very short"})
            if skill.get("trigger", "").lower() == "use when":
                results["warnings"].append({"name": name, "warning": "Trigger template not customized"})
    
    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Skill Sync Manager")
    parser.add_argument("--sync", action="store_true", help="Sync skills from global to project")
    parser.add_argument("--validate", action="store_true", help="Validate all skills")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--list", action="store_true", help="List all skills")
    args = parser.parse_args()
    
    # Default action: sync (for cron compatibility)
    if not any([args.sync, args.validate, args.list]):
        args.sync = True
    
    if args.sync:
        results = sync_skills(dry_run=args.dry_run)
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 0 if not results["errors"] else 1
    
    if args.validate:
        results = validate_skills()
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 0 if not results["invalid"] else 1
    
    if args.list:
        dirs = get_skills_dirs()
        global_skills = scan_skills_dir(dirs["global"])
        project_skills = scan_skills_dir(dirs["project"])
        
        print("=== Global Skills ===")
        for name, skill in sorted(global_skills.items()):
            print(f"  {name}: {skill.get('description', 'no description')} (v{skill.get('version', '?')})")
        
        print("\n=== Project Skills ===")
        for name, skill in sorted(project_skills.items()):
            print(f"  {name}: {skill.get('description', 'no description')} (v{skill.get('version', '?')})")
        return 0
    
    # Default: sync
    results = sync_skills(dry_run=args.dry_run)
    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0 if not results["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())