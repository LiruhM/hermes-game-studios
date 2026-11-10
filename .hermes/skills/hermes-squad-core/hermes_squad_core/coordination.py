"""
Coordination Manager - Task coordination between agents
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import uuid
from datetime import datetime

class TaskStatus(Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

@dataclass
class Task:
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    description: str = ""
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    assignee: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    assigned_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Any = None
    error: Optional[str] = None

class CoordinationManager:
    """Coordinate tasks between agents."""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.tasks: Dict[str, Task] = {}
    
    def create_task(self, name: str, description: str = "", 
                    priority: TaskPriority = TaskPriority.NORMAL,
                    assignee: str = None,
                    dependencies: List[str] = None) -> Task:
        """Create a new task."""
        task = Task(
            name=name,
            description=description,
            priority=priority,
            assignee=assignee,
            dependencies=dependencies or []
        )
        self.tasks[task.task_id] = task
        return task
    
    def assign_task(self, task_id: str, agent_id: str) -> bool:
        """Assign task to agent."""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.assignee = agent_id
            task.status = TaskStatus.ASSIGNED
            task.assigned_at = datetime.now()
            return True
        return False
    
    def start_task(self, task_id: str) -> bool:
        """Start task execution."""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            if task.status in [TaskStatus.ASSIGNED, TaskStatus.PENDING]:
                task.status = TaskStatus.IN_PROGRESS
                return True
        return False
    
    def complete_task(self, task_id: str, result: Any = None) -> bool:
        """Complete a task."""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = result
            return True
        return False
    
    def fail_task(self, task_id: str, error: str) -> bool:
        """Mark task as failed."""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.status = TaskStatus.FAILED
            task.error = error
            task.completed_at = datetime.now()
            return True
        return False
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        return self.tasks.get(task_id)
    
    def get_pending_tasks(self, agent_id: str = None) -> List[Task]:
        """Get pending tasks."""
        tasks = [t for t in self.tasks.values() if t.status == TaskStatus.PENDING]
        if agent_id:
            tasks = [t for t in tasks if t.assignee == agent_id]
        return tasks
    
    def get_task_dependencies(self, task_id: str) -> List[Task]:
        """Get task dependencies."""
        task = self.tasks.get(task_id)
        if not task:
            return []
        return [self.tasks[dep_id] for dep_id in task.dependencies if dep_id in self.tasks]

def create_coordination_manager(config: dict = None) -> CoordinationManager:
    return CoordinationManager(config)