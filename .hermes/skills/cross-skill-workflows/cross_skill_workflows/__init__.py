"""
Cross-Skill Workflows v1.0 — Main Entry Point
Orchestration engine for multi-skill workflows.
"""

from typing import List, Optional, Dict, Any

from .models import (
    Workflow, WorkflowStep, WorkflowInput,
    WorkflowStatus, StepStatus, RetryPolicy,
    StepExecution, WorkflowExecution, ExecutionContext,
    create_workflow
)
from .engine import WorkflowEngine, create_workflow_engine
from .loader import WorkflowLoader, create_workflow_loader
from .executor import WorkflowExecutor, SkillExecutor, StepResult, create_executor
from .state import WorkflowStateStore, create_state_store
from .registry import SkillRegistry, SkillCapability, EventBus, MetricsCollector, create_skill_registry, create_event_bus, create_metrics_collector


__version__ = "1.0.0"

__all__ = [
    # Models
    "Workflow",
    "WorkflowStep",
    "WorkflowInput",
    "WorkflowStatus",
    "StepStatus",
    "RetryPolicy",
    "StepExecution",
    "WorkflowExecution",
    "ExecutionContext",
    "create_workflow",
    
    # Engine
    "WorkflowEngine",
    "create_workflow_engine",
    
    # Loader
    "WorkflowLoader",
    "create_workflow_loader",
    
    # Executor
    "WorkflowExecutor",
    "SkillExecutor",
    "StepResult",
    "create_executor",
    
    # State
    "WorkflowStateStore",
    "create_state_store",
    
    # Registry & Events
    "SkillRegistry",
    "SkillCapability",
    "EventBus",
    "MetricsCollector",
    "create_skill_registry",
    "create_event_bus",
    "create_metrics_collector",
    "create_cross_skill_workflows",
]


# Convenience function for quick workflows
def quick_workflow(
    name: str,
    steps: List[Dict[str, Any]],
    inputs: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None
) -> WorkflowExecution:
    """Execute a quick inline workflow."""
    engine = create_workflow_engine(config)
    return engine.execute_quick(name, steps, inputs)


def create_cross_skill_workflows(config: Optional[Dict[str, Any]] = None) -> WorkflowEngine:
    """Factory function to create a cross-skill workflows engine."""
    return create_workflow_engine(config)