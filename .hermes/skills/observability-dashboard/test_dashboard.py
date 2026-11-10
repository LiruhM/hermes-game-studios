"""
Observability Dashboard v1.0 — Integration Tests
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime

from observability_dashboard import (
    MetricsStorage, MetricPoint, MetricsCollector, SystemCollector,
    HealthChecker, HealthCheckResult, HealthStatus,
    AlertEngine, AlertRule, Alert, AlertSeverity, AlertOperator,
    SnapshotGenerator, DashboardSnapshot,
    ObservabilityDashboard,
    create_metrics_storage, create_metrics_collector,
    create_health_checker, create_alert_engine, create_snapshot_generator
)


class TestMetricsStorage:
    """Test metrics storage."""
    
    def test_write_and_query_metric(self):
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        
        try:
            storage = create_metrics_storage(db_path)
            
            # Write metric
            point = MetricPoint(
                timestamp=datetime.now(),
                name="test_metric",
                value=42.5,
                labels={"source": "test"},
                metric_type="gauge"
            )
            storage.write_metric(point)
            
            # Query metric
            points = storage.query_metric("test_metric", hours=1)
            assert len(points) == 1
            assert points[0].value == 42.5
            assert points[0].labels["source"] == "test"
        finally:
            if db_path.exists():
                try:
                    db_path.unlink()
                except PermissionError:
                    pass
    
    def test_batch_write(self):
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        
        try:
            storage = create_metrics_storage(db_path)
            
            points = [
                MetricPoint(datetime.now(), "batch_test", float(i), {}, "gauge")
                for i in range(10)
            ]
            storage.write_metrics_batch(points)
            
            queried = storage.query_metric("batch_test", hours=1)
            assert len(queried) == 10
        finally:
            if db_path.exists():
                try:
                    db_path.unlink()
                except PermissionError:
                    pass
    
    def test_latest_metric(self):
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        
        try:
            storage = create_metrics_storage(db_path)
            
            storage.write_metric(MetricPoint(datetime.now(), "latest_test", 1.0, {}, "gauge"))
            storage.write_metric(MetricPoint(datetime.now(), "latest_test", 2.0, {}, "gauge"))
            storage.write_metric(MetricPoint(datetime.now(), "latest_test", 3.0, {}, "gauge"))
            
            latest = storage.get_latest_metric("latest_test")
            assert latest is not None
            assert latest.value == 3.0
        finally:
            if db_path.exists():
                try:
                    db_path.unlink()
                except PermissionError:
                    pass
    
    def test_metric_summary(self):
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        
        try:
            storage = create_metrics_storage(db_path)
            
            for v in [10, 20, 30, 40, 50]:
                storage.write_metric(MetricPoint(datetime.now(), "summary_test", float(v), {}, "gauge"))
            
            summary = storage.get_metric_summary("summary_test", hours=1)
            assert summary["count"] == 5
            assert summary["min"] == 10
            assert summary["max"] == 50
            assert summary["avg"] == 30
        finally:
            if db_path.exists():
                try:
                    db_path.unlink()
                except PermissionError:
                    pass


class TestSystemCollector:
    """Test system metrics collector."""
    
    def test_collect(self):
        collector = SystemCollector()
        points = collector.collect()
        
        assert len(points) > 0
        names = [p.name for p in points]
        assert "system_cpu_pct" in names
        assert "system_memory_pct" in names
        assert "system_disk_pct" in names
        
        # Values should be reasonable
        for p in points:
            if "pct" in p.name:
                assert 0 <= p.value <= 100


class TestHealthChecker:
    """Test health checker."""
    
    def test_check_system(self):
        checker = create_health_checker({})
        result = checker._check_system()
        
        assert result.component == "system"
        assert result.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.CRITICAL]
        assert result.latency_ms >= 0
    
    def test_check_memory(self):
        checker = create_health_checker({})
        result = checker._check_memory()
        
        assert result.component == "memory"
        assert result.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.CRITICAL]
    
    def test_check_disk(self):
        checker = create_health_checker({})
        result = checker._check_disk()
        
        assert result.component == "disk"
        assert result.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.CRITICAL]
    
    def test_run_all(self):
        checker = create_health_checker({})
        results = checker.run_all()
        
        assert "system" in results
        assert "memory" in results
        assert "disk" in results
        
        overall = checker.get_overall_status(results)
        assert overall in [HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.CRITICAL]


class TestAlertEngine:
    """Test alert engine."""
    
    def test_evaluate_gt(self):
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        
        try:
            storage = create_metrics_storage(db_path)
            config = {
                "alerts": {
                    "rules": [
                        {
                            "name": "test_high",
                            "metric": "test_metric",
                            "threshold": 50,
                            "operator": ">",
                            "severity": "warning"
                        }
                    ]
                }
            }
            
            engine = create_alert_engine(config, storage)
            
            # Test triggering
            metrics = {"test_metric": 75}
            alerts = engine.evaluate(metrics)
            assert len(alerts) == 1
            assert alerts[0].severity == AlertSeverity.WARNING
            assert alerts[0].metric_value == 75
            
            # Test not triggering
            metrics = {"test_metric": 25}
            alerts = engine.evaluate(metrics)
            assert len(alerts) == 0
        finally:
            if db_path.exists():
                try:
                    db_path.unlink()
                except PermissionError:
                    pass
    
    def test_evaluate_lt(self):
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        
        try:
            storage = create_metrics_storage(db_path)
            config = {
                "alerts": {
                    "rules": [
                        {
                            "name": "test_low",
                            "metric": "test_metric",
                            "threshold": 50,
                            "operator": "<",
                            "severity": "warning"
                        }
                    ]
                }
            }
            
            engine = create_alert_engine(config, storage)
            
            metrics = {"test_metric": 25}
            alerts = engine.evaluate(metrics)
            assert len(alerts) == 1
            
            metrics = {"test_metric": 75}
            alerts = engine.evaluate(metrics)
            assert len(alerts) == 0
        finally:
            if db_path.exists():
                try:
                    db_path.unlink()
                except PermissionError:
                    pass
    
    def test_cooldown(self):
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        
        try:
            storage = create_metrics_storage(db_path)
            config = {
                "alerts": {
                    "rules": [
                        {
                            "name": "test_cooldown",
                            "metric": "test_metric",
                            "threshold": 50,
                            "operator": ">",
                            "severity": "warning",
                            "cooldown_seconds": 3600  # 1 hour
                        }
                    ]
                }
            }
            
            engine = create_alert_engine(config, storage)
            
            # First trigger
            alerts = engine.evaluate({"test_metric": 75})
            assert len(alerts) == 1
            
            # Second trigger should be suppressed by cooldown
            alerts = engine.evaluate({"test_metric": 80})
            assert len(alerts) == 0
        finally:
            if db_path.exists():
                try:
                    db_path.unlink()
                except PermissionError:
                    pass


class TestSnapshotGenerator:
    """Test snapshot generation."""
    
    def test_generate_snapshot(self):
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        
        try:
            config = {"metrics_db": str(db_path), "vault_path": "/tmp"}
            generator = create_snapshot_generator(config)
            
            snapshot = generator.generate(hours_trends=1)
            
            assert isinstance(snapshot, DashboardSnapshot)
            assert snapshot.timestamp is not None
            assert "workflows" in snapshot.metrics
            assert "tokens" in snapshot.metrics
            assert "system" in snapshot.metrics
            assert "overall" in snapshot.health
            assert isinstance(snapshot.alerts, list)
            assert isinstance(snapshot.trends, dict)
            assert isinstance(snapshot.summary, dict)
        finally:
            if db_path.exists():
                try:
                    db_path.unlink()
                except PermissionError:
                    pass
    
    def test_save_and_load_snapshot(self):
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            json_path = Path(f.name)
        
        try:
            config = {"metrics_db": str(db_path), "vault_path": str(json_path.parent)}
            generator = create_snapshot_generator(config)
            
            snapshot = generator.generate(hours_trends=1)
            saved_path = generator.save_snapshot(snapshot, json_path)
            
            assert saved_path.exists()
            
            loaded = generator.load_snapshot(saved_path)
            assert loaded.timestamp == snapshot.timestamp
            assert loaded.metrics == snapshot.metrics
        finally:
            if db_path.exists():
                try:
                    db_path.unlink()
                except PermissionError:
                    pass
            if json_path.exists():
                try:
                    json_path.unlink()
                except PermissionError:
                    pass


class TestObservabilityDashboard:
    """Test high-level dashboard interface."""
    
    def test_dashboard_creation(self):
        config = {"metrics_db": "/tmp/test.db"}
        dashboard = ObservabilityDashboard(config)
        
        assert dashboard.collector is not None
        assert dashboard.health_checker is not None
        assert dashboard.alert_engine is not None
        assert dashboard.snapshot_generator is not None
    
    def test_get_metrics(self):
        config = {"metrics_db": "/tmp/test.db", "sources": ["system"]}
        dashboard = ObservabilityDashboard(config)
        
        metrics = dashboard.get_metrics()
        assert "system" in metrics
        assert "system_cpu_pct" in metrics["system"]
    
    def test_get_health(self):
        config = {"metrics_db": "/tmp/test.db"}
        dashboard = ObservabilityDashboard(config)
        
        health = dashboard.get_health()
        assert "overall" in health
        assert "checks" in health
    
    def test_export_prometheus(self):
        config = {"metrics_db": "/tmp/test.db", "sources": ["system"]}
        dashboard = ObservabilityDashboard(config)
        
        prom = dashboard.export_prometheus()
        assert isinstance(prom, str)
        assert len(prom) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])