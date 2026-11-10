"""
Observability Dashboard v1.0 — Storage
SQLite-based time-series storage for metrics and events.
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class MetricPoint:
    """Single metric data point."""
    timestamp: datetime
    name: str
    value: float
    labels: Dict[str, str]
    metric_type: str  # gauge, counter, histogram


class MetricsStorage:
    """SQLite-backed time-series storage for metrics."""
    
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    name TEXT NOT NULL,
                    value REAL NOT NULL,
                    labels TEXT NOT NULL,
                    metric_type TEXT NOT NULL
                );
                
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    data TEXT NOT NULL
                );
                
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    alert_name TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    metric_name TEXT,
                    metric_value REAL,
                    threshold REAL,
                    resolved BOOLEAN DEFAULT FALSE,
                    resolved_at TEXT
                );
                
                CREATE TABLE IF NOT EXISTS health_checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    component TEXT NOT NULL,
                    status TEXT NOT NULL,
                    details TEXT,
                    latency_ms INTEGER
                );
                
                CREATE INDEX IF NOT EXISTS idx_metrics_name_time ON metrics(name, timestamp);
                CREATE INDEX IF NOT EXISTS idx_metrics_labels ON metrics(labels);
                CREATE INDEX IF NOT EXISTS idx_events_type_time ON events(event_type, timestamp);
                CREATE INDEX IF NOT EXISTS idx_alerts_active ON alerts(resolved, timestamp);
                CREATE INDEX IF NOT EXISTS idx_health_time ON health_checks(timestamp);
            """)
    
    def write_metric(self, point: MetricPoint):
        """Write a single metric point."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO metrics (timestamp, name, value, labels, metric_type)
                VALUES (?, ?, ?, ?, ?)
            """, (
                point.timestamp.isoformat(),
                point.name,
                point.value,
                json.dumps(point.labels),
                point.metric_type
            ))
    
    def write_metrics_batch(self, points: List[MetricPoint]):
        """Write multiple metric points efficiently."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany("""
                INSERT INTO metrics (timestamp, name, value, labels, metric_type)
                VALUES (?, ?, ?, ?, ?)
            """, [
                (p.timestamp.isoformat(), p.name, p.value, json.dumps(p.labels), p.metric_type)
                for p in points
            ])
    
    def write_event(self, event_type: str, source: str, data: Dict[str, Any]):
        """Write an event."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO events (timestamp, event_type, source, data)
                VALUES (?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                event_type,
                source,
                json.dumps(data)
            ))
    
    def write_alert(self, alert_name: str, severity: str, message: str,
                   metric_name: str = None, metric_value: float = None,
                   threshold: float = None):
        """Write an alert."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO alerts (timestamp, alert_name, severity, message, metric_name, metric_value, threshold)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                alert_name,
                severity,
                message,
                metric_name,
                metric_value,
                threshold
            ))
    
    def resolve_alert(self, alert_id: int):
        """Mark alert as resolved."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE alerts SET resolved = TRUE, resolved_at = ? WHERE id = ?
            """, (datetime.now().isoformat(), alert_id))
    
    def write_health_check(self, component: str, status: str,
                          details: str = None, latency_ms: int = None):
        """Write a health check result."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO health_checks (timestamp, component, status, details, latency_ms)
                VALUES (?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                component,
                status,
                details,
                latency_ms
            ))
    
    def query_metrics(self, name: str, hours: int = 24,
                     labels: Dict[str, str] = None) -> List[MetricPoint]:
        """Query metrics by name and time range."""
        since = datetime.now() - timedelta(hours=hours)
        
        query = """
            SELECT timestamp, name, value, labels, metric_type
            FROM metrics
            WHERE name = ? AND timestamp >= ?
        """
        params = [name, since.isoformat()]
        
        if labels:
            for k, v in labels.items():
                query += f" AND labels LIKE '%\"{k}\": \"{v}\"%'"
        
        query += " ORDER BY timestamp ASC"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            return [
                MetricPoint(
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    name=row["name"],
                    value=row["value"],
                    labels=json.loads(row["labels"]),
                    metric_type=row["metric_type"]
                )
                for row in cursor.fetchall()
            ]
    
    def query_metric(self, name: str, hours: int = 24,
                     labels: Dict[str, str] = None) -> List[MetricPoint]:
        """Query metrics by name and time range. Alias for query_metrics."""
        return self.query_metrics(name, hours, labels)
    
    def get_latest_metric(self, name: str, labels: Dict[str, str] = None) -> Optional[MetricPoint]:
        """Get the most recent value for a metric."""
        points = self.query_metrics(name, hours=1, labels=labels)
        return points[-1] if points else None
    
    def get_metric_summary(self, name: str, hours: int = 24) -> Dict[str, float]:
        """Get statistical summary of a metric."""
        points = self.query_metrics(name, hours=hours)
        if not points:
            return {}
        
        values = [p.value for p in points]
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "latest": values[-1]
        }
    
    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get all unresolved alerts."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM alerts WHERE resolved = FALSE ORDER BY timestamp DESC
            """)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_latest_health(self) -> Dict[str, Any]:
        """Get latest health status for each component."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT component, status, details, latency_ms, timestamp
                FROM health_checks
                WHERE timestamp = (
                    SELECT MAX(timestamp) FROM health_checks h2 WHERE h2.component = health_checks.component
                )
            """)
            return {row["component"]: dict(row) for row in cursor.fetchall()}
    
    def cleanup_old_data(self, retention_days: int = 30):
        """Remove data older than retention period."""
        cutoff = datetime.now() - timedelta(days=retention_days)
        cutoff_str = cutoff.isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM metrics WHERE timestamp < ?", (cutoff_str,))
            conn.execute("DELETE FROM events WHERE timestamp < ?", (cutoff_str,))
            conn.execute("DELETE FROM health_checks WHERE timestamp < ?", (cutoff_str,))
            # Keep resolved alerts for longer
            conn.execute("DELETE FROM alerts WHERE resolved = TRUE AND resolved_at < ?", (cutoff_str,))


def create_metrics_storage(db_path: Path) -> MetricsStorage:
    return MetricsStorage(db_path)


__all__ = ["MetricsStorage", "MetricPoint", "create_metrics_storage"]