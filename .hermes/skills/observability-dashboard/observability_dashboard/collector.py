"""
Observability Dashboard v1.0 — Collector
Collects metrics from various sources in the Hermes ecosystem.
"""

import time
import psutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from collections import defaultdict

from .storage import MetricsStorage, MetricPoint, create_metrics_storage


@dataclass
class CollectionConfig:
    """Configuration for a metric source."""
    name: str
    enabled: bool = True
    interval_seconds: int = 30
    collector_func: Optional[Callable] = None


class SystemCollector:
    """Collects system-level metrics."""
    
    @staticmethod
    def collect() -> List[MetricPoint]:
        points = []
        now = datetime.now()
        
        # CPU
        cpu_pct = psutil.cpu_percent(interval=0.1)
        points.append(MetricPoint(now, "system_cpu_pct", cpu_pct, {}, "gauge"))
        
        # Memory
        mem = psutil.virtual_memory()
        points.append(MetricPoint(now, "system_memory_pct", mem.percent, {}, "gauge"))
        points.append(MetricPoint(now, "system_memory_available_mb", mem.available / 1024 / 1024, {}, "gauge"))
        points.append(MetricPoint(now, "system_memory_used_mb", mem.used / 1024 / 1024, {}, "gauge"))
        
        # Disk
        disk = psutil.disk_usage("/")
        points.append(MetricPoint(now, "system_disk_pct", disk.percent, {}, "gauge"))
        points.append(MetricPoint(now, "system_disk_free_gb", disk.free / 1024 / 1024 / 1024, {}, "gauge"))
        
        # Network
        net = psutil.net_io_counters()
        points.append(MetricPoint(now, "system_network_bytes_sent", net.bytes_sent, {}, "counter"))
        points.append(MetricPoint(now, "system_network_bytes_recv", net.bytes_recv, {}, "counter"))
        
        # Process count
        points.append(MetricPoint(now, "system_process_count", len(psutil.pids()), {}, "gauge"))
        
        return points


class TokenOptimizationCollector:
    """Collects metrics from token-optimization skill."""
    
    def __init__(self, skill_loader: Callable):
        self.skill_loader = skill_loader
    
    def collect(self) -> List[MetricPoint]:
        points = []
        now = datetime.now()
        
        try:
            # Try to load token-optimization skill
            skill = self.skill_loader("token-optimization")
            if not skill:
                return points
            
            # Get budget governor metrics
            if hasattr(skill, 'get_budget_status'):
                status = skill.get_budget_status()
                points.append(MetricPoint(now, "token_usage_pct", 
                    status.get("usage_pct", 0), {"feature": "default"}, "gauge"))
                points.append(MetricPoint(now, "token_budget_remaining",
                    status.get("remaining", 0), {"feature": "default"}, "gauge"))
                points.append(MetricPoint(now, "token_budget_limit",
                    status.get("limit", 0), {"feature": "default"}, "gauge"))
            
            # Get pipeline observability metrics
            if hasattr(skill, 'get_pipeline_metrics'):
                metrics = skill.get_pipeline_metrics()
                for name, value in metrics.items():
                    points.append(MetricPoint(now, f"token_{name}", value, {}, "gauge"))
            
            # Get compression ratio
            if hasattr(skill, 'get_compression_ratio'):
                ratio = skill.get_compression_ratio()
                points.append(MetricPoint(now, "token_compression_ratio", ratio, {}, "gauge"))
            
            # Latency metrics
            if hasattr(skill, 'get_latency_metrics'):
                latency = skill.get_latency_metrics()
                for op, ms in latency.items():
                    points.append(MetricPoint(now, "token_latency_ms", ms, {"operation": op}, "histogram"))
                    
        except Exception:
            pass
        
        return points


class WorkflowCollector:
    """Collects metrics from cross-skill-workflows."""
    
    def __init__(self, skill_loader: Callable):
        self.skill_loader = skill_loader
    
    def collect(self) -> List[MetricPoint]:
        points = []
        now = datetime.now()
        
        try:
            skill = self.skill_loader("cross-skill-workflows")
            if not skill:
                return points
            
            # Get workflow execution metrics
            if hasattr(skill, 'get_metrics'):
                metrics = skill.get_metrics()
                for name, value in metrics.items():
                    if isinstance(value, (int, float)):
                        points.append(MetricPoint(now, f"workflow_{name}", value, {}, "gauge"))
            
            # Get queue depth
            if hasattr(skill, 'get_queue_depth'):
                depth = skill.get_queue_depth()
                points.append(MetricPoint(now, "workflow_queue_depth", depth, {}, "gauge"))
            
            # Active executions
            if hasattr(skill, 'get_active_count'):
                active = skill.get_active_count()
                points.append(MetricPoint(now, "workflow_active", active, {}, "gauge"))
                    
        except Exception:
            pass
        
        return points


class SkillComposabilityCollector:
    """Collects metrics from skill-composability."""
    
    def __init__(self, skill_loader: Callable):
        self.skill_loader = skill_loader
    
    def collect(self) -> List[MetricPoint]:
        points = []
        now = datetime.now()
        
        try:
            skill = self.skill_loader("skill-composability")
            if not skill:
                return points
            
            # Skill health
            if hasattr(skill, 'get_skill_health'):
                health = skill.get_skill_health()
                for skill_name, status in health.items():
                    status_val = 2 if status == "healthy" else (1 if status == "degraded" else 0)
                    points.append(MetricPoint(now, "skill_health", status_val, {"skill": skill_name}, "gauge"))
            
            # Load times
            if hasattr(skill, 'get_load_times'):
                times = skill.get_load_times()
                for skill_name, ms in times.items():
                    points.append(MetricPoint(now, "skill_load_time_ms", ms, {"skill": skill_name}, "histogram"))
            
            # Memory per skill
            if hasattr(skill, 'get_memory_usage'):
                memory = skill.get_memory_usage()
                for skill_name, mb in memory.items():
                    points.append(MetricPoint(now, "skill_memory_mb", mb, {"skill": skill_name}, "gauge"))
            
            # Errors
            if hasattr(skill, 'get_error_counts'):
                errors = skill.get_error_counts()
                for skill_name, count in errors.items():
                    points.append(MetricPoint(now, "skill_errors_total", count, {"skill": skill_name}, "counter"))
                    
        except Exception:
            pass
        
        return points


class SkillMarketplaceCollector:
    """Collects metrics from skill-marketplace."""
    
    def __init__(self, skill_loader: Callable):
        self.skill_loader = skill_loader
    
    def collect(self) -> List[MetricPoint]:
        points = []
        now = datetime.now()
        
        try:
            skill = self.skill_loader("skill-marketplace")
            if not skill:
                return points
            
            # Registry stats
            if hasattr(skill, 'get_registry_stats'):
                stats = skill.get_registry_stats()
                points.append(MetricPoint(now, "marketplace_skills_total", stats.get("total", 0), {}, "gauge"))
                points.append(MetricPoint(now, "marketplace_skills_installed", stats.get("installed", 0), {}, "gauge"))
                points.append(MetricPoint(now, "marketplace_skills_published", stats.get("published", 0), {}, "gauge"))
            
            # Install/publish rates (would need time-series)
            if hasattr(skill, 'get_install_rate'):
                points.append(MetricPoint(now, "marketplace_install_rate", skill.get_install_rate(), {}, "gauge"))
            if hasattr(skill, 'get_publish_rate'):
                points.append(MetricPoint(now, "marketplace_publish_rate", skill.get_publish_rate(), {}, "gauge"))
                    
        except Exception:
            pass
        
        return points


class MetricsCollector:
    """Main metrics collector orchestrating all sources."""
    
    def __init__(self, config: Dict[str, Any], skill_loader: Callable = None):
        self.config = config
        self.skill_loader = skill_loader
        self.storage = create_metrics_storage(
            Path(config.get("metrics_db", "90-Sistema/_data/observability.db"))
        )
        
        # Initialize collectors
        self.collectors = {
            "system": SystemCollector(),
            "token_optimization": TokenOptimizationCollector(skill_loader) if skill_loader else None,
            "cross_skill_workflows": WorkflowCollector(skill_loader) if skill_loader else None,
            "skill_composability": SkillComposabilityCollector(skill_loader) if skill_loader else None,
            "skill_marketplace": SkillMarketplaceCollector(skill_loader) if skill_loader else None,
        }
        
        # Filter enabled sources
        enabled_sources = config.get("sources", [])
        self.collectors = {k: v for k, v in self.collectors.items() 
                          if v and k in enabled_sources}
        
        self.interval = config.get("collection_interval_seconds", 30)
        self._running = False
        self._thread: Optional[threading.Thread] = None
    
    def collect_all(self) -> List[MetricPoint]:
        """Collect metrics from all enabled sources."""
        all_points = []
        
        for name, collector in self.collectors.items():
            try:
                points = collector.collect()
                # Add source label
                for p in points:
                    p.labels["source"] = name
                all_points.extend(points)
            except Exception as e:
                # Write error metric
                all_points.append(MetricPoint(
                    timestamp=datetime.now(),
                    name="collector_errors_total",
                    value=1,
                    labels={"source": name, "error": str(e)[:100]},
                    metric_type="counter"
                ))
        
        return all_points
    
    def collect_and_store(self):
        """Collect and immediately store metrics."""
        points = self.collect_all()
        if points:
            self.storage.write_metrics_batch(points)
    
    def start(self):
        """Start background collection."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._collection_loop, daemon=True)
        self._thread.start()
    
    def stop(self):
        """Stop background collection."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
    
    def _collection_loop(self):
        """Background collection loop."""
        while self._running:
            start = time.time()
            try:
                self.collect_and_store()
            except Exception:
                pass
            
            elapsed = time.time() - start
            sleep_time = max(0, self.interval - elapsed)
            time.sleep(sleep_time)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics snapshot organized by category."""
        categories = {
            "workflows": ["workflow_started_total", "workflow_completed_total", 
                         "workflow_failed_total", "workflow_active", "workflow_queue_depth"],
            "tokens": ["token_usage_pct", "token_budget_remaining", "token_budget_limit",
                      "token_compression_ratio", "token_latency_ms"],
            "skills": ["skill_health", "skill_load_time_ms", "skill_memory_mb", "skill_errors_total"],
            "system": ["system_cpu_pct", "system_memory_pct", "system_disk_pct",
                      "system_network_bytes_sent", "system_network_bytes_recv"],
            "marketplace": ["marketplace_skills_total", "marketplace_skills_installed",
                           "marketplace_skills_published"]
        }
        
        result = {}
        for category, metric_names in categories.items():
            result[category] = {}
            for name in metric_names:
                point = self.storage.get_latest_metric(name)
                if point:
                    result[category][name] = point.value
        
        return result
    
    def query_metric(self, name: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Query time series for a metric."""
        points = self.storage.query_metric(name, hours=hours)
        return [
            {"timestamp": p.timestamp.isoformat(), "value": p.value, "labels": p.labels}
            for p in points
        ]
    
    def get_health(self) -> Dict[str, Any]:
        """Get overall health status."""
        health = self.storage.get_latest_health()
        
        # Determine overall status
        statuses = [h.get("status", "unknown") for h in health.values()]
        if "critical" in statuses or "down" in statuses:
            overall = "critical"
        elif "degraded" in statuses:
            overall = "degraded"
        elif statuses:
            overall = "healthy"
        else:
            overall = "unknown"
        
        return {
            "overall": overall,
            "components": health,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get active alerts from storage."""
        return self.storage.get_active_alerts()
    
    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []
        
        # Get all recent metrics
        for category in ["workflows", "tokens", "skills", "system", "marketplace"]:
            metrics = self.get_metrics().get(category, {})
            for name, value in metrics.items():
                # Sanitize metric name for Prometheus
                prom_name = name.replace(".", "_").replace("-", "_")
                lines.append(f'# TYPE {prom_name} gauge')
                lines.append(f'{prom_name} {value}')
        
        return "\n".join(lines)


def create_metrics_collector(config: Dict[str, Any], skill_loader: Callable = None) -> MetricsCollector:
    return MetricsCollector(config, skill_loader)


__all__ = [
    "MetricsCollector",
    "SystemCollector",
    "TokenOptimizationCollector",
    "WorkflowCollector",
    "SkillComposabilityCollector",
    "SkillMarketplaceCollector",
    "create_metrics_collector"
]