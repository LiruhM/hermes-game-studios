"""
Cross-Skill Workflows v1.0 — Core Models
Pydantic models for workflow definition and execution.
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List, Set
from enum import Enum
from datetime import datetime
from dataclasses import dataclass, field
import uuid


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WAITING_APPROVAL = "waiting_approval"


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class RetryPolicy(BaseModel):
    max_attempts: int = 3
    backoff_seconds: List[int] = [5, 30, 120]
    exponential: bool = True


class WorkflowStep(BaseModel):
    """Single step in a workflow."""
    id: str = Field(..., min_length=1)
    skill: str = Field(..., min_length=1)
    action: str = Field(..., min_length=1)
    params: Dict[str, Any] = Field(default_factory=dict)
    depends_on: List[str] = Field(default_factory=list)
    outputs: List[str] = Field(default_factory=list)
    timeout: int = 300
    retry: Optional[RetryPolicy] = None
    condition: Optional[str] = None  # Jinja2 condition for conditional execution
    approval_required: bool = False
    description: Optional[str] = None


class WorkflowInput(BaseModel):
    """Workflow input parameter definition."""
    name: str
    type: str = "string"
    required: bool = True
    default: Any = None
    enum: Optional[List[str]] = None
    description: Optional[str] = None


class Workflow(BaseModel):
    """Complete workflow definition."""
    name: str = Field(..., min_length=1)
    version: str = "1.0"
    description: str = ""
    inputs: List[WorkflowInput] = Field(default_factory=list)
    steps: List[WorkflowStep] = Field(default_factory=list)
    execution: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    def get_step(self, step_id: str) -> Optional[WorkflowStep]:
        for step in self.steps:
            if step.id == step_id:
                return step
        return None

    def get_dependencies(self, step_id: str) -> List[str]:
        step = self.get_step(step_id)
        return step.depends_on if step else []

    def get_dependents(self, step_id: str) -> List[str]:
        dependents = []
        for step in self.steps:
            if step_id in step.depends_on:
                dependents.append(step.id)
        return dependents

    def topological_sort(self) -> List[List[str]]:
        """Return steps grouped by execution level (parallel groups)."""
        from collections import defaultdict, deque
        
        in_degree = {step.id: 0 for step in self.steps}
        graph = defaultdict(list)
        
        for step in self.steps:
            for dep in step.depends_on:
                graph[dep].append(step.id)
                in_degree[step.id] += 1
        
        levels = []
        queue = deque([sid for sid, deg in in_degree.items() if deg == 0])
        
        while queue:
            level = []
            for _ in range(len(queue)):
                node = queue.popleft()
                level.append(node)
                for neighbor in graph[node]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)
            if level:
                levels.append(level)
        
        # Check for cycles
        total_sorted = sum(len(l) for l in levels)
        if total_sorted != len(self.steps):
            raise ValueError("Cycle detected in workflow dependencies")
        
        return levels


@dataclass
class StepExecution:
    """Runtime state of a step execution."""
    step_id: str
    status: StepStatus = StepStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    outputs: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    attempt: int = 0
    retry_after: Optional[datetime] = None


@dataclass
class WorkflowExecution:
    """Runtime state of a workflow execution."""
    workflow_id: str
    workflow_name: str
    workflow_version: str
    inputs: Dict[str, Any]
    status: WorkflowStatus = WorkflowStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    steps: Dict[str, StepExecution] = field(default_factory=dict)
    current_level: int = 0
    error: Optional[str] = None


class ExecutionContext:
    """Context passed between steps during execution."""
    def __init__(self, workflow: Workflow, inputs: Dict[str, Any]):
        self.workflow = workflow
        self.inputs = inputs
        self.step_outputs: Dict[str, Dict[str, Any]] = {}
        self.execution_id = str(uuid.uuid4())
        self.started_at = datetime.now()
    
    def get_param(self, template: Any) -> Any:
        """Resolve template variables like {{steps.research.outputs.papers}}."""
        if not isinstance(template, str):
            return template
        
        import re
        import json
        
        # Check if the entire template is a single variable reference
        single_var_match = re.match(r'^\{\{([^}]+)\}\}$', template.strip())
        if single_var_match:
            path = single_var_match.group(1).strip()
            parts = path.split('.')
            if parts[0] == 'inputs':
                return self._get_nested(self.inputs, parts[1:])
            elif parts[0] == 'steps':
                if len(parts) >= 4 and parts[2] == 'outputs':
                    step_id = parts[1]
                    output_key = parts[3]
                    return self.step_outputs.get(step_id, {}).get(output_key)
            return template
        
        # For mixed content, use re.sub with string conversion
        def replace(match):
            path = match.group(1).strip()
            parts = path.split('.')
            if parts[0] == 'inputs':
                value = self._get_nested(self.inputs, parts[1:])
            elif parts[0] == 'steps':
                if len(parts) >= 4 and parts[2] == 'outputs':
                    step_id = parts[1]
                    output_key = parts[3]
                    value = self.step_outputs.get(step_id, {}).get(output_key)
                else:
                    value = None
            else:
                value = None
            
            # Convert to string for replacement
            if value is None:
                return match.group(0)
            elif isinstance(value, (dict, list)):
                return json.dumps(value, ensure_ascii=False)
            else:
                return str(value)
        
        return re.sub(r'\{\{([^}]+)\}\}', replace, template)
    
    def _get_nested(self, obj: Dict, keys: List[str]) -> Any:
        for key in keys:
            if isinstance(obj, dict) and key in obj:
                obj = obj[key]
            else:
                return None
        return obj
    
    def set_step_output(self, step_id: str, outputs: Dict[str, Any]):
        self.step_outputs[step_id] = outputs


# ============================================================
# FACTORY FUNCTIONS
# ============================================================

def create_workflow(
    name: str,
    steps: List[Dict[str, Any]],
    inputs: Optional[List[Dict[str, Any]]] = None,
    **kwargs
) -> Workflow:
    """Create a workflow from simple dict definitions."""
    workflow_steps = [WorkflowStep(**s) for s in steps]
    workflow_inputs = [WorkflowInput(**i) for i in (inputs or [])]
    return Workflow(
        name=name,
        steps=workflow_steps,
        inputs=workflow_inputs,
        **kwargs
    )


__all__ = [
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
]