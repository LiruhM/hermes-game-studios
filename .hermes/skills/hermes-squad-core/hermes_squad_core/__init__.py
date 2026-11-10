"""
Hermes Squad Core - Main Package
"""

from .squad import SquadManager, create_squad_manager
from .agents import AgentRegistry, create_agent_registry
from .coordination import CoordinationManager, create_coordination_manager
from .communication import CommunicationBus, create_communication_bus

__version__ = "1.0.0"
__all__ = [
    "SquadManager", "create_squad_manager",
    "AgentRegistry", "create_agent_registry",
    "CoordinationManager", "create_coordination_manager",
    "CommunicationBus", "create_communication_bus",
]

def create_hermes_squad_core(config: dict = None) -> dict:
    """Factory to create all squad core tools."""
    return {
        "squad": create_squad_manager(config),
        "agents": create_agent_registry(config),
        "coordination": create_coordination_manager(config),
        "communication": create_communication_bus(config),
    }