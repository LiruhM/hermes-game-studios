"""
Agent Registry - Registry of available agents
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

class AgentType(Enum):
    WORKER = "worker"
    COORDINATOR = "coordinator"
    SPECIALIST = "specialist"
    SUPERVISOR = "supervisor"

class AgentStatus(Enum):
    ACTIVE = "active"
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"

@dataclass
class Agent:
    agent_id: str
    name: str
    agent_type: AgentType
    capabilities: List[str] = field(default_factory=list)
    status: AgentStatus = AgentStatus.IDLE
    metadata: Dict[str, Any] = field(default_factory=dict)

class AgentRegistry:
    """Registry of available agents."""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.agents: Dict[str, Agent] = {}
    
    def register(self, agent: Agent) -> bool:
        """Register an agent."""
        self.agents[agent.agent_id] = agent
        return True
    
    def unregister(self, agent_id: str) -> bool:
        """Unregister an agent."""
        if agent_id in self.agents:
            del self.agents[agent_id]
            return True
        return False
    
    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get agent by ID."""
        return self.agents.get(agent_id)
    
    def find_by_capability(self, capability: str) -> List[Agent]:
        """Find agents with a specific capability."""
        return [a for a in self.agents.values() if capability in a.capabilities]
    
    def find_by_type(self, agent_type: AgentType) -> List[Agent]:
        """Find agents by type."""
        return [a for a in self.agents.values() if a.agent_type == agent_type]
    
    def get_available(self, capability: str = None) -> List[Agent]:
        """Get available agents (optionally with capability)."""
        agents = [a for a in self.agents.values() if a.status == AgentStatus.IDLE]
        if capability:
            agents = [a for a in agents if capability in a.capabilities]
        return agents
    
    def update_status(self, agent_id: str, status: AgentStatus) -> bool:
        """Update agent status."""
        if agent_id in self.agents:
            self.agents[agent_id].status = status
            return True
        return False

def create_agent_registry(config: dict = None) -> AgentRegistry:
    return AgentRegistry(config)