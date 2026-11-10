#!/usr/bin/env python3
"""
Health Check Script
Comprehensive health checks for all Hermes ecosystem services.
"""

import json
import os
import sys
import subprocess
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional


def check_service(name: str, url: str, method: str = "GET", json_data: dict = None, timeout: int = 3) -> Dict[str, Any]:
    """Check a single service health endpoint."""
    import requests
    start = time.time()
    try:
        if method == "GET":
            resp = requests.get(url, timeout=timeout)
        else:
            resp = requests.post(url, json=json_data, timeout=timeout)
        latency_ms = (time.time() - start) * 1000
        
        if resp.status_code == 200:
            try:
                data = resp.json()
                return {
                    "service": name,
                    "url": url,
                    "status": "healthy",
                    "latency_ms": round(latency_ms, 1),
                    "details": data,
                    "timestamp": datetime.now().isoformat(),
                }
            except:
                return {
                    "service": name,
                    "url": url,
                    "status": "healthy",
                    "latency_ms": round(latency_ms, 1),
                    "details": {"raw": resp.text[:200]},
                    "timestamp": datetime.now().isoformat(),
                }
        else:
            return {
                "service": name,
                "url": url,
                "status": "down",
                "latency_ms": round(latency_ms, 1),
                "error": f"HTTP {resp.status_code}",
                "timestamp": datetime.now().isoformat(),
            }
    except requests.ConnectionError:
        return {
            "service": name,
            "url": url,
            "status": "down",
            "latency_ms": round((time.time() - start) * 1000, 1),
            "error": "Connection refused",
            "timestamp": datetime.now().isoformat(),
        }
    except requests.Timeout:
        return {
            "service": name,
            "url": url,
            "status": "down",
            "latency_ms": round((time.time() - start) * 1000, 1),
            "error": "Timeout",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {
            "service": name,
            "url": url,
            "status": "down",
            "latency_ms": round((time.time() - start) * 1000, 1),
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


def run_all_checks() -> Dict[str, Any]:
    """Run all health checks."""
    services = [
        ("headroom-proxy", "http://127.0.0.1:8787/health"),
        ("mempalace-mcp", "http://127.0.0.1:8765/mcp", "POST", {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}),
        ("system-tray", "http://127.0.0.1:36787/status"),
        ("watchdog", "http://127.0.0.1:36788/health"),
        ("ai-gateway", "http://127.0.0.1:20128/health"),
        ("ai-gateway-dashboard", "http://127.0.0.1:20129/dashboard"),
        ("memory-substrate", "http://127.0.0.1:8766/health"),
    ]
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "checks": [],
        "summary": {"healthy": 0, "degraded": 0, "down": 0, "total": 0},
    }
    
    for svc in services:
        if len(svc) == 2:
            name, url = svc
            result = check_service(name, url)
        elif len(svc) == 3:
            name, url, method = svc
            result = check_service(name, url, method=method)
        else:
            name, url, method, json_data = svc
            result = check_service(name, url, method=method, json_data=json_data)
        
        results["checks"].append(result)
        
        if result["status"] == "healthy":
            # Check for degraded signals in details
            details = result.get("details", {})
            if isinstance(details, dict):
                checks = details.get("checks", {})
                kompress = checks.get("kompress", {})
                if not kompress.get("ready", True):
                    result["status"] = "degraded"
                    results["summary"]["degraded"] += 1
                else:
                    results["summary"]["healthy"] += 1
            else:
                results["summary"]["healthy"] += 1
        else:
            results["summary"]["down"] += 1
        results["summary"]["total"] += 1
    
    # Overall status
    if results["summary"]["down"] > 0:
        results["overall"] = "down"
    elif results["summary"]["degraded"] > 0:
        results["overall"] = "degraded"
    else:
        results["overall"] = "healthy"
    
    return results


def check_cron_jobs() -> Dict[str, Any]:
    """Check Hermes cron jobs status."""
    try:
        result = subprocess.run(["hermes", "cron", "list"], capture_output=True, text=True, timeout=10, cwd=Path(os.environ.get("LOCALAPPDATA", "")) / "hermes")
        return {
            "service": "cron-jobs",
            "status": "healthy" if result.returncode == 0 else "down",
            "output": result.stdout,
            "error": result.stderr if result.returncode != 0 else None,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {
            "service": "cron-jobs",
            "status": "down",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


def check_session_persistence() -> Dict[str, Any]:
    """Check session persistence (active.md freshness)."""
    try:
        active_md = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / "memory" / "active.md"
        if active_md.exists():
            mtime = active_md.stat().st_mtime
            age = time.time() - mtime
            return {
                "service": "session-persistence",
                "status": "healthy" if age < 300 else "degraded",
                "age_seconds": round(age, 1),
                "path": str(active_md),
                "timestamp": datetime.now().isoformat(),
            }
        return {
            "service": "session-persistence",
            "status": "down",
            "error": "active.md not found",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {
            "service": "session-persistence",
            "status": "down",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


def check_disk_space() -> Dict[str, Any]:
    """Check disk space for critical paths."""
    try:
        import shutil
        localappdata = Path(os.environ.get("LOCALAPPDATA", ""))
        usage = shutil.disk_usage(localappdata)
        free_gb = usage.free / (1024**3)
        total_gb = usage.total / (1024**3)
        pct_free = (usage.free / usage.total) * 100
        
        return {
            "service": "disk-space",
            "status": "healthy" if pct_free > 10 else ("degraded" if pct_free > 5 else "down"),
            "free_gb": round(free_gb, 1),
            "total_gb": round(total_gb, 1),
            "percent_free": round(pct_free, 1),
            "path": str(localappdata),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {
            "service": "disk-space",
            "status": "down",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


def check_ntfy_connectivity() -> Dict[str, Any]:
    """Check ntfy.sh connectivity."""
    import requests
    try:
        resp = requests.get("https://ntfy.sh/hermes-mathe-r8gemiyxxm", timeout=5)
        return {
            "service": "ntfy-connectivity",
            "status": "healthy" if resp.status_code == 200 else "down",
            "http_status": resp.status_code,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {
            "service": "ntfy-connectivity",
            "status": "down",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Hermes Health Check")
    parser.add_argument("--once", action="store_true", help="Run checks once and exit")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--monitor", action="store_true", help="Run continuously (every 30s)")
    parser.add_argument("--interval", type=int, default=30, help="Monitor interval in seconds")
    args = parser.parse_args()
    
    # Default action: once (for cron compatibility)
    if not any([args.once, args.monitor]):
        args.once = True
    
    def run_checks():
        all_results = run_all_checks()
        all_results["checks"].append(check_cron_jobs())
        all_results["checks"].append(check_session_persistence())
        all_results["checks"].append(check_disk_space())
        all_results["checks"].append(check_ntfy_connectivity())
        
        # Recalculate summary
        summary = {"healthy": 0, "degraded": 0, "down": 0, "total": 0}
        for check in all_results["checks"]:
            summary["total"] += 1
            summary[check["status"]] = summary.get(check["status"], 0) + 1
        all_results["summary"] = summary
        
        if summary["down"] > 0:
            all_results["overall"] = "down"
        elif summary["degraded"] > 0:
            all_results["overall"] = "degraded"
        else:
            all_results["overall"] = "healthy"
        
        return all_results
    
    if args.monitor:
        print(f"Starting health monitor (interval: {args.interval}s)...")
        try:
            while True:
                results = run_checks()
                if args.json:
                    print(json.dumps(results, indent=2))
                else:
                    print(f"\n=== Health Check {results['timestamp']} ===")
                    print(f"Overall: {results['overall'].upper()}")
                    print(f"Healthy: {results['summary']['healthy']}, Degraded: {results['summary']['degraded']}, Down: {results['summary']['down']}")
                    for check in results["checks"]:
                        status_icon = "OK" if check["status"] == "healthy" else ("WARN" if check["status"] == "degraded" else "DOWN")
                        latency = f" ({check.get('latency_ms', 0):.1f}ms)" if "latency_ms" in check else ""
                        print(f"  [{status_icon}] {check['service']}{latency}")
                        if check["status"] != "healthy" and "error" in check:
                            print(f"      Error: {check['error']}")
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nMonitor stopped")
        return 0
    
    results = run_checks()
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(f"=== Health Check {results['timestamp']} ===")
        print(f"Overall: {results['overall'].upper()}")
        print(f"Healthy: {results['summary']['healthy']}, Degraded: {results['summary']['degraded']}, Down: {results['summary']['down']}")
        for check in results["checks"]:
            status_icon = "OK" if check["status"] == "healthy" else ("WARN" if check["status"] == "degraded" else "DOWN")
            latency = f" ({check.get('latency_ms', 0):.1f}ms)" if "latency_ms" in check else ""
            print(f"  [{status_icon}] {check['service']}{latency}")
            if check["status"] != "healthy" and "error" in check:
                print(f"      Error: {check['error']}")
    
    # Exit code based on overall status
    if results["overall"] == "down":
        return 2
    elif results["overall"] == "degraded":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())