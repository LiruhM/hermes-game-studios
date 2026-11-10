"""
Cross-Skill Workflows v1.0 — YAML Loader
Load workflows from YAML files with validation.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from .models import Workflow, WorkflowStep, WorkflowInput


class WorkflowLoader:
    """Load and validate workflows from YAML files."""
    
    def __init__(self, workflows_dir: Path):
        self.workflows_dir = Path(workflows_dir)
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, Workflow] = {}
    
    def load(self, name: str, use_cache: bool = True) -> Workflow:
        """Load workflow by name (filename without extension)."""
        if use_cache and name in self._cache:
            return self._cache[name]
        
        # Try multiple extensions
        for ext in [".yaml", ".yml"]:
            path = self.workflows_dir / f"{name}{ext}"
            if path.exists():
                return self.load_file(path, use_cache)
        
        raise FileNotFoundError(f"Workflow not found: {name}")
    
    def load_file(self, path: Path, use_cache: bool = True) -> Workflow:
        """Load workflow from file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Workflow file not found: {path}")
        
        content = path.read_text(encoding="utf-8")
        return self.load_content(content, source_path=path, use_cache=use_cache)
    
    def load_content(
        self,
        content: str,
        source_path: Optional[Path] = None,
        use_cache: bool = True
    ) -> Workflow:
        """Load workflow from YAML string."""
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML: {e}")
        
        if not data:
            raise ValueError("Empty workflow definition")
        
        # Validate required fields
        if "name" not in data:
            raise ValueError("Workflow must have a 'name' field")
        
        # Parse steps
        steps = []
        for i, step_data in enumerate(data.get("steps", [])):
            try:
                step = WorkflowStep(**step_data)
                steps.append(step)
            except Exception as e:
                raise ValueError(f"Invalid step {i} ({step_data.get('id', 'unknown')}): {e}")
        
        # Parse inputs
        inputs = []
        for i, input_data in enumerate(data.get("inputs", [])):
            try:
                inp = WorkflowInput(**input_data)
                inputs.append(inp)
            except Exception as e:
                raise ValueError(f"Invalid input {i}: {e}")
        
        workflow = Workflow(
            name=data["name"],
            version=data.get("version", "1.0"),
            description=data.get("description", ""),
            inputs=inputs,
            steps=steps,
            execution=data.get("execution", {}),
            tags=data.get("tags", [])
        )
        
        # Validate workflow
        self._validate_workflow(workflow)
        
        if use_cache and source_path:
            self._cache[str(source_path)] = workflow
        
        return workflow
    
    def _validate_workflow(self, workflow: Workflow):
        """Validate workflow structure."""
        # Check for duplicate step IDs
        step_ids = [s.id for s in workflow.steps]
        if len(step_ids) != len(set(step_ids)):
            duplicates = [sid for sid in step_ids if step_ids.count(sid) > 1]
            raise ValueError(f"Duplicate step IDs: {duplicates}")
        
        # Check all dependencies exist
        for step in workflow.steps:
            for dep in step.depends_on:
                if not any(s.id == dep for s in workflow.steps):
                    raise ValueError(f"Step '{step.id}' depends on non-existent step: {dep}")
        
        # Check for cycles (via topological sort)
        try:
            workflow.topological_sort()
        except ValueError as e:
            raise ValueError(f"Workflow validation failed: {e}")
    
    def list_workflows(self) -> List[Dict[str, Any]]:
        """List all available workflow files."""
        workflows = []
        for ext in [".yaml", ".yml"]:
            for path in self.workflows_dir.glob(f"*{ext}"):
                try:
                    workflow = self.load_file(path, use_cache=False)
                    workflows.append({
                        "name": workflow.name,
                        "version": workflow.version,
                        "description": workflow.description,
                        "path": str(path),
                        "step_count": len(workflow.steps),
                        "tags": workflow.tags
                    })
                except Exception as e:
                    workflows.append({
                        "name": path.stem,
                        "path": str(path),
                        "error": str(e)
                    })
        return workflows
    
    def create_example_workflow(self, name: str) -> Path:
        """Create an example workflow file."""
        example = f"""name: {name}
version: "1.0"
description: "Example workflow - customize this"
inputs:
  - name: topic
    type: string
    required: true
    description: "Topic to process"

steps:
  - id: step1
    skill: research-tools
    action: search
    params:
      query: "{{inputs.topic}}"
      limit: 5
    outputs: [results]
    timeout: 60

  - id: step2
    skill: productivity-tools
    action: create_note
    params:
      content: "{{steps.step1.outputs.results}}"
    depends_on: [step1]
    outputs: [note_path]

execution:
  parallel_groups:
    - [step1]
    - [step2]
"""
        path = self.workflows_dir / f"{name}.yaml"
        path.write_text(example, encoding="utf-8")
        return path


def create_workflow_loader(workflows_dir: Path) -> WorkflowLoader:
    """Factory function."""
    return WorkflowLoader(workflows_dir)


__all__ = ["WorkflowLoader", "create_workflow_loader"]