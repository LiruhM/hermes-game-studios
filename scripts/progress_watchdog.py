#!/usr/bin/env python3
"""
Progress Watchdog
Monitors sprint/milestone progress and alerts on blockers.
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List


def get_sprint_dir() -> Path:
    """Get the sprint directory."""
    return Path.cwd() / "production" / "sprints"


def get_milestone_dir() -> Path:
    """Get the milestone directory."""
    return Path.cwd() / "production" / "milestones"


def load_active_sprint() -> Dict[str, Any]:
    """Load the active sprint status."""
    sprint_dir = get_sprint_dir()
    status_file = sprint_dir / "sprint-status.yaml"
    
    if status_file.exists():
        try:
            import yaml
            return yaml.safe_load(status_file.read_text(encoding="utf-8")) or {}
        except Exception:
            pass
    return {}


def load_milestones() -> List[Dict[str, Any]]:
    """Load all milestones."""
    milestone_dir = get_milestone_dir()
    milestones = []
    
    for md_file in milestone_dir.glob("milestone-*.md"):
        try:
            content = md_file.read_text(encoding="utf-8")
            # Extract basic info from markdown
            lines = content.splitlines()
            title = ""
            date = ""
            status = "planned"
            for line in lines:
                if line.startswith("# "):
                    title = line[2:].strip()
                elif "date:" in line.lower():
                    date = line.split(":", 1)[1].strip()
                elif "status:" in line.lower():
                    status = line.split(":", 1)[1].strip()
            
            milestones.append({
                "file": md_file.name,
                "title": title,
                "date": date,
                "status": status,
            })
        except Exception:
            continue
    
    return milestones


def check_sprint_health(sprint: Dict[str, Any]) -> Dict[str, Any]:
    """Check sprint for blockers and risks."""
    issues = []
    warnings = []
    
    stories = sprint.get("stories", [])
    total = len(stories)
    done = sum(1 for s in stories if s.get("status") == "done")
    in_progress = sum(1 for s in stories if s.get("status") == "in_progress")
    blocked = sum(1 for s in stories if s.get("status") == "blocked")
    todo = sum(1 for s in stories if s.get("status") in ("todo", "ready"))
    
    if blocked > 0:
        issues.append(f"{blocked} story(s) blocked")
    
    if total > 0:
        progress = done / total
        if progress < 0.3 and in_progress == 0:
            warnings.append("Low progress, no stories in progress")
        elif progress < 0.5 and in_progress > 3:
            warnings.append("Many stories in progress, risk of spillover")
    
    # Check sprint end date
    end_date_str = sprint.get("end_date", "")
    if end_date_str:
        try:
            end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
            days_left = (end_date - datetime.now()).days
            if days_left < 0:
                issues.append("Sprint end date passed")
            elif days_left <= 2 and progress < 0.8:
                warnings.append(f"Sprint ends in {days_left} days, only {progress:.0%} complete")
        except Exception:
            pass
    
    return {
        "total_stories": total,
        "done": done,
        "in_progress": in_progress,
        "blocked": blocked,
        "todo": todo,
        "progress_pct": round((done / total * 100) if total > 0 else 0, 1),
        "issues": issues,
        "warnings": warnings,
        "healthy": len(issues) == 0,
    }


def check_milestone_health(milestones: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Check milestones for risks."""
    at_risk = []
    upcoming = []
    
    for ms in milestones:
        if ms["status"] in ("planned", "in_progress"):
            if ms["date"]:
                try:
                    target_date = datetime.fromisoformat(ms["date"].replace("Z", "+00:00"))
                    days_left = (target_date - datetime.now()).days
                    if days_left < 0:
                        at_risk.append(f"{ms['title']}: OVERDUE by {abs(days_left)} days")
                    elif days_left <= 7:
                        upcoming.append(f"{ms['title']}: {days_left} days")
                except Exception:
                    pass
    
    return {
        "total": len(milestones),
        "at_risk": at_risk,
        "upcoming": upcoming,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Progress Watchdog")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()
    
    sprint = load_active_sprint()
    milestones = load_milestones()
    
    sprint_health = check_sprint_health(sprint)
    milestone_health = check_milestone_health(milestones)
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "sprint": sprint_health,
        "milestones": milestone_health,
        "alerts": [],
    }
    
    # Generate alerts
    for issue in sprint_health["issues"]:
        results["alerts"].append({"level": "critical", "type": "sprint", "message": issue})
    for warning in sprint_health["warnings"]:
        results["alerts"].append({"level": "warning", "type": "sprint", "message": warning})
    for risk in milestone_health["at_risk"]:
        results["alerts"].append({"level": "critical", "type": "milestone", "message": risk})
    for upcoming in milestone_health["upcoming"]:
        results["alerts"].append({"level": "info", "type": "milestone", "message": upcoming})
    
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(f"=== Progress Watchdog {results['timestamp']} ===")
        print(f"\nSprint: {sprint.get('name', 'Unknown')}")
        print(f"  Stories: {sprint_health['total_stories']} total, {sprint_health['done']} done, {sprint_health['in_progress']} in progress, {sprint_health['blocked']} blocked")
        print(f"  Progress: {sprint_health['progress_pct']}%")
        if sprint_health["issues"]:
            for issue in sprint_health["issues"]:
                print(f"  [CRITICAL] {issue}")
        if sprint_health["warnings"]:
            for warning in sprint_health["warnings"]:
                print(f"  [WARN] {warning}")
        
        print(f"\nMilestones: {milestone_health['total']} total")
        if milestone_health["at_risk"]:
            for risk in milestone_health["at_risk"]:
                print(f"  [CRITICAL] {risk}")
        if milestone_health["upcoming"]:
            for up in milestone_health["upcoming"]:
                print(f"  [INFO] {up}")
    
    # Exit code: 0 = healthy, 1 = warnings, 2 = critical
    has_critical = any(a["level"] == "critical" for a in results["alerts"])
    has_warning = any(a["level"] == "warning" for a in results["alerts"])
    
    if has_critical:
        return 2
    elif has_warning:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())