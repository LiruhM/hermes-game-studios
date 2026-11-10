"""
Observability Dashboard v1.0 — Snapshot Generator
Generates dashboard snapshots for reports and historical analysis.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, asdict

from .storage import MetricsStorage, create_metrics_storage
from .collector import MetricsCollector, create_metrics_collector
from .health import HealthChecker, create_health_checker
from .alerting import AlertEngine, create_alert_engine


@dataclass
class DashboardSnapshot:
    """Complete dashboard snapshot for reporting."""
    timestamp: datetime
    metrics: Dict[str, Any]
    health: Dict[str, Any]
    alerts: List[Dict[str, Any]]
    trends: Dict[str, Any]
    summary: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "metrics": self.metrics,
            "health": self.health,
            "alerts": self.alerts,
            "trends": self.trends,
            "summary": self.summary
        }
    
    def to_json(self, path: Path = None) -> str:
        json_str = json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
        if path:
            path.write_text(json_str, encoding="utf-8")
        return json_str


class SnapshotGenerator:
    """Generates comprehensive dashboard snapshots."""
    
    def __init__(self, config: Dict[str, Any], skill_loader: Callable = None):
        self.config = config
        self.skill_loader = skill_loader
        
        # Initialize components
        self.collector = create_metrics_collector(config, skill_loader)
        self.health_checker = create_health_checker(config, skill_loader)
        self.alert_engine = create_alert_engine(config, self.collector.storage)
    
    def generate(self, hours_trends: int = 24) -> DashboardSnapshot:
        """Generate a complete snapshot."""
        timestamp = datetime.now()
        
        # Collect current metrics
        self.collector.collect_and_store()
        metrics = self.collector.get_metrics()
        
        # Get health status
        health = self.health_checker.run_and_report()
        
        # Get active alerts
        alerts = self.alert_engine.get_active_alerts()
        alerts_data = [
            {
                "rule_name": a.rule_name,
                "severity": a.severity.value,
                "message": a.message,
                "metric": a.metric_name,
                "value": a.metric_value,
                "threshold": a.threshold,
                "triggered_at": a.triggered_at.isoformat()
            }
            for a in alerts
        ]
        
        # Calculate trends
        trends = self._calculate_trends(hours_trends)
        
        # Generate summary
        summary = self._generate_summary(metrics, health, alerts_data, trends)
        
        return DashboardSnapshot(
            timestamp=timestamp,
            metrics=metrics,
            health=health,
            alerts=alerts_data,
            trends=trends,
            summary=summary
        )
    
    def _calculate_trends(self, hours: int) -> Dict[str, Any]:
        """Calculate trend data for key metrics."""
        key_metrics = [
            "token_usage_pct",
            "workflow_completed_total",
            "workflow_failed_total",
            "system_cpu_pct",
            "system_memory_pct",
            "workflow_queue_depth"
        ]
        
        trends = {}
        for metric in key_metrics:
            points = self.collector.storage.query_metric(metric, hours=hours)
            if points:
                values = [p.value for p in points]
                if len(values) >= 2:
                    # Simple trend: compare first half vs second half
                    mid = len(values) // 2
                    first_half_avg = sum(values[:mid]) / mid if mid > 0 else values[0]
                    second_half_avg = sum(values[mid:]) / (len(values) - mid) if len(values) > mid else values[-1]
                    
                    change_pct = 0
                    if first_half_avg != 0:
                        change_pct = ((second_half_avg - first_half_avg) / first_half_avg) * 100
                    
                    trends[metric] = {
                        "current": values[-1],
                        "avg": sum(values) / len(values),
                        "min": min(values),
                        "max": max(values),
                        "change_pct": round(change_pct, 2),
                        "direction": "up" if change_pct > 1 else ("down" if change_pct < -1 else "stable"),
                        "data_points": len(values)
                    }
        
        return trends
    
    def _generate_summary(self, metrics: Dict, health: Dict, alerts: List, trends: Dict) -> Dict[str, Any]:
        """Generate executive summary."""
        # Count workflows
        wf = metrics.get("workflows", {})
        workflows_started = wf.get("workflow_started_total", 0)
        workflows_completed = wf.get("workflow_completed_total", 0)
        workflows_failed = wf.get("workflow_failed_total", 0)
        
        # Token usage
        tokens = metrics.get("tokens", {})
        token_usage = tokens.get("token_usage_pct", 0)
        
        # System health
        system = metrics.get("system", {})
        cpu = system.get("system_cpu_pct", 0)
        mem = system.get("system_memory_pct", 0)
        
        # Alert counts by severity
        alert_counts = {"critical": 0, "warning": 0, "info": 0}
        for alert in alerts:
            alert_counts[alert.get("severity", "info")] += 1
        
        return {
            "workflows": {
                "started": workflows_started,
                "completed": workflows_completed,
                "failed": workflows_failed,
                "success_rate": workflows_completed / workflows_started if workflows_started > 0 else 0
            },
            "tokens": {
                "usage_pct": token_usage,
                "status": "ok" if token_usage < 70 else ("warning" if token_usage < 90 else "critical")
            },
            "system": {
                "cpu_pct": cpu,
                "memory_pct": mem,
                "status": "ok" if cpu < 70 and mem < 80 else ("warning" if cpu < 90 and mem < 90 else "critical")
            },
            "health": {
                "overall": health.get("overall", "unknown"),
                "checks_passed": len([c for c in health.get("checks", {}).values() if c.get("status") == "healthy"]),
                "checks_total": len(health.get("checks", {}))
            },
            "alerts": alert_counts,
            "trends": {
                metric: data.get("direction", "stable")
                for metric, data in trends.items()
            }
        }
    
    def save_snapshot(self, snapshot: DashboardSnapshot, path: Path = None) -> Path:
        """Save snapshot to file."""
        if path is None:
            path = Path(self.config.get("vault_path", "50-Meta/observability")) / f"snapshot-{snapshot.timestamp.strftime('%Y%m%d-%H%M%S')}.json"
        
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        snapshot.to_json(path)
        return path
    
    def load_snapshot(self, path: Path) -> DashboardSnapshot:
        """Load snapshot from file."""
        data = json.loads(path.read_text(encoding="utf-8"))
        return DashboardSnapshot(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metrics=data["metrics"],
            health=data["health"],
            alerts=data["alerts"],
            trends=data["trends"],
            summary=data["summary"]
        )
    
    def compare_snapshots(self, current: DashboardSnapshot, previous: DashboardSnapshot) -> Dict[str, Any]:
        """Compare two snapshots and return differences."""
        diff = {
            "time_diff_hours": (current.timestamp - previous.timestamp).total_seconds() / 3600,
            "metrics_delta": {},
            "health_changed": current.health.get("overall") != previous.health.get("overall"),
            "alerts_delta": len(current.alerts) - len(previous.alerts),
            "summary_delta": {}
        }
        
        # Compare key metrics
        for category in ["workflows", "tokens", "system"]:
            curr = current.metrics.get(category, {})
            prev = previous.metrics.get(category, {})
            for key in curr:
                if key in prev:
                    diff["metrics_delta"][f"{category}.{key}"] = {
                        "current": curr[key],
                        "previous": prev[key],
                        "delta": curr[key] - prev[key] if isinstance(curr[key], (int, float)) else "N/A"
                    }
        
        # Compare summary
        for key in ["workflows", "tokens", "system", "health", "alerts"]:
            if key in current.summary and key in previous.summary:
                diff["summary_delta"][key] = {
                    "current": current.summary[key],
                    "previous": previous.summary[key]
                }
        
        return diff


def create_snapshot_generator(config: Dict[str, Any], skill_loader: Callable = None) -> SnapshotGenerator:
    return SnapshotGenerator(config, skill_loader)


__all__ = ["SnapshotGenerator", "DashboardSnapshot", "create_snapshot_generator"]