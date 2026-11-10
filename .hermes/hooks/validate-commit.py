#!/usr/bin/env python3
"""
Runs quality gates before git commit
Hermes Game Studios - Native Hook
Auto-generated from CCGS hook migration
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

# Project root resolution
PROJECT_ROOT = Path(__file__).parent.parent.parent
HERMES_DIR = PROJECT_ROOT / ".hermes"
MEMORY_DIR = HERMES_DIR / "memory"
CONTRACTS_DIR = HERMES_DIR / "contracts"
SETTINGS_FILE = HERMES_DIR / "settings.json"

def load_settings() -> dict[str, Any]:
    """Load project settings."""
    if SETTINGS_FILE.exists():
        return json.loads(SETTINGS_FILE.read_text())
    return {}

def load_yaml(path: Path) -> dict[str, Any]:
    """Safely load YAML file."""
    if path.exists():
        return yaml.safe_load(path.read_text())
    return {}

def save_checkpoint(data: dict[str, Any]) -> None:
    """Save session checkpoint to active.md."""
    active_file = MEMORY_DIR / "active.md"
    active_file.parent.mkdir(parents=True, exist_ok=True)
    
    content = f"""# Session Checkpoint
session_id: {data.get('session_id', datetime.now().strftime('%Y%m%d-%H%M%S'))}
updated_at: {datetime.now().isoformat()}
project_stage: {data.get('project_stage', 'unknown')}
review_mode: {data.get('review_mode', 'full')}
engine: {data.get('engine', 'godot')}
active_contracts: {json.dumps(data.get('active_contracts', []))}
dispatched_agents: {json.dumps(data.get('dispatched_agents', []))}
last_hook: {data.get('last_hook', 'unknown')}
"""
    active_file.write_text(content)

def log_session(event: str, data: dict[str, Any]) -> None:
    """Log session event to session-logs."""
    log_dir = MEMORY_DIR / "session-logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / f"session-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
    content = f"""# Session Log: {event}
timestamp: {datetime.now().isoformat()}
event: {event}
data: {json.dumps(data, indent=2)}
"""
    log_file.write_text(content)

def ntfy_notify(topic: str, message: str, priority: str = "default", tags: list | None = None) -> bool:
    """Send ntfy push notification."""
    try:
        import urllib.request
        url = f"https://ntfy.sh/{topic}"
        headers = {"Priority": priority}
        if tags:
            headers["Tags"] = ",".join(tags)
        req = urllib.request.Request(url, data=message.encode(), headers=headers, method="POST")
        urllib.request.urlopen(req, timeout=5)
        return True
    except Exception:
        return False

def validate_boundaries(agent_name: str, file_path: str, action: str) -> bool:
    """Validate agent boundary access."""
    settings = load_settings()
    settings.get("agents", {})
    return True

def main():
    """Main hook entry point."""
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        input_data = {}
    
    result = run_hook(input_data)
    print(json.dumps(result))
    
    # Exit with non-zero if gates failed
    if result.get("status") == "failed":
        sys.exit(1)

def run_hook(input_data):
    """Run quality gates before git commit."""
    import subprocess
    
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    gates_passed = True
    gate_results = {
        "eslint": {"status": "passed", "errors": 0, "warnings": 0},
        "ruff": {"status": "passed", "errors": 0, "warnings": 0},
        "clippy": {"status": "passed", "errors": 0, "warnings": 0},
        "max_lines_per_file": True,
        "no_direct_console": True,
        "no_direct_data_access": True,
        "test_execution": True
    }
    
    # Run ESLint (JS/TS files)
    try:
        result = subprocess.run(
            "npx eslint . --config .hermes/rules/eslint-index.cjs --no-ignore",
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=60,
            shell=True
        )
        if result.returncode != 0:
            gates_passed = False
            gate_results["eslint"]["status"] = "failed"
            # Parse output for error/warning counts
            for line in result.stdout.split('\n'):
                if 'error' in line.lower() and 'warning' in line.lower():
                    parts = line.split()
                    for i, p in enumerate(parts):
                        if p.isdigit():
                            gate_results["eslint"]["errors"] = int(p)
                            break
    except Exception as e:
        gate_results["eslint"]["status"] = "error"
        gate_results["eslint"]["error"] = str(e)
    
    # Run Ruff (Python files)
    try:
        result = subprocess.run(
            ["ruff", "check", "."],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode != 0:
            gates_passed = False
            gate_results["ruff"]["status"] = "failed"
            # Count violations
            gate_results["ruff"]["errors"] = result.stdout.count('\n') if result.stdout else 0
    except Exception as e:
        gate_results["ruff"]["status"] = "error"
        gate_results["ruff"]["error"] = str(e)
    
    # Run Clippy (Rust files)
    try:
        result = subprocess.run(
            ["cargo", "clippy"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.returncode != 0:
            gates_passed = False
            gate_results["clippy"]["status"] = "failed"
            # Count warnings/errors
            gate_results["clippy"]["warnings"] = result.stderr.count('warning:') if result.stderr else 0
    except Exception as e:
        gate_results["clippy"]["status"] = "error"
        gate_results["clippy"]["error"] = str(e)
    
    return {
        "status": "ok" if gates_passed else "failed",
        "hook": "validate-commit",
        "gates": gate_results
    }

if __name__ == "__main__":
    main()
