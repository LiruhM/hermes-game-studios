#!/usr/bin/env python3
"""
Ops Infrastructure Setup Script
Installs and validates the complete ops infrastructure.
"""

import json
import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, Any


def run_command(cmd: list, cwd: Path = None, capture: bool = True) -> Dict[str, Any]:
    """Run a command and return result."""
    try:
        result = subprocess.run(cmd, capture_output=capture, text=True, timeout=60, cwd=cwd)
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout if capture else "",
            "stderr": result.stderr if capture else "",
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timeout", "returncode": -1, "stdout": "", "stderr": ""}
    except Exception as e:
        return {"success": False, "error": str(e), "returncode": -1, "stdout": "", "stderr": ""}


def check_prerequisites() -> Dict[str, Any]:
    """Check if all prerequisites are installed."""
    checks = {}
    
    # Python
    result = run_command(["python", "--version"])
    checks["python"] = {"installed": result["success"], "version": result["stdout"].strip() if result["success"] else result.get("error")}
    
    # Docker
    result = run_command(["docker", "--version"])
    checks["docker"] = {"installed": result["success"], "version": result["stdout"].strip() if result["success"] else result.get("error")}
    
    # Hermes CLI
    result = run_command(["hermes", "--version"])
    checks["hermes"] = {"installed": result["success"], "version": result["stdout"].strip() if result["success"] else result.get("error")}
    
    # Required Python packages
    for pkg in ["requests", "yaml", "watchdog"]:
        try:
            __import__(pkg)
            checks[f"python-{pkg}"] = {"installed": True}
        except ImportError:
            checks[f"python-{pkg}"] = {"installed": False}
    
    all_ok = all(c.get("installed", False) for c in checks.values())
    return {"all_ok": all_ok, "checks": checks}


def install_cron_jobs() -> Dict[str, Any]:
    """Install all cron jobs via cron_manager."""
    project_dir = Path.cwd()
    result = run_command(["python", "scripts/cron_manager.py", "--install"], cwd=project_dir)
    return {
        "success": result["success"],
        "output": result["stdout"],
        "error": result["stderr"],
    }


def validate_cron_jobs() -> Dict[str, Any]:
    """Validate cron jobs are installed."""
    project_dir = Path.cwd()
    result = run_command(["python", "scripts/cron_manager.py", "--validate"], cwd=project_dir)
    try:
        return json.loads(result["stdout"])
    except:
        return {"valid": False, "error": "Failed to parse validation output", "raw": result["stdout"]}


def start_ai_gateway() -> Dict[str, Any]:
    """Start the AI Gateway via Docker Compose."""
    gateway_dir = Path.cwd() / ".hermes" / "ai-gateway"
    if not gateway_dir.exists():
        return {"success": False, "error": "Gateway directory not found"}
    
    # Check if docker-compose exists
    compose_file = gateway_dir / "docker-compose.yaml"
    if not compose_file.exists():
        return {"success": False, "error": "docker-compose.yaml not found"}
    
    # Check for .env file with API keys
    env_file = gateway_dir / ".env"
    if not env_file.exists():
        # Create template
        env_template = """# Hermes AI Gateway Environment Variables
# Copy to .env and fill in your keys

GROQ_API_KEY=your_groq_key_here
NVIDIA_API_KEY=your_nvidia_key_here
"""
        env_file.write_text(env_template)
        return {"success": False, "error": f"Created template .env at {env_file}, please fill in API keys"}
    
    result = run_command(["docker-compose", "up", "-d"], cwd=gateway_dir)
    return {
        "success": result["success"],
        "output": result["stdout"],
        "error": result["stderr"],
    }


def check_ai_gateway_health() -> Dict[str, Any]:
    """Check AI Gateway health."""
    import requests
    try:
        resp = requests.get("http://127.0.0.1:20128/health", timeout=5)
        if resp.status_code == 200:
            return {"healthy": True, "data": resp.json()}
        return {"healthy": False, "status_code": resp.status_code}
    except Exception as e:
        return {"healthy": False, "error": str(e)}


def run_health_checks() -> Dict[str, Any]:
    """Run comprehensive health checks."""
    project_dir = Path.cwd()
    result = run_command(["python", "scripts/health_check.py", "--once", "--json"], cwd=project_dir)
    try:
        return json.loads(result["stdout"])
    except:
        return {"error": "Failed to parse health check output", "raw": result["stdout"]}


def test_ntfy() -> Dict[str, Any]:
    """Test ntfy connectivity."""
    project_dir = Path.cwd()
    result = run_command(["python", "scripts/ntfy_alert.py", "--title", "Test", "--message", "Ops infra test", "--priority", "low"], cwd=project_dir)
    return {"success": result["success"], "output": result["stdout"], "error": result["stderr"]}


def test_session_checkpoint() -> Dict[str, Any]:
    """Test session checkpoint save/restore."""
    project_dir = Path.cwd()
    result = run_command(["python", "scripts/session_checkpoint.py", "--save"], cwd=project_dir)
    return {"success": result["success"], "output": result["stdout"], "error": result["stderr"]}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Ops Infrastructure Setup")
    parser.add_argument("--check", action="store_true", help="Check prerequisites only")
    parser.add_argument("--install-cron", action="store_true", help="Install cron jobs")
    parser.add_argument("--start-gateway", action="store_true", help="Start AI Gateway")
    parser.add_argument("--validate", action="store_true", help="Run full validation")
    parser.add_argument("--test-all", action="store_true", help="Run all tests")
    args = parser.parse_args()
    
    results = {
        "timestamp": __import__("datetime").datetime.now().isoformat(),
        "steps": {},
    }
    
    print("=== Ops Infrastructure Setup ===\n")
    
    # Prerequisites
    print("1. Checking prerequisites...")
    prereq = check_prerequisites()
    results["steps"]["prerequisites"] = prereq
    for name, check in prereq["checks"].items():
        status = "OK" if check.get("installed") else "MISSING"
        version = check.get("version", "")
        print(f"  [{status}] {name} {version}")
    if not prereq["all_ok"]:
        print("  Some prerequisites missing!")
    
    if args.check:
        print(json.dumps(results, indent=2))
        return 0 if prereq["all_ok"] else 1
    
    # Install cron jobs
    if args.install_cron or args.test_all or args.validate:
        print("\n2. Installing cron jobs...")
        cron_install = install_cron_jobs()
        results["steps"]["cron_install"] = cron_install
        print(f"  Success: {cron_install['success']}")
        if not cron_install["success"]:
            print(f"  Error: {cron_install.get('error')}")
    
    # Validate cron jobs
    if args.validate or args.test_all:
        print("\n3. Validating cron jobs...")
        cron_valid = validate_cron_jobs()
        results["steps"]["cron_validate"] = cron_valid
        print(f"  Valid: {cron_valid.get('valid')}")
        if not cron_valid.get("valid"):
            print(f"  Missing: {cron_valid.get('missing')}")
    
    # Start AI Gateway
    if args.start_gateway or args.test_all:
        print("\n4. Starting AI Gateway...")
        gateway_start = start_ai_gateway()
        results["steps"]["gateway_start"] = gateway_start
        print(f"  Success: {gateway_start['success']}")
        if not gateway_start["success"]:
            print(f"  Error: {gateway_start.get('error')}")
    
    # Check AI Gateway health
    if args.test_all:
        print("\n5. Checking AI Gateway health...")
        gateway_health = check_ai_gateway_health()
        results["steps"]["gateway_health"] = gateway_health
        print(f"  Healthy: {gateway_health.get('healthy')}")
    
    # Run health checks
    if args.test_all or args.validate:
        print("\n6. Running health checks...")
        health = run_health_checks()
        results["steps"]["health_check"] = health
        overall = health.get("overall", "unknown")
        print(f"  Overall: {overall}")
        print(f"  Healthy: {health.get('summary', {}).get('healthy', 0)}, Degraded: {health.get('summary', {}).get('degraded', 0)}, Down: {health.get('summary', {}).get('down', 0)}")
    
    # Test ntfy
    if args.test_all:
        print("\n7. Testing ntfy...")
        ntfy_test = test_ntfy()
        results["steps"]["ntfy_test"] = ntfy_test
        print(f"  Success: {ntfy_test['success']}")
    
    # Test session checkpoint
    if args.test_all:
        print("\n8. Testing session checkpoint...")
        checkpoint_test = test_session_checkpoint()
        results["steps"]["checkpoint_test"] = checkpoint_test
        print(f"  Success: {checkpoint_test['success']}")
    
    print("\n=== Setup Complete ===")
    print(json.dumps(results, indent=2))
    
    # Determine overall success
    critical_steps = ["prerequisites", "cron_install", "cron_validate"]
    all_critical_ok = all(results["steps"].get(s, {}).get("all_ok", results["steps"].get(s, {}).get("success", results["steps"].get(s, {}).get("valid", False))) for s in critical_steps if s in results["steps"])
    
    return 0 if all_critical_ok else 1


if __name__ == "__main__":
    sys.exit(main())