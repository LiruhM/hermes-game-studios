"""
Observability Dashboard v1.0 — Main Entry Point
Real-time metrics, health monitoring, and visual dashboards.
"""

from typing import Dict, Any, Optional, List, Callable
from pathlib import Path

from .storage import MetricsStorage, MetricPoint, create_metrics_storage
from .collector import (
    MetricsCollector,
    SystemCollector,
    TokenOptimizationCollector,
    WorkflowCollector,
    SkillComposabilityCollector,
    SkillMarketplaceCollector,
    create_metrics_collector
)
from .health import HealthChecker, HealthCheckResult, HealthStatus, create_health_checker
from .alerting import (
    AlertEngine, AlertRule, Alert, AlertSeverity, AlertOperator,
    console_notifier, ntfy_notifier, webhook_notifier,
    create_alert_engine
)
from .snapshot import SnapshotGenerator, DashboardSnapshot, create_snapshot_generator


__version__ = "1.0.0"

__all__ = [
    # Storage
    "MetricsStorage",
    "MetricPoint",
    "create_metrics_storage",
    
    # Collector
    "MetricsCollector",
    "SystemCollector",
    "TokenOptimizationCollector",
    "WorkflowCollector",
    "SkillComposabilityCollector",
    "SkillMarketplaceCollector",
    "create_metrics_collector",
    
    # Health
    "HealthChecker",
    "HealthCheckResult",
    "HealthStatus",
    "create_health_checker",
    
    # Alerting
    "AlertEngine",
    "AlertRule",
    "Alert",
    "AlertSeverity",
    "AlertOperator",
    "console_notifier",
    "ntfy_notifier",
    "webhook_notifier",
    "create_alert_engine",
    
    # Snapshot
    "SnapshotGenerator",
    "DashboardSnapshot",
    "create_snapshot_generator",
]


# Convenience class for easy usage
class ObservabilityDashboard:
    """High-level observability dashboard interface."""
    
    def __init__(self, config: Dict[str, Any] = None, skill_loader: Callable = None):
        self.config = config or {}
        self.skill_loader = skill_loader
        
        # Initialize components
        self.collector = create_metrics_collector(self.config, skill_loader)
        self.health_checker = create_health_checker(self.config, skill_loader)
        self.alert_engine = create_alert_engine(self.config, self.collector.storage)
        self.snapshot_generator = create_snapshot_generator(self.config, skill_loader)
    
    def start(self):
        """Start background metric collection."""
        self.collector.start()
    
    def stop(self):
        """Stop background metric collection."""
        self.collector.stop()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics snapshot."""
        self.collector.collect_and_store()
        return self.collector.get_metrics()
    
    def get_health(self) -> Dict[str, Any]:
        """Get health status."""
        return self.health_checker.run_and_report()
    
    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get active alerts."""
        alerts = self.alert_engine.get_active_alerts()
        return [
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
    
    def query_metric(self, name: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Query metric time series."""
        return self.collector.query_metric(name, hours)
    
    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        return self.collector.export_prometheus()
    
    def generate_snapshot(self, hours_trends: int = 24) -> DashboardSnapshot:
        """Generate a complete dashboard snapshot."""
        return self.snapshot_generator.generate(hours_trends)
    
    def save_snapshot(self, snapshot: DashboardSnapshot, path: Path = None) -> Path:
        """Save snapshot to file."""
        return self.snapshot_generator.save_snapshot(snapshot, path)
    
    def evaluate_alerts(self) -> List[Alert]:
        """Evaluate alert rules against current metrics."""
        metrics = self.get_metrics()
        return self.alert_engine.evaluate(metrics)


from typing import Dict, Any, Optional, List, Callable
from pathlib import Path