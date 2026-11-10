#!/usr/bin/env python3
"""
Backup Script
Creates backups of critical Hermes data.
"""

import json
import os
import sys
import shutil
import tarfile
from pathlib import Path
from datetime import datetime
from typing import Dict, Any


def get_backup_dir() -> Path:
    """Get the backup directory."""
    localappdata = os.environ.get("LOCALAPPDATA", "")
    if not localappdata:
        raise RuntimeError("LOCALAPPDATA not set")
    backup_dir = Path(localappdata) / "hermes" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def get_critical_paths() -> Dict[str, Path]:
    """Get paths to backup."""
    localappdata = os.environ.get("LOCALAPPDATA", "")
    userprofile = os.environ.get("USERPROFILE", "")
    
    paths = {
        "hermes_config": Path(localappdata) / "hermes" / "config.yaml",
        "hermes_memory": Path(localappdata) / "hermes" / "memory",
        "hermes_skills": Path(localappdata) / "hermes" / "skills",
        "hermes_logs": Path(localappdata) / "hermes" / "logs",
        "project_config": Path.cwd() / "project.yaml",
        "project_hermes": Path.cwd() / ".hermes",
    }
    
    if userprofile:
        paths["obsidian_vault"] = Path(userprofile) / "Hermes_Brain"
    
    # Filter existing paths
    return {k: v for k, v in paths.items() if v.exists()}


def create_backup(full: bool = False) -> Dict[str, Any]:
    """Create a backup archive."""
    backup_dir = get_backup_dir()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_name = f"hermes-backup-{'full' if full else 'incremental'}-{timestamp}.tar.gz"
    backup_path = backup_dir / backup_name
    
    paths = get_critical_paths()
    
    results = {
        "backup_file": str(backup_path),
        "timestamp": datetime.now().isoformat(),
        "type": "full" if full else "incremental",
        "included": [],
        "excluded": [],
        "size_bytes": 0,
        "size_mb": 0,
    }
    
    try:
        with tarfile.open(backup_path, "w:gz") as tar:
            for name, path in paths.items():
                if path.exists():
                    try:
                        tar.add(path, arcname=f"hermes-backup/{name}")
                        results["included"].append(name)
                        print(f"  Added: {name} ({path})")
                    except Exception as e:
                        results["excluded"].append({"name": name, "error": str(e)})
                        print(f"  Failed: {name} - {e}")
                else:
                    results["excluded"].append({"name": name, "error": "Path does not exist"})
                    print(f"  Missing: {name} ({path})")
        
        # Get backup size
        size = backup_path.stat().st_size
        results["size_bytes"] = size
        results["size_mb"] = round(size / (1024 * 1024), 2)
        
        # Cleanup old backups (keep last 7 daily, 4 weekly, 12 monthly)
        cleanup_old_backups(backup_dir)
        
        print(f"Backup created: {backup_path} ({results['size_mb']} MB)")
        return results
        
    except Exception as e:
        results["error"] = str(e)
        print(f"Backup failed: {e}", file=sys.stderr)
        return results


def cleanup_old_backups(backup_dir: Path):
    """Clean up old backups based on retention policy."""
    backups = sorted(backup_dir.glob("hermes-backup-*.tar.gz"), key=lambda p: p.stat().st_mtime, reverse=True)
    
    # Simple retention: keep last 30 backups
    for old_backup in backups[30:]:
        try:
            old_backup.unlink()
            print(f"Removed old backup: {old_backup.name}")
        except Exception as e:
            print(f"Failed to remove {old_backup.name}: {e}")


def restore_backup(backup_file: Path, target_dir: Path = None) -> Dict[str, Any]:
    """Restore from a backup file."""
    if target_dir is None:
        target_dir = Path.cwd()
    
    results = {
        "backup_file": str(backup_file),
        "restored_to": str(target_dir),
        "extracted": [],
        "errors": [],
    }
    
    try:
        with tarfile.open(backup_file, "r:gz") as tar:
            members = tar.getmembers()
            for member in members:
                try:
                    tar.extract(member, target_dir)
                    results["extracted"].append(member.name)
                except Exception as e:
                    results["errors"].append({"file": member.name, "error": str(e)})
        
        print(f"Restored {len(results['extracted'])} items from {backup_file}")
        return results
        
    except Exception as e:
        results["errors"].append({"general": str(e)})
        print(f"Restore failed: {e}", file=sys.stderr)
        return results


def list_backups() -> Dict[str, Any]:
    """List available backups."""
    backup_dir = get_backup_dir()
    backups = sorted(backup_dir.glob("hermes-backup-*.tar.gz"), key=lambda p: p.stat().st_mtime, reverse=True)
    
    results = {"backups": []}
    
    for backup in backups:
        stat = backup.stat()
        results["backups"].append({
            "name": backup.name,
            "path": str(backup),
            "size_bytes": stat.st_size,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        })
    
    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Backup Manager")
    parser.add_argument("--full", action="store_true", help="Full backup (default)")
    parser.add_argument("--incremental", action="store_true", help="Incremental backup")
    parser.add_argument("--list", action="store_true", help="List backups")
    parser.add_argument("--restore", type=str, help="Restore from backup file")
    parser.add_argument("--target", type=str, help="Target directory for restore")
    args = parser.parse_args()
    
    # Default action: full backup (for cron compatibility)
    if not any([args.full, args.incremental, args.list, args.restore]):
        args.full = True
    
    if args.list:
        results = list_backups()
        print(json.dumps(results, indent=2))
        return 0
    
    if args.restore:
        backup_file = Path(args.restore)
        target_dir = Path(args.target) if args.target else None
        results = restore_backup(backup_file, target_dir)
        print(json.dumps(results, indent=2))
        return 0 if not results["errors"] else 1
    
    # Default: full backup
    full = args.full or not args.incremental
    results = create_backup(full=full)
    print(json.dumps(results, indent=2))
    return 0 if "error" not in results else 1


if __name__ == "__main__":
    sys.exit(main())