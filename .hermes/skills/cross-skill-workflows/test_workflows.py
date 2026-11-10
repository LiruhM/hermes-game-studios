"""
Cross-Skill Workflows v1.0 — Integration Tests
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime

from cross_skill_workflows import (
    Workflow, WorkflowStep, WorkflowInput, WorkflowStatus, StepStatus,
    WorkflowEngine, WorkflowLoader, WorkflowStateStore,
    WorkflowExecution, StepExecution, ExecutionContext,
    create_workflow, create_workflow_engine, create_workflow_loader,
    create_state_store, EventBus, MetricsCollector
)


class TestWorkflowModels:
    """Test workflow data models."""
    
    def test_workflow_creation(self):
        """Test creating a workflow from dict."""
        workflow = create_workflow(
            name="test-workflow",
            steps=[
                {"id": "step1", "skill": "skill-a", "action": "do_something", "params": {"x": 1}},
                {"id": "step2", "skill": "skill-b", "action": "do_other", "params": {"y": "{{steps.step1.outputs.result}}"}, "depends_on": ["step1"]}
            ],
            inputs=[
                {"name": "topic", "type": "string", "required": True}
            ]
        )
        
        assert workflow.name == "test-workflow"
        assert len(workflow.steps) == 2
        assert workflow.steps[0].id == "step1"
        assert workflow.steps[1].depends_on == ["step1"]
        assert len(workflow.inputs) == 1
    
    def test_topological_sort(self):
        """Test dependency resolution."""
        workflow = create_workflow(
            name="test",
            steps=[
                {"id": "a", "skill": "s", "action": "a"},
                {"id": "b", "skill": "s", "action": "b", "depends_on": ["a"]},
                {"id": "c", "skill": "s", "action": "c", "depends_on": ["a"]},
                {"id": "d", "skill": "s", "action": "d", "depends_on": ["b", "c"]}
            ]
        )
        
        levels = workflow.topological_sort()
        assert levels == [["a"], ["b", "c"], ["d"]]
    
    def test_cycle_detection(self):
        """Test cycle detection in dependencies."""
        workflow = create_workflow(
            name="test",
            steps=[
                {"id": "a", "skill": "s", "action": "a", "depends_on": ["b"]},
                {"id": "b", "skill": "s", "action": "b", "depends_on": ["a"]}
            ]
        )
        
        with pytest.raises(ValueError, match="Cycle detected"):
            workflow.topological_sort()


class TestExecutionContext:
    """Test template variable resolution."""
    
    def test_resolve_inputs(self):
        workflow = create_workflow(name="test", steps=[])
        context = ExecutionContext(workflow, {"topic": "AI", "depth": "deep"})
        
        assert context.get_param("{{inputs.topic}}") == "AI"
        assert context.get_param("{{inputs.depth}}") == "deep"
    
    def test_resolve_step_outputs(self):
        workflow = create_workflow(name="test", steps=[])
        context = ExecutionContext(workflow, {})
        context.set_step_output("research", {"papers": ["paper1", "paper2"], "count": 2})
        
        assert context.get_param("{{steps.research.outputs.papers}}") == ["paper1", "paper2"]
        assert context.get_param("{{steps.research.outputs.count}}") == 2
    
    def test_non_template_passthrough(self):
        workflow = create_workflow(name="test", steps=[])
        context = ExecutionContext(workflow, {})
        
        assert context.get_param("plain string") == "plain string"
        assert context.get_param(123) == 123
        assert context.get_param({"key": "value"}) == {"key": "value"}


class TestWorkflowLoader:
    """Test YAML workflow loading."""
    
    def test_load_from_yaml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            workflows_dir = Path(tmpdir) / "workflows"
            workflows_dir.mkdir()
            
            # Create test workflow
            workflow_yaml = """
name: test-workflow
version: "1.0"
description: Test workflow
inputs:
  - name: topic
    type: string
    required: true
steps:
  - id: step1
    skill: test-skill
    action: test-action
    params:
      query: "{{inputs.topic}}"
    outputs: [result]
"""
            (workflows_dir / "test-workflow.yaml").write_text(workflow_yaml)
            
            loader = create_workflow_loader(workflows_dir)
            workflow = loader.load("test-workflow")
            
            assert workflow.name == "test-workflow"
            assert workflow.version == "1.0"
            assert len(workflow.steps) == 1
            assert workflow.steps[0].id == "step1"
    
    def test_load_invalid_yaml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            workflows_dir = Path(tmpdir) / "workflows"
            workflows_dir.mkdir()
            
            (workflows_dir / "bad.yaml").write_text("invalid: yaml: [}")
            
            loader = create_workflow_loader(workflows_dir)
            with pytest.raises(ValueError, match="Invalid YAML"):
                loader.load_file(workflows_dir / "bad.yaml")
    
    def test_validate_dependencies(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            workflows_dir = Path(tmpdir) / "workflows"
            workflows_dir.mkdir()
            
            # Missing dependency
            workflow_yaml = """
name: test
steps:
  - id: step1
    skill: s
    action: a
    depends_on: [nonexistent]
"""
            (workflows_dir / "bad.yaml").write_text(workflow_yaml)
            
            loader = create_workflow_loader(workflows_dir)
            with pytest.raises(ValueError, match="non-existent step"):
                loader.load_file(workflows_dir / "bad.yaml")


class TestWorkflowEngine:
    """Test workflow execution engine."""
    
    def test_execute_quick_workflow(self):
        """Test simple inline workflow execution."""
        engine = create_workflow_engine()
        
        # Mock skill loader
        def mock_loader(skill_name):
            class MockSkill:
                def test_action(self, x):
                    return {"result": x * 2}
            return MockSkill()
        
        engine.set_skill_loader(mock_loader)
        
        result = engine.execute_quick(
            name="test",
            steps=[
                {"id": "step1", "skill": "mock", "action": "test_action", "params": {"x": 5}}
            ],
            inputs={}
        )
        
        assert result.status == WorkflowStatus.COMPLETED
        assert result.steps["step1"].outputs["result"] == 10
    
    def test_execute_with_dependencies(self):
        """Test workflow with step dependencies."""
        engine = create_workflow_engine()
        
        def mock_loader(skill_name):
            class MockSkill:
                def step1(self, x):
                    return {"value": x + 10}
                def step2(self, value):
                    return {"final": value * 2}
            return MockSkill()
        
        engine.set_skill_loader(mock_loader)
        
        result = engine.execute_quick(
            name="test",
            steps=[
                {"id": "step1", "skill": "mock", "action": "step1", "params": {"x": 5}},
                {"id": "step2", "skill": "mock", "action": "step2", "params": {"value": "{{steps.step1.outputs.value}}"}, "depends_on": ["step1"]}
            ],
            inputs={}
        )
        
        assert result.status == WorkflowStatus.COMPLETED
        assert result.steps["step1"].outputs["value"] == 15
        assert result.steps["step2"].outputs["final"] == 30
    
    def test_parallel_execution(self):
        """Test that independent steps run in parallel."""
        import time
        
        engine = create_workflow_engine({"max_parallel": 4})
        
        def mock_loader(skill_name):
            class MockSkill:
                def slow_action(self, x):
                    time.sleep(0.1)
                    return {"result": x}
            return MockSkill()
        
        engine.set_skill_loader(mock_loader)
        
        start = time.time()
        result = engine.execute_quick(
            name="test",
            steps=[
                {"id": "a", "skill": "mock", "action": "slow_action", "params": {"x": 1}},
                {"id": "b", "skill": "mock", "action": "slow_action", "params": {"x": 2}},
                {"id": "c", "skill": "mock", "action": "slow_action", "params": {"x": 3}}
            ],
            inputs={}
        )
        elapsed = time.time() - start
        
        assert result.status == WorkflowStatus.COMPLETED
        # Should take ~0.1s (parallel) not 0.3s (sequential)
        assert elapsed < 0.25


class TestStateStore:
    """Test workflow state persistence."""
    
    def test_save_and_load_execution(self):
        import tempfile
        import os
        from pathlib import Path
        from datetime import datetime
        
        # Use a named temp file instead of TemporaryDirectory to avoid locking issues
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        
        try:
            store = create_state_store(db_path)
            
            # Create execution
            execution = WorkflowExecution(
                workflow_id="test-123",
                workflow_name="test-workflow",
                workflow_version="1.0",
                inputs={"topic": "test"},
                status=WorkflowStatus.COMPLETED,
                started_at=datetime.now(),
                completed_at=datetime.now()
            )
            execution.steps["step1"] = StepExecution(
                step_id='step1',
                status=StepStatus.COMPLETED,
                started_at=datetime.now(),
                completed_at=datetime.now(),
                outputs={'result': 'ok'},
                error=None,
                attempt=1,
                retry_after=None
            )
            
            workflow = create_workflow(name="test-workflow", steps=[])
            
            store.save_execution(execution, workflow)
            loaded = store.load_execution("test-123")
            
            assert loaded is not None
            assert loaded.workflow_id == "test-123"
            assert loaded.workflow_name == "test-workflow"
            assert loaded.status == WorkflowStatus.COMPLETED
            assert "step1" in loaded.steps
        finally:
            if db_path.exists():
                try:
                    db_path.unlink()
                except PermissionError:
                    pass
    
    def test_list_executions(self):
        import tempfile
        import os
        from pathlib import Path
        from datetime import datetime
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        
        try:
            store = create_state_store(db_path)
            
            for i in range(3):
                execution = WorkflowExecution(
                    workflow_id=f"test-{i}",
                    workflow_name="test-workflow",
                    workflow_version="1.0",
                    inputs={},
                    status=WorkflowStatus.COMPLETED if i < 2 else WorkflowStatus.FAILED,
                    started_at=datetime.now(),
                    completed_at=datetime.now()
                )
                workflow = create_workflow(name="test-workflow", steps=[])
                store.save_execution(execution, workflow)
            
            all_execs = store.list_executions(limit=10)
            assert len(all_execs) == 3
            
            completed = store.list_executions(status=WorkflowStatus.COMPLETED, limit=10)
            assert len(completed) == 2
            
            failed = store.list_executions(status=WorkflowStatus.FAILED, limit=10)
            assert len(failed) == 1
        finally:
            if db_path.exists():
                try:
                    db_path.unlink()
                except PermissionError:
                    pass


class TestEventBus:
    """Test event system."""
    
    def test_emit_and_subscribe(self):
        bus = EventBus()
        events = []
        
        def handler(event):
            events.append(event)
        
        bus.subscribe("test_event", handler)
        bus.emit("test_event", {"key": "value"})
        
        assert len(events) == 1
        assert events[0]["type"] == "test_event"
        assert events[0]["data"]["key"] == "value"
    
    def test_event_filtering(self):
        bus = EventBus()
        
        bus.emit("type_a", {"id": 1})
        bus.emit("type_b", {"id": 2})
        bus.emit("type_a", {"id": 3})
        
        all_events = bus.get_events()
        assert len(all_events) == 3
        
        type_a = bus.get_events(event_type="type_a")
        assert len(type_a) == 2


class TestMetricsCollector:
    """Test metrics collection."""
    
    def test_workflow_metrics(self):
        collector = MetricsCollector()
        
        collector.record_workflow_start("exec-1", "workflow-a")
        collector.record_workflow_start("exec-2", "workflow-b")
        collector.record_workflow_complete("exec-1", "completed", 1000)
        collector.record_workflow_complete("exec-2", "failed", 500)
        
        summary = collector.get_summary()
        
        assert summary["workflows_started"] == 2
        assert summary["workflows_completed"] == 1
        assert summary["workflows_failed"] == 1
        assert summary["success_rate"] == 0.5
        assert summary["avg_duration_ms"] == 750


if __name__ == "__main__":
    pytest.main([__file__, "-v"])