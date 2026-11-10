"""
Cross-Skill Workflows v1.0 — Main Engine & Loader
Entry point for workflow orchestration.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime

from .models import Workflow, WorkflowStep, WorkflowInput, WorkflowExecution, WorkflowStatus
from .state import WorkflowStateStore, create_state_store
from .executor import WorkflowExecutor, create_executor


class WorkflowEngine:
    """Main workflow orchestration engine."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.workflows_dir = Path(self.config.get("workflows_dir", "workflows"))
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
        
        # State store
        state_db = Path(self.config.get("state_db", "90-Sistema/_data/workflow-state.db"))
        self.state_store = create_state_store(state_db)
        
        # Skill loader (to be implemented by host)
        self.skill_loader: Optional[Callable[[str], Any]] = None
        
        # Executor
        self.executor = create_executor(
            skill_loader=self._load_skill,
            state_store=self.state_store,
            max_parallel=self.config.get("max_parallel", 4),
            default_timeout=self.config.get("default_timeout", 300),
            event_emitter=self._emit_event
        )
        
        # Event handlers
        self.event_handlers: Dict[str, List[Callable]] = {}
    
    def set_skill_loader(self, loader: Callable[[str], Any]):
        """Set the skill loader function."""
        self.skill_loader = loader
        self.executor.skill_executor.skill_loader = loader
    
    def _load_skill(self, skill_name: str):
        """Load a skill by name."""
        if self.skill_loader:
            return self.skill_loader(skill_name)
        return None
    
    def _emit_event(self, event_type: str, data: Dict[str, Any]):
        """Emit event to registered handlers."""
        for handler in self.event_handlers.get(event_type, []):
            try:
                handler(data)
            except Exception:
                pass
    
    def on_event(self, event_type: str, handler: Callable):
        """Register event handler."""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
    
    def load_workflow(self, path: Path) -> Workflow:
        """Load workflow from YAML file."""
        path = Path(path)
        if not path.exists():
            # Try in workflows dir
            path = self.workflows_dir / path
        if not path.exists():
            raise FileNotFoundError(f"Workflow not found: {path}")
        
        content = path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        
        # Parse steps
        steps = [WorkflowStep(**s) for s in data.get("steps", [])]
        inputs = [WorkflowInput(**i) for i in data.get("inputs", [])]
        
        return Workflow(
            name=data["name"],
            version=data.get("version", "1.0"),
            description=data.get("description", ""),
            inputs=inputs,
            steps=steps,
            execution=data.get("execution", {}),
            tags=data.get("tags", [])
        )
    
    def execute(
        self,
        workflow: Workflow,
        inputs: Dict[str, Any],
        execution_id: Optional[str] = None
    ) -> WorkflowExecution:
        """Execute a workflow."""
        # Validate inputs
        for inp in workflow.inputs:
            if inp.required and inp.name not in inputs:
                if inp.default is not None:
                    inputs[inp.name] = inp.default
                else:
                    raise ValueError(f"Required input missing: {inp.name}")
        
        return self.executor.execute(workflow, inputs)
    
    def execute_from_file(
        self,
        workflow_path: Path,
        inputs: Dict[str, Any]
    ) -> WorkflowExecution:
        """Load and execute workflow from file."""
        workflow = self.load_workflow(workflow_path)
        return self.execute(workflow, inputs)
    
    def execute_quick(
        self,
        name: str,
        steps: List[Dict[str, Any]],
        inputs: Dict[str, Any]
    ) -> WorkflowExecution:
        """Execute a quick inline workflow."""
        workflow_steps = [WorkflowStep(**s) for s in steps]
        workflow = Workflow(name=name, steps=workflow_steps)
        return self.execute(workflow, inputs)
    
    def get_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Get execution by ID."""
        return self.state_store.load_execution(execution_id)
    
    def list_executions(
        self,
        workflow_name: Optional[str] = None,
        status: Optional[WorkflowStatus] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List workflow executions."""
        return self.state_store.list_executions(
            workflow_id=workflow_name,
            status=status,
            limit=limit
        )
    
    def resume_execution(self, execution_id: str) -> WorkflowExecution:
        """Resume a paused/failed execution."""
        execution = self.state_store.load_execution(execution_id)
        if not execution:
            raise ValueError(f"Execution not found: {execution_id}")
        
        # Reset failed/running steps to pending
        for step_exec in execution.steps.values():
            if step_exec.status in [StepStatus.FAILED, StepStatus.RUNNING]:
                step_exec.status = StepStatus.PENDING
                step_exec.error = None
        
        execution.status = WorkflowStatus.RUNNING
        execution.error = None
        
        # Reload workflow definition
        workflow_data = self.state_store.db_path  # This would need the workflow def
        # For now, just re-execute from current level
        return self.executor.execute(execution.workflow, execution.inputs)
    
    def cancel_execution(self, execution_id: str) -> bool:
        """Cancel a running execution."""
        execution = self.state_store.load_execution(execution_id)
        if not execution or execution.status not in [WorkflowStatus.RUNNING, WorkflowStatus.PENDING]:
            return False
        
        execution.status = WorkflowStatus.CANCELLED
        execution.completed_at = datetime.now()
        self.state_store.save_execution(execution, execution.workflow)
        return True


def create_workflow_engine(config: Optional[Dict[str, Any]] = None) -> WorkflowEngine:
    """Factory function."""
    return WorkflowEngine(config)


__all__ = ["WorkflowEngine", "create_workflow_engine"]