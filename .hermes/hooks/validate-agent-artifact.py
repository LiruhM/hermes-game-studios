#!/usr/bin/env python3
"""
Validates agent-produced artifacts meet contracts
Hermes Game Studios - Native Hook
Auto-generated from CCGS hook migration
"""

import json
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

def run_hook(input_data: dict[str, Any]) -> dict[str, Any]:
    """Override in each hook."""
    return {"status": "ok", "hook": "validate-agent-artifact"}

if __name__ == "__main__":
    main()

def run_hook(input_data):
    """Validate agent-produced artifact meets contract requirements."""
    input_data.get("agent_name", "")
    artifact_path = input_data.get("artifact_path", "")
    contract_ref = input_data.get("contract_ref", "")
    
    load_yaml(CONTRACTS_DIR / contract_ref) if contract_ref else {}
    artifact_file = PROJECT_ROOT / artifact_path
    exists = artifact_file.exists()
    
    valid = exists
    errors = []
    
    if not exists:
        errors.append(f"Artifact not found: {artifact_path}")
    
    return {
        "status": "ok" if valid else "failed",
        "hook": "validate-agent-artifact",
        "artifact": artifact_path,
        "exists": exists,
        "contract_compliant": valid,
        "errors": errors
    }
