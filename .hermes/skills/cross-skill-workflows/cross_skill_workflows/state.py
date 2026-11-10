"""
Cross-Skill Workflows v1.0 — State Persistence
SQLite-based state management for workflow executions.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
import uuid

from .models import Workflow, WorkflowExecution, StepExecution, WorkflowStatus, StepStatus


class WorkflowStateStore:
    """SQLite-backed state store for workflow executions."""
    
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS workflow_executions (
                    execution_id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    workflow_name TEXT NOT NULL,
                    workflow_version TEXT NOT NULL,
                    workflow_def TEXT NOT NULL,
                    inputs TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    current_level INTEGER DEFAULT 0,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                
                CREATE TABLE IF NOT EXISTS step_executions (
                    execution_id TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    outputs TEXT,
                    error TEXT,
                    attempt INTEGER DEFAULT 0,
                    retry_after TEXT,
                    PRIMARY KEY (execution_id, step_id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_executions_status ON workflow_executions(status);
                CREATE INDEX IF NOT EXISTS idx_executions_workflow ON workflow_executions(workflow_id);
                CREATE INDEX IF NOT EXISTS idx_steps_execution ON step_executions(execution_id);
            """)
    
    def save_execution(self, execution: WorkflowExecution, workflow: Workflow):
        """Save or update workflow execution state."""
        with sqlite3.connect(self.db_path) as conn:
            now = datetime.now().isoformat()
            
            # Check if exists
            cursor = conn.execute(
                "SELECT execution_id FROM workflow_executions WHERE execution_id = ?",
                (execution.workflow_id,)
            )
            exists = cursor.fetchone() is not None
            
            if exists:
                conn.execute("""
                    UPDATE workflow_executions SET
                        status = ?, completed_at = ?, current_level = ?, error = ?, updated_at = ?
                    WHERE execution_id = ?
                """, (
                    execution.status.value,
                    execution.completed_at.isoformat() if execution.completed_at else None,
                    execution.current_level,
                    execution.error,
                    now,
                    execution.workflow_id
                ))
            else:
                conn.execute("""
                    INSERT INTO workflow_executions (
                        execution_id, workflow_id, workflow_name, workflow_version,
                        workflow_def, inputs, status, started_at, completed_at,
                        current_level, error, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    execution.workflow_id,  # execution_id (PK)
                    execution.workflow_id,  # workflow_id
                    execution.workflow_name,
                    execution.workflow_version,
                    workflow.model_dump_json(),
                    json.dumps(execution.inputs),
                    execution.status.value,
                    execution.started_at.isoformat() if execution.started_at else None,
                    execution.completed_at.isoformat() if execution.completed_at else None,
                    execution.current_level,
                    execution.error,
                    now,
                    now
                ))
            
            # Save steps
            for step_id, step_exec in execution.steps.items():
                conn.execute("""
                    INSERT OR REPLACE INTO step_executions (
                        execution_id, step_id, status, started_at, completed_at,
                        outputs, error, attempt, retry_after
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    execution.workflow_id,
                    step_id,
                    step_exec.status.value,
                    step_exec.started_at.isoformat() if step_exec.started_at else None,
                    step_exec.completed_at.isoformat() if step_exec.completed_at else None,
                    json.dumps(step_exec.outputs),
                    step_exec.error,
                    step_exec.attempt,
                    step_exec.retry_after.isoformat() if step_exec.retry_after else None
                ))
    
    def load_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Load workflow execution by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            cursor = conn.execute(
                "SELECT * FROM workflow_executions WHERE execution_id = ?",
                (execution_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            
            execution = WorkflowExecution(
                workflow_id=row["execution_id"],
                workflow_name=row["workflow_name"],
                workflow_version=row["workflow_version"],
                inputs=json.loads(row["inputs"]),
                status=WorkflowStatus(row["status"]),
                started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
                completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
                current_level=row["current_level"],
                error=row["error"]
            )
            
            # Load steps
            cursor = conn.execute(
                "SELECT * FROM step_executions WHERE execution_id = ?",
                (execution_id,)
            )
            for step_row in cursor.fetchall():
                step_exec = StepExecution(
                    step_id=step_row["step_id"],
                    status=StepStatus(step_row["status"]),
                    started_at=datetime.fromisoformat(step_row["started_at"]) if step_row["started_at"] else None,
                    completed_at=datetime.fromisoformat(step_row["completed_at"]) if step_row["completed_at"] else None,
                    outputs=json.loads(step_row["outputs"]) if step_row["outputs"] else {},
                    error=step_row["error"],
                    attempt=step_row["attempt"],
                    retry_after=datetime.fromisoformat(step_row["retry_after"]) if step_row["retry_after"] else None
                )
                execution.steps[step_row["step_id"]] = step_exec
            
            return execution
    
    def list_executions(
        self,
        workflow_id: Optional[str] = None,
        status: Optional[WorkflowStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List workflow executions with filters."""
        query = "SELECT * FROM workflow_executions WHERE 1=1"
        params = []
        
        if workflow_id:
            query += " AND workflow_id = ?"
            params.append(workflow_id)
        if status:
            query += " AND status = ?"
            params.append(status.value)
        
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_latest_execution(self, workflow_id: str) -> Optional[WorkflowExecution]:
        """Get the most recent execution for a workflow."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT execution_id FROM workflow_executions WHERE workflow_id = ? ORDER BY created_at DESC LIMIT 1",
                (workflow_id,)
            )
            row = cursor.fetchone()
            if row:
                return self.load_execution(row["execution_id"])
            return None


def create_state_store(db_path: Path) -> WorkflowStateStore:
    """Factory function."""
    return WorkflowStateStore(db_path)


__all__ = ["WorkflowStateStore", "create_state_store"]