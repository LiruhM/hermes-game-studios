#!/usr/bin/env python3
"""
Cron Jobs Manager for Hermes Game Studios
Installs and manages all scheduled ops jobs.
"""

import json
import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, List, Any


# Cron job definitions
# Scripts are located in the Hermes scripts directory (~/.hermes/scripts/)
# Default actions are used (no args needed for cron - scripts have defaults)
import os
HERMES_SCRIPTS_DIR = os.path.join(os.environ.get("LOCALAPPDATA", ""), "hermes", "scripts")

CRON_JOBS = [
    {
        "name": "session-checkpoint",
        "schedule": "*/15 * * * *",  # Every 15 minutes
        "script": "session_checkpoint.py",
        "args": "",
        "description": "Save session checkpoint every 15 minutes",
    },
    {
        "name": "skill-sync",
        "schedule": "0 * * * *",  # Hourly
        "script": "skill_sync.py",
        "args": "",
        "description": "Sync skills from global to project hourly",
    },
    {
        "name": "vault-sync",
        "schedule": "0 */6 * * *",  # Every 6 hours
        "script": "vault_sync.py",
        "args": "",
        "description": "Scan vault every 6 hours",
    },
    {
        "name": "health-check",
        "schedule": "*/5 * * * *",  # Every 5 minutes
        "script": "health_check.py",
        "args": "",
        "description": "Comprehensive health check every 5 minutes",
    },
    {
        "name": "resilience-validation",
        "schedule": "*/5 * * * *",  # Every 5 minutes
        "script": "watchdog.py",
        "args": "",
        "description": "Watchdog resilience validation every 5 minutes",
    },
    {
        "name": "daily-backup",
        "schedule": "0 3 * * *",  # 3 AM daily
        "script": "backup.py",
        "args": "",
        "description": "Daily backup at 3 AM",
    },
    {
        "name": "weekly-token-audit",
        "schedule": "0 4 * * 0",  # 4 AM Sunday
        "script": "token_audit.py",
        "args": "",
        "description": "Weekly token usage audit",
    },
    {
        "name": "progress-watchdog",
        "schedule": "0 * * * *",  # Hourly
        "script": "progress_watchdog.py",
        "args": "",
        "description": "Hourly progress watchdog",
    },
]


def get_hermes_dir() -> Path:
    """Get the Hermes base directory."""
    localappdata = os.environ.get("LOCALAPPDATA", "")
    if not localappdata:
        raise RuntimeError("LOCALAPPDATA not set")
    return Path(localappdata) / "hermes"


def get_project_dir() -> Path:
    """Get the project directory."""
    return Path.cwd()


def install_cron_jobs() -> Dict[str, Any]:
    """Install all cron jobs via hermes cron."""
    hermes_dir = get_hermes_dir()
    project_dir = get_project_dir()
    
    results = {
        "installed": [],
        "failed": [],
        "skipped": [],
    }
    
    for job in CRON_JOBS:
        try:
            # Use hermes cron create with --script and --no-agent
            script_name = job["script"]
            args = job.get("args", "")
            cmd = [
                "hermes", "cron", "create",
                "--name", job["name"],
                "--script", script_name,
                "--no-agent",
                "--workdir", str(project_dir),
            ]
            if args:
                cmd.append(args)
            cmd.append(job["schedule"])
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=hermes_dir)
            
            if result.returncode == 0:
                results["installed"].append(job["name"])
                print(f"Installed: {job['name']} ({job['schedule']})")
            else:
                # Check if already exists
                if "already exists" in result.stderr.lower() or "duplicate" in result.stderr.lower():
                    results["skipped"].append(job["name"])
                    print(f"Skipped (exists): {job['name']}")
                else:
                    results["failed"].append({"name": job["name"], "error": result.stderr})
                    print(f"Failed: {job['name']} - {result.stderr}")
                   
        except Exception as e:
            results["failed"].append({"name": job["name"], "error": str(e)})
            print(f"Error installing {job['name']}: {e}")
   
    return results


def list_cron_jobs() -> Dict[str, Any]:
    """List all installed cron jobs."""
    hermes_dir = get_hermes_dir()
    
    try:
        result = subprocess.run(["hermes", "cron", "list"], capture_output=True, text=True, timeout=10, cwd=hermes_dir)
        if result.returncode == 0:
            return {"jobs": result.stdout, "error": None}
        return {"jobs": None, "error": result.stderr}
    except Exception as e:
        return {"jobs": None, "error": str(e)}


def remove_cron_jobs(job_names: List[str] = None) -> Dict[str, Any]:
    """Remove cron jobs."""
    hermes_dir = get_hermes_dir()
    
    if job_names is None:
        job_names = [job["name"] for job in CRON_JOBS]
    
    results = {"removed": [], "failed": []}
    
    for name in job_names:
        try:
            result = subprocess.run(["hermes", "cron", "remove", name], capture_output=True, text=True, timeout=10, cwd=hermes_dir)
            if result.returncode == 0:
                results["removed"].append(name)
                print(f"Removed: {name}")
            else:
                results["failed"].append({"name": name, "error": result.stderr})
                print(f"Failed to remove {name}: {result.stderr}")
        except Exception as e:
            results["failed"].append({"name": name, "error": str(e)})
            print(f"Error removing {name}: {e}")
    
    return results


def validate_cron_jobs() -> Dict[str, Any]:
    """Validate all cron jobs are installed and healthy."""
    hermes_dir = get_hermes_dir()
    
    try:
        result = subprocess.run(["hermes", "cron", "list"], capture_output=True, text=True, timeout=10, cwd=hermes_dir)
        if result.returncode != 0:
            return {"valid": False, "error": "Failed to list cron jobs", "output": result.stderr}
        
        output = result.stdout
        installed_names = []
        for line in output.splitlines():
            # Parse cron list output
            if line.strip() and not line.startswith("==="):
                parts = line.split()
                if parts:
                    installed_names.append(parts[0])
        
        expected_names = {job["name"] for job in CRON_JOBS}
        missing = expected_names - set(installed_names)
        extra = set(installed_names) - expected_names
        
        return {
            "valid": len(missing) == 0,
            "installed": installed_names,
            "expected": list(expected_names),
            "missing": list(missing),
            "extra": list(extra),
        }
    except Exception as e:
        return {"valid": False, "error": str(e)}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Cron Jobs Manager")
    parser.add_argument("--install", action="store_true", help="Install all cron jobs")
    parser.add_argument("--list", action="store_true", help="List installed cron jobs")
    parser.add_argument("--remove", action="store_true", help="Remove all managed cron jobs")
    parser.add_argument("--validate", action="store_true", help="Validate cron jobs")
    parser.add_argument("--job", type=str, help="Specific job name for remove")
    args = parser.parse_args()
    
    if args.install:
        results = install_cron_jobs()
        print(json.dumps(results, indent=2))
        return 0 if not results["failed"] else 1
    
    if args.list:
        results = list_cron_jobs()
        if results["error"]:
            print(f"Error: {results['error']}", file=sys.stderr)
            return 1
        print(results["jobs"])
        return 0
    
    if args.remove:
        jobs = [args.job] if args.job else None
        results = remove_cron_jobs(jobs)
        print(json.dumps(results, indent=2))
        return 0 if not results["failed"] else 1
    
    if args.validate:
        results = validate_cron_jobs()
        print(json.dumps(results, indent=2))
        return 0 if results["valid"] else 1
    
    # Default: install
    results = install_cron_jobs()
    print(json.dumps(results, indent=2))
    return 0 if not results["failed"] else 1


if __name__ == "__main__":
    sys.exit(main())