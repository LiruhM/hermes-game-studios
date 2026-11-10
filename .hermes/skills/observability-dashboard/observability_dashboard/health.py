"""
Observability Dashboard v1.0 — Health Checks
Health check orchestrator for all Hermes skills and components.
"""

import time
import psutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
from enum import Enum

from .storage import MetricsStorage, create_metrics_storage


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    DOWN = "down"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a single health check."""
    component: str
    status: HealthStatus
    details: str = ""
    latency_ms: int = 0
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class HealthChecker:
    """Orchestrates health checks across all Hermes components."""
    
    def __init__(self, config: Dict[str, Any], skill_loader: Callable = None):
        self.config = config
        self.skill_loader = skill_loader
        self.storage = create_metrics_storage(
            Path(config.get("metrics_db", "90-Sistema/_data/observability.db"))
        )
        self.checks: Dict[str, Callable] = {}
        self._register_default_checks()
    
    def _register_default_checks(self):
        """Register built-in health checks."""
        self.register_check("system", self._check_system)
        self.register_check("disk", self._check_disk)
        self.register_check("memory", self._check_memory)
        
        if self.skill_loader:
            self.register_check("skill_loader", self._check_skill_loader)
            # Individual skill checks would be registered dynamically
    
    def register_check(self, name: str, check_func: Callable[[], HealthCheckResult]):
        """Register a health check function."""
        self.checks[name] = check_func
    
    def run_all(self) -> Dict[str, HealthCheckResult]:
        """Run all registered health checks."""
        results = {}
        
        for name, check_func in self.checks.items():
            start = time.time()
            try:
                result = check_func()
                result.latency_ms = int((time.time() - start) * 1000)
                results[name] = result
            except Exception as e:
                results[name] = HealthCheckResult(
                    component=name,
                    status=HealthStatus.CRITICAL,
                    details=f"Check failed: {e}",
                    latency_ms=int((time.time() - start) * 1000)
                )
            
            # Persist to storage
            self.storage.write_health_check(
                component=name,
                status=results[name].status.value,
                details=results[name].details,
                latency_ms=results[name].latency_ms
            )
        
        return results
    
    def get_overall_status(self, results: Dict[str, HealthCheckResult]) -> HealthStatus:
        """Determine overall health from individual checks."""
        statuses = [r.status for r in results.values()]
        
        if HealthStatus.CRITICAL in statuses or HealthStatus.DOWN in statuses:
            return HealthStatus.CRITICAL
        elif HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        elif HealthStatus.HEALTHY in statuses:
            return HealthStatus.HEALTHY
        else:
            return HealthStatus.UNKNOWN
    
    def run_and_report(self) -> Dict[str, Any]:
        """Run all checks and return comprehensive report."""
        results = self.run_all()
        overall = self.get_overall_status(results)
        
        return {
            "overall": overall.value,
            "timestamp": datetime.now().isoformat(),
            "checks": {
                name: {
                    "status": result.status.value,
                    "details": result.details,
                    "latency_ms": result.latency_ms,
                    "timestamp": result.timestamp.isoformat()
                }
                for name, result in results.items()
            }
        }
    
    # Built-in checks
    def _check_system(self) -> HealthCheckResult:
        """Check system resources."""
        cpu = psutil.cpu_percent(interval=0.5)
        if cpu > 90:
            return HealthCheckResult("system", HealthStatus.CRITICAL, f"CPU at {cpu}%")
        elif cpu > 75:
            return HealthCheckResult("system", HealthStatus.DEGRADED, f"CPU at {cpu}%")
        return HealthCheckResult("system", HealthStatus.HEALTHY, f"CPU at {cpu}%")
    
    def _check_memory(self) -> HealthCheckResult:
        """Check memory usage."""
        mem = psutil.virtual_memory()
        if mem.percent > 90:
            return HealthCheckResult("memory", HealthStatus.CRITICAL, f"Memory at {mem.percent}%")
        elif mem.percent > 80:
            return HealthCheckResult("memory", HealthStatus.DEGRADED, f"Memory at {mem.percent}%")
        return HealthCheckResult("memory", HealthStatus.HEALTHY, f"Memory at {mem.percent}%")
    
    def _check_disk(self) -> HealthCheckResult:
        """Check disk space."""
        disk = psutil.disk_usage("/")
        if disk.percent > 95:
            return HealthCheckResult("disk", HealthStatus.CRITICAL, f"Disk at {disk.percent}%")
        elif disk.percent > 85:
            return HealthCheckResult("disk", HealthStatus.DEGRADED, f"Disk at {disk.percent}%")
        return HealthCheckResult("disk", HealthStatus.HEALTHY, f"Disk at {disk.percent}%")
    
    def _check_skill_loader(self) -> HealthCheckResult:
        """Check if skill loader is functional."""
        if not self.skill_loader:
            return HealthCheckResult("skill_loader", HealthStatus.UNKNOWN, "No skill loader configured")
        
        try:
            # Try loading a core skill
            skill = self.skill_loader("skill-composability")
            if skill:
                return HealthCheckResult("skill_loader", HealthStatus.HEALTHY, "Skill loader functional")
            else:
                return HealthCheckResult("skill_loader", HealthStatus.DEGRADED, "Core skill not found")
        except Exception as e:
            return HealthCheckResult("skill_loader", HealthStatus.CRITICAL, f"Skill loader error: {e}")


def create_health_checker(config: Dict[str, Any], skill_loader: Callable = None) -> HealthChecker:
    return HealthChecker(config, skill_loader)


__all__ = ["HealthChecker", "HealthCheckResult", "HealthStatus", "create_health_checker"]