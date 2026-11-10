"""
Cross-Skill Workflows v1.0 — DAG Executor
Parallel execution engine with dependency resolution.
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

from .models import (
    Workflow, WorkflowStep, WorkflowExecution, StepExecution,
    WorkflowStatus, StepStatus, ExecutionContext
)
from .state import WorkflowStateStore


@dataclass
class StepResult:
    """Result of a step execution."""
    step_id: str
    success: bool
    outputs: Dict[str, Any]
    error: Optional[str] = None
    duration_ms: int = 0


class SkillExecutor:
    """Executes a single skill action."""
    
    def __init__(self, skill_loader_func: Callable[[str], Any]):
        self.skill_loader = skill_loader_func
        self._skill_cache: Dict[str, Any] = {}
    
    def get_skill(self, skill_name: str):
        if skill_name not in self._skill_cache:
            self._skill_cache[skill_name] = self.skill_loader(skill_name)
        return self._skill_cache[skill_name]
    
    def execute(self, skill_name: str, action: str, params: Dict[str, Any]) -> StepResult:
        """Execute a skill action."""
        start = time.time()
        try:
            skill = self.get_skill(skill_name)
            if not skill:
                return StepResult(
                    step_id="",
                    success=False,
                    outputs={},
                    error=f"Skill not found: {skill_name}"
                )
            
            # Try to call the action
            if hasattr(skill, action):
                method = getattr(skill, action)
                result = method(**params)
            elif hasattr(skill, 'execute'):
                result = skill.execute(action, params)
            else:
                return StepResult(
                    step_id="",
                    success=False,
                    outputs={},
                    error=f"Action '{action}' not found on skill '{skill_name}'"
                )
            
            duration = int((time.time() - start) * 1000)
            
            # Normalize result to dict
            if isinstance(result, dict):
                outputs = result
            elif hasattr(result, '__dict__'):
                outputs = result.__dict__
            else:
                outputs = {"result": result}
            
            return StepResult(
                step_id="",
                success=True,
                outputs=outputs,
                duration_ms=duration
            )
            
        except Exception as e:
            duration = int((time.time() - start) * 1000)
            return StepResult(
                step_id="",
                success=False,
                outputs={},
                error=str(e),
                duration_ms=duration
            )


class WorkflowExecutor:
    """Executes workflows with DAG-based parallelism."""
    
    def __init__(
        self,
        skill_loader: Callable[[str], Any],
        state_store: Optional[WorkflowStateStore] = None,
        max_parallel: int = 4,
        default_timeout: int = 300,
        event_emitter: Optional[Callable] = None
    ):
        self.skill_executor = SkillExecutor(skill_loader)
        self.state_store = state_store
        self.max_parallel = max_parallel
        self.default_timeout = default_timeout
        self.event_emitter = event_emitter
        self._running = False
    
    def _emit(self, event_type: str, data: Dict[str, Any]):
        """Emit event for observability."""
        if self.event_emitter:
            try:
                self.event_emitter(event_type, data)
            except Exception:
                pass
    
    def execute(self, workflow: Workflow, inputs: Dict[str, Any]) -> WorkflowExecution:
        """Execute a workflow synchronously."""
        execution_id = f"{workflow.name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        execution = WorkflowExecution(
            workflow_id=execution_id,
            workflow_name=workflow.name,
            workflow_version=workflow.version,
            inputs=inputs,
            status=WorkflowStatus.RUNNING,
            started_at=datetime.now()
        )
        
        # Initialize step executions
        for step in workflow.steps:
            execution.steps[step.id] = StepExecution(step_id=step.id)
        
        # Save initial state
        if self.state_store:
            self.state_store.save_execution(execution, workflow)
        
        self._emit("workflow_started", {
            "execution_id": execution_id,
            "workflow": workflow.name,
            "inputs": inputs
        })
        
        try:
            # Get execution levels (parallel groups)
            levels = workflow.topological_sort()
            
            for level_idx, level_steps in enumerate(levels):
                execution.current_level = level_idx
                
                # Check if workflow was cancelled
                if execution.status == WorkflowStatus.CANCELLED:
                    break
                
                # Execute level in parallel
                self._execute_level(workflow, execution, level_steps)
                
                # Save progress
                if self.state_store:
                    self.state_store.save_execution(execution, workflow)
                
                # Check for failures
                failed = [s for s in level_steps if execution.steps[s].status == StepStatus.FAILED]
                if failed:
                    execution.status = WorkflowStatus.FAILED
                    execution.completed_at = datetime.now()
                    execution.error = f"Steps failed: {', '.join(failed)}"
                    break
            
            if execution.status == WorkflowStatus.RUNNING:
                execution.status = WorkflowStatus.COMPLETED
                execution.completed_at = datetime.now()
            
        except Exception as e:
            execution.status = WorkflowStatus.FAILED
            execution.completed_at = datetime.now()
            execution.error = str(e)
        
        # Final save
        if self.state_store:
            self.state_store.save_execution(execution, workflow)
        
        self._emit("workflow_completed", {
            "execution_id": execution_id,
            "workflow": workflow.name,
            "status": execution.status.value,
            "duration_ms": int((execution.completed_at - execution.started_at).total_seconds() * 1000) if execution.completed_at else 0
        })
        
        return execution
    
    def _execute_level(self, workflow: Workflow, execution: WorkflowExecution, step_ids: List[str]):
        """Execute a level of steps in parallel."""
        if not step_ids:
            return
        
        self._emit("level_started", {
            "execution_id": execution.workflow_id,
            "level": execution.current_level,
            "steps": step_ids
        })
        
        with ThreadPoolExecutor(max_workers=min(self.max_parallel, len(step_ids))) as executor:
            futures = {}
            
            for step_id in step_ids:
                step = workflow.get_step(step_id)
                step_exec = execution.steps[step_id]
                
                # Check condition
                if step.condition:
                    context = ExecutionContext(workflow, execution.inputs)
                    context.step_outputs = {k: v.outputs for k, v in execution.steps.items()}
                    try:
                        if not eval(step.condition, {"context": context}):
                            step_exec.status = StepStatus.SKIPPED
                            continue
                    except Exception:
                        step_exec.status = StepStatus.SKIPPED
                        continue
                
                step_exec.status = StepStatus.RUNNING
                step_exec.started_at = datetime.now()
                step_exec.attempt += 1
                
                # Prepare params with template resolution
                context = ExecutionContext(workflow, execution.inputs)
                context.step_outputs = {k: v.outputs for k, v in execution.steps.items()}
                resolved_params = self._resolve_params(step.params, context)
                
                future = executor.submit(
                    self.skill_executor.execute,
                    step.skill,
                    step.action,
                    resolved_params
                )
                futures[future] = (step_id, step, step_exec)
            
            # Collect results
            for future in as_completed(futures):
                step_id, step, step_exec = futures[future]
                
                try:
                    result = future.result(timeout=step.timeout or self.default_timeout)
                    
                    if result.success:
                        step_exec.status = StepStatus.COMPLETED
                        step_exec.outputs = result.outputs
                        execution.steps[step_id] = step_exec
                        
                        self._emit("step_completed", {
                            "execution_id": execution.workflow_id,
                            "step_id": step_id,
                            "outputs": result.outputs,
                            "duration_ms": result.duration_ms
                        })
                    else:
                        step_exec.status = StepStatus.FAILED
                        step_exec.error = result.error
                        execution.steps[step_id] = step_exec
                        
                        self._emit("step_failed", {
                            "execution_id": execution.workflow_id,
                            "step_id": step_id,
                            "error": result.error,
                            "attempt": step_exec.attempt
                        })
                        
                        # Retry logic
                        if step.retry and step_exec.attempt < step.retry.max_attempts:
                            self._schedule_retry(execution, step, step_exec, futures, executor)
                
                except Exception as e:
                    step_exec.status = StepStatus.FAILED
                    step_exec.error = str(e)
                    execution.steps[step_id] = step_exec
                    
                    self._emit("step_failed", {
                        "execution_id": execution.workflow_id,
                        "step_id": step_id,
                        "error": str(e),
                        "attempt": step_exec.attempt
                    })
        
        self._emit("level_completed", {
            "execution_id": execution.workflow_id,
            "level": execution.current_level,
            "steps": step_ids
        })
    
    def _resolve_params(self, params: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """Resolve template variables in params."""
        resolved = {}
        for key, value in params.items():
            resolved[key] = context.get_param(value)
        return resolved
    
    def _schedule_retry(
        self,
        execution: WorkflowExecution,
        step: WorkflowStep,
        step_exec: StepExecution,
        futures: Dict,
        executor: ThreadPoolExecutor
    ):
        """Schedule a retry for a failed step."""
        backoff = step.retry.backoff_seconds[min(step_exec.attempt - 1, len(step.retry.backoff_seconds) - 1)]
        step_exec.retry_after = datetime.now().replace(microsecond=0)
        
        def retry():
            time.sleep(backoff)
            step_exec.attempt += 1
            step_exec.started_at = datetime.now()
            
            context = ExecutionContext(execution.workflow, execution.inputs)
            context.step_outputs = {k: v.outputs for k, v in execution.steps.items()}
            resolved_params = self._resolve_params(step.params, context)
            
            result = self.skill_executor.execute(step.skill, step.action, resolved_params)
            
            if result.success:
                step_exec.status = StepStatus.COMPLETED
                step_exec.outputs = result.outputs
            else:
                step_exec.status = StepStatus.FAILED
                step_exec.error = result.error
        
        executor.submit(retry)


def create_executor(
    skill_loader: Callable[[str], Any],
    state_store: Optional[WorkflowStateStore] = None,
    max_parallel: int = 4,
    default_timeout: int = 300,
    event_emitter: Optional[Callable] = None
) -> WorkflowExecutor:
    """Factory function."""
    return WorkflowExecutor(
        skill_loader=skill_loader,
        state_store=state_store,
        max_parallel=max_parallel,
        default_timeout=default_timeout,
        event_emitter=event_emitter
    )


__all__ = ["WorkflowExecutor", "SkillExecutor", "StepResult", "create_executor"]