"""
Observability Dashboard v1.0 — Alerting Engine
Threshold-based alerting with multiple notification channels.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum

from .storage import MetricsStorage, create_metrics_storage


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertOperator(str, Enum):
    GT = ">"
    LT = "<"
    GTE = ">="
    LTE = "<="
    EQ = "=="
    NEQ = "!="


@dataclass
class AlertRule:
    """Alert rule definition."""
    name: str
    metric: str
    threshold: float
    operator: AlertOperator
    severity: AlertSeverity
    labels: Dict[str, str] = field(default_factory=dict)
    cooldown_seconds: int = 300
    description: str = ""
    enabled: bool = True


@dataclass
class Alert:
    """Active alert instance."""
    rule_name: str
    severity: AlertSeverity
    message: str
    metric_name: str
    metric_value: float
    threshold: float
    triggered_at: datetime
    labels: Dict[str, str]
    alert_id: Optional[int] = None


class AlertEngine:
    """Evaluates alert rules against metrics and manages alert lifecycle."""
    
    def __init__(
        self,
        config: Dict[str, Any],
        storage: MetricsStorage,
        notifiers: Dict[str, Callable] = None
    ):
        self.config = config
        self.storage = storage
        self.notifiers = notifiers or {}
        self.rules: List[AlertRule] = []
        self.active_alerts: Dict[str, Alert] = {}  # rule_name -> Alert
        self._load_rules()
    
    def _load_rules(self):
        """Load alert rules from config."""
        rules_config = self.config.get("alerts", {}).get("rules", [])
        for rule_data in rules_config:
            rule = AlertRule(
                name=rule_data["name"],
                metric=rule_data["metric"],
                threshold=rule_data["threshold"],
                operator=AlertOperator(rule_data["operator"]),
                severity=AlertSeverity(rule_data["severity"]),
                labels=rule_data.get("labels", {}),
                cooldown_seconds=rule_data.get("cooldown_seconds", 300),
                description=rule_data.get("description", ""),
                enabled=rule_data.get("enabled", True)
            )
            self.rules.append(rule)
    
    def evaluate(self, metrics: Dict[str, Any]) -> List[Alert]:
        """Evaluate all rules against current metrics."""
        new_alerts = []
        
        for rule in self.rules:
            if not rule.enabled:
                continue
            
            # Get metric value
            value = self._get_metric_value(metrics, rule.metric, rule.labels)
            if value is None:
                continue
            
            # Evaluate condition
            triggered = self._evaluate_condition(value, rule.threshold, rule.operator)
            
            if triggered:
                # Check if already alerting (cooldown)
                if rule.name in self.active_alerts:
                    alert = self.active_alerts[rule.name]
                    elapsed = (datetime.now() - alert.triggered_at).total_seconds()
                    if elapsed < rule.cooldown_seconds:
                        continue
                
                # Create new alert
                alert = Alert(
                    rule_name=rule.name,
                    severity=rule.severity,
                    message=f"{rule.description or rule.name}: {rule.metric}={value} {rule.operator.value} {rule.threshold}",
                    metric_name=rule.metric,
                    metric_value=value,
                    threshold=rule.threshold,
                    triggered_at=datetime.now(),
                    labels={**rule.labels, "alert_rule": rule.name}
                )
                
                # Persist to storage
                alert_id = self._persist_alert(alert)
                alert.alert_id = alert_id
                
                self.active_alerts[rule.name] = alert
                new_alerts.append(alert)
                
                # Notify
                self._notify(alert)
                
            else:
                # Check if we should resolve an active alert
                if rule.name in self.active_alerts:
                    self._resolve_alert(rule.name)
        
        return new_alerts
    
    def _get_metric_value(self, metrics: Dict[str, Any], metric: str, labels: Dict[str, str]) -> Optional[float]:
        """Extract metric value from metrics dict."""
        # Check nested structure
        for category in ["workflows", "tokens", "skills", "system", "marketplace"]:
            if category in metrics and metric in metrics[category]:
                return metrics[category][metric]
        
        # Try flat structure
        if metric in metrics:
            return metrics[metric]
        
        return None
    
    def _evaluate_condition(self, value: float, threshold: float, operator: AlertOperator) -> bool:
        """Evaluate alert condition."""
        if operator == AlertOperator.GT:
            return value > threshold
        elif operator == AlertOperator.LT:
            return value < threshold
        elif operator == AlertOperator.GTE:
            return value >= threshold
        elif operator == AlertOperator.LTE:
            return value <= threshold
        elif operator == AlertOperator.EQ:
            return value == threshold
        elif operator == AlertOperator.NEQ:
            return value != threshold
        return False
    
    def _persist_alert(self, alert: Alert) -> int:
        """Persist alert to storage."""
        self.storage.write_alert(
            alert_name=alert.rule_name,
            severity=alert.severity.value,
            message=alert.message,
            metric_name=alert.metric_name,
            metric_value=alert.metric_value,
            threshold=alert.threshold
        )
        
        # Get the inserted ID
        with sqlite3.connect(self.storage.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT id FROM alerts WHERE alert_name = ? AND resolved = FALSE ORDER BY timestamp DESC LIMIT 1",
                (alert.rule_name,)
            )
            row = cursor.fetchone()
            return row["id"] if row else 0
    
    def _resolve_alert(self, rule_name: str):
        """Resolve an active alert."""
        alert = self.active_alerts.pop(rule_name, None)
        if alert and alert.alert_id:
            self.storage.resolve_alert(alert.alert_id)
    
    def _notify(self, alert: Alert):
        """Send alert notifications."""
        channels = self.config.get("alerts", {}).get("channels", ["console"])
        
        for channel in channels:
            notifier = self.notifiers.get(channel)
            if notifier:
                try:
                    notifier(alert)
                except Exception:
                    pass
    
    def get_active_alerts(self) -> List[Alert]:
        """Get all currently active alerts."""
        return list(self.active_alerts.values())


# Default notifiers
def console_notifier(alert: Alert):
    """Print alert to console."""
    severity_emoji = {
        AlertSeverity.INFO: "ℹ️",
        AlertSeverity.WARNING: "⚠️",
        AlertSeverity.CRITICAL: "🚨"
    }
    emoji = severity_emoji.get(alert.severity, "📢")
    print(f"{emoji} [{alert.severity.value.upper()}] {alert.message}")


def ntfy_notifier(alert: Alert, topic: str = None):
    """Send alert via ntfy.sh."""
    import requests
    topic = topic or "hermes-alerts"
    url = f"https://ntfy.sh/{topic}"
    
    severity_emoji = {
        AlertSeverity.INFO: "ℹ️",
        AlertSeverity.WARNING: "⚠️",
        AlertSeverity.CRITICAL: "🚨"
    }
    emoji = severity_emoji.get(alert.severity, "📢")
    
    headers = {
        "Title": f"{emoji} Hermes Alert: {alert.rule_name}",
        "Priority": "high" if alert.severity == AlertSeverity.CRITICAL else "default",
        "Tags": f"alert,{alert.severity.value}"
    }
    
    requests.post(url, data=alert.message, headers=headers, timeout=5)


def webhook_notifier(alert: Alert, url: str = None):
    """Send alert to webhook."""
    import requests
    url = url or "http://localhost:8080/alerts"
    
    payload = {
        "alert_name": alert.rule_name,
        "severity": alert.severity.value,
        "message": alert.message,
        "metric": alert.metric_name,
        "value": alert.metric_value,
        "threshold": alert.threshold,
        "timestamp": alert.triggered_at.isoformat(),
        "labels": alert.labels
    }
    
    requests.post(url, json=payload, timeout=5)


def create_alert_engine(config: Dict[str, Any], storage: MetricsStorage) -> AlertEngine:
    notifiers = {
        "console": console_notifier,
        "ntfy": lambda a: ntfy_notifier(a, config.get("alerts", {}).get("ntfy_topic")),
        "webhook": lambda a: webhook_notifier(a, config.get("alerts", {}).get("webhook_url"))
    }
    return AlertEngine(config, storage, notifiers)


import sqlite3

__all__ = [
    "AlertEngine",
    "AlertRule",
    "Alert",
    "AlertSeverity",
    "AlertOperator",
    "console_notifier",
    "ntfy_notifier",
    "webhook_notifier",
    "create_alert_engine"
]