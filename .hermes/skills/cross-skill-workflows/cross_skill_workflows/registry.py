"""
Cross-Skill Workflows v1.0 — Registry & Events
Skill capability registry and event system for observability.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, asdict
from collections import defaultdict


@dataclass
class SkillCapability:
    """A capability provided by a skill."""
    skill: str
    action: str
    description: str
    params: Dict[str, Any]
    returns: Dict[str, Any]
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class SkillRegistry:
    """Registry of available skills and their capabilities for workflow planning."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.skills: Dict[str, Any] = {}  # skill_name -> skill_instance
        self.capabilities: Dict[str, List[SkillCapability]] = defaultdict(list)
        self._discover_skills()
    
    def _discover_skills(self):
        """Discover available skills from config."""
        skill_names = self.config.get("skill_registry", [])
        for skill_name in skill_names:
            try:
                # This would be populated by the host application
                pass
            except Exception:
                pass
    
    def register_skill(self, skill_name: str, skill_instance: Any, capabilities: List[SkillCapability] = None):
        """Register a skill with its capabilities."""
        self.skills[skill_name] = skill_instance
        if capabilities:
            for cap in capabilities:
                self.capabilities[skill_name].append(cap)
    
    def get_skill(self, skill_name: str) -> Optional[Any]:
        """Get skill instance."""
        return self.skills.get(skill_name)
    
    def find_skills_for_action(self, action: str) -> List[str]:
        """Find skills that can perform an action."""
        matching = []
        for skill_name, caps in self.capabilities.items():
            for cap in caps:
                if cap.action == action:
                    matching.append(skill_name)
                    break
        return matching
    
    def get_capability(self, skill_name: str, action: str) -> Optional[SkillCapability]:
        """Get capability for a skill action."""
        for cap in self.capabilities.get(skill_name, []):
            if cap.action == action:
                return cap
        return None
    
    def list_capabilities(self) -> Dict[str, List[Dict[str, Any]]]:
        """List all capabilities."""
        return {
            skill: [asdict(cap) for cap in caps]
            for skill, caps in self.capabilities.items()
        }


class EventBus:
    """Simple event bus for workflow observability."""
    
    def __init__(self):
        self.handlers: Dict[str, List[Callable]] = defaultdict(list)
        self.event_log: List[Dict[str, Any]] = []
        self.max_log_size = 1000
    
    def subscribe(self, event_type: str, handler: Callable):
        """Subscribe to event type."""
        self.handlers[event_type].append(handler)
    
    def emit(self, event_type: str, data: Dict[str, Any]):
        """Emit event to all handlers."""
        event = {
            "type": event_type,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }
        
        # Log event
        self.event_log.append(event)
        if len(self.event_log) > self.max_log_size:
            self.event_log = self.event_log[-self.max_log_size:]
        
        # Call handlers
        for handler in self.handlers.get(event_type, []):
            try:
                handler(event)
            except Exception:
                pass
    
    def get_events(
        self,
        event_type: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get filtered events."""
        events = self.event_log
        if event_type:
            events = [e for e in events if e["type"] == event_type]
        if since:
            events = [e for e in events if datetime.fromisoformat(e["timestamp"]) >= since]
        return events[-limit:]


class MetricsCollector:
    """Collect workflow execution metrics."""
    
    def __init__(self):
        self.metrics = defaultdict(list)
    
    def record_workflow_start(self, execution_id: str, workflow_name: str):
        self.metrics["workflow_starts"].append({
            "execution_id": execution_id,
            "workflow": workflow_name,
            "timestamp": datetime.now().isoformat()
        })
    
    def record_workflow_complete(self, execution_id: str, status: str, duration_ms: int):
        self.metrics["workflow_completions"].append({
            "execution_id": execution_id,
            "status": status,
            "duration_ms": duration_ms,
            "timestamp": datetime.now().isoformat()
        })
    
    def record_step_complete(self, execution_id: str, step_id: str, duration_ms: int):
        self.metrics["step_completions"].append({
            "execution_id": execution_id,
            "step_id": step_id,
            "duration_ms": duration_ms,
            "timestamp": datetime.now().isoformat()
        })
    
    def record_step_failed(self, execution_id: str, step_id: str, error: str, attempt: int):
        self.metrics["step_failures"].append({
            "execution_id": execution_id,
            "step_id": step_id,
            "error": error,
            "attempt": attempt,
            "timestamp": datetime.now().isoformat()
        })
    
    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        starts = len(self.metrics["workflow_starts"])
        completions = self.metrics["workflow_completions"]
        successes = [c for c in completions if c["status"] == "completed"]
        failures = [c for c in completions if c["status"] == "failed"]
        
        avg_duration = 0
        if completions:
            avg_duration = sum(c["duration_ms"] for c in completions) / len(completions)
        
        return {
            "workflows_started": starts,
            "workflows_completed": len(successes),
            "workflows_failed": len(failures),
            "success_rate": len(successes) / len(completions) if completions else 0,
            "avg_duration_ms": avg_duration,
            "total_steps_completed": len(self.metrics["step_completions"]),
            "total_steps_failed": len(self.metrics["step_failures"])
        }


def create_skill_registry(config: Dict[str, Any]) -> SkillRegistry:
    return SkillRegistry(config)


def create_event_bus() -> EventBus:
    return EventBus()


def create_metrics_collector() -> MetricsCollector:
    return MetricsCollector()


__all__ = [
    "SkillRegistry",
    "SkillCapability",
    "EventBus",
    "MetricsCollector",
    "create_skill_registry",
    "create_event_bus",
    "create_metrics_collector"
]