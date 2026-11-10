#!/usr/bin/env python3
"""
Session Checkpoint Script
Saves current session state to disk for persistence across restarts.
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional


def get_active_md_path() -> Path:
    """Get the path to the active.md file."""
    localappdata = os.environ.get("LOCALAPPDATA", "")
    if not localappdata:
        raise RuntimeError("LOCALAPPDATA not set")
    return Path(localappdata) / "hermes" / "memory" / "active.md"


def get_session_state_dir() -> Path:
    """Get the session state directory."""
    localappdata = os.environ.get("LOCALAPPDATA", "")
    if not localappdata:
        raise RuntimeError("LOCALAPPDATA not set")
    return Path(localappdata) / "hermes" / "memory" / "session-state"


def read_active_md() -> str:
    """Read the active.md content."""
    path = get_active_md_path()
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def write_checkpoint(state: Dict[str, Any]) -> Path:
    """Write a checkpoint file."""
    session_dir = get_session_state_dir()
    session_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    checkpoint_file = session_dir / f"checkpoint-{timestamp}.json"
    
    state["checkpoint_time"] = datetime.now().isoformat()
    state["checkpoint_file"] = str(checkpoint_file)
    
    checkpoint_file.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    
    # Also write latest (copy instead of symlink for Windows compatibility)
    latest = session_dir / "latest.json"
    try:
        latest.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    
    return checkpoint_file


def load_latest_checkpoint() -> Optional[Dict[str, Any]]:
    """Load the latest checkpoint if it exists."""
    session_dir = get_session_state_dir()
    latest = session_dir / "latest.json"
    if latest.exists():
        try:
            return json.loads(latest.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Error loading checkpoint: {e}", file=sys.stderr)
    return None


def create_session_checkpoint() -> Dict[str, Any]:
    """Create a complete session checkpoint."""
    active_content = read_active_md()
    
    checkpoint = {
        "version": "1.0",
        "active_md": active_content,
        "active_md_path": str(get_active_md_path()),
        "environment": {
            "LOCALAPPDATA": os.environ.get("LOCALAPPDATA", ""),
            "USERPROFILE": os.environ.get("USERPROFILE", ""),
        },
        "hermes_config": get_hermes_config_snapshot(),
    }
    
    return checkpoint


def get_hermes_config_snapshot() -> Dict[str, Any]:
    """Get a snapshot of relevant Hermes config."""
    config = {}
    localappdata = os.environ.get("LOCALAPPDATA", "")
    config_path = Path(localappdata) / "hermes" / "config.yaml"
    if config_path.exists():
        try:
            import yaml
            config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except Exception:
            pass
    return config


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Session Checkpoint Manager")
    parser.add_argument("--save", action="store_true", help="Save current session checkpoint")
    parser.add_argument("--restore", action="store_true", help="Restore latest checkpoint")
    parser.add_argument("--list", action="store_true", help="List available checkpoints")
    parser.add_argument("--show-latest", action="store_true", help="Show latest checkpoint info")
    args = parser.parse_args()
    
    # Default action: save (for cron compatibility)
    if not any([args.save, args.restore, args.list, args.show_latest]):
        args.save = True
    
    if args.save:
        checkpoint = create_session_checkpoint()
        path = write_checkpoint(checkpoint)
        print(f"Checkpoint saved: {path}")
        return 0
    
    if args.restore:
        checkpoint = load_latest_checkpoint()
        if checkpoint:
            active_path = get_active_md_path()
            active_path.parent.mkdir(parents=True, exist_ok=True)
            active_path.write_text(checkpoint.get("active_md", ""), encoding="utf-8")
            print(f"Restored checkpoint from {checkpoint.get('checkpoint_time', 'unknown')}")
            return 0
        else:
            print("No checkpoint found", file=sys.stderr)
            return 1
    
    if args.list:
        session_dir = get_session_state_dir()
        if session_dir.exists():
            for f in sorted(session_dir.glob("checkpoint-*.json"), reverse=True):
                print(f.name)
        return 0
    
    if args.show_latest:
        checkpoint = load_latest_checkpoint()
        if checkpoint:
            print(json.dumps({
                "checkpoint_time": checkpoint.get("checkpoint_time"),
                "checkpoint_file": checkpoint.get("checkpoint_file"),
                "active_md_length": len(checkpoint.get("active_md", "")),
            }, indent=2))
            return 0
        print("No checkpoint found")
        return 1
    
    # Default: save
    checkpoint = create_session_checkpoint()
    path = write_checkpoint(checkpoint)
    print(f"Checkpoint saved: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())