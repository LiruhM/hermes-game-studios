"""
Squad Manager - Manage agent squads
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

class SquadStatus(Enum):
    ACTIVE = "active"
    IDLE = "idle"
    PAUSED = "paused"
    STOPPED = "stopped"

@dataclass
class SquadMember:
    agent_id: str
    role: str
    capabilities: List[str]
    status: str = "active"

@dataclass
class Squad:
    name: str
    members: List[SquadMember] = field(default_factory=list)
    status: SquadStatus = SquadStatus.IDLE
    metadata: Dict[str, Any] = field(default_factory=dict)

class SquadManager:
    """Manage agent squads."""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.squads: Dict[str, Squad] = {}
    
    def create_squad(self, name: str, members: List[Dict] = None) -> Squad:
        """Create a new squad."""
        squad = Squad(name=name)
        if members:
            for m in members:
                squad.members.append(SquadMember(
                    agent_id=m.get("agent_id", ""),
                    role=m.get("role", "worker"),
                    capabilities=m.get("capabilities", [])
                ))
        self.squads[name] = squad
        return squad
    
    def add_member(self, squad_name: str, member: SquadMember) -> bool:
        """Add member to squad."""
        if squad_name in self.squads:
            self.squads[squad_name].members.append(member)
            return True
        return False
    
    def remove_member(self, squad_name: str, agent_id: str) -> bool:
        """Remove member from squad."""
        if squad_name in self.squads:
            squad = self.squads[squad_name]
            squad.members = [m for m in squad.members if m.agent_id != agent_id]
            return True
        return False
    
    def get_squad(self, name: str) -> Optional[Squad]:
        """Get squad by name."""
        return self.squads.get(name)
    
    def list_squads(self) -> List[Squad]:
        """List all squads."""
        return list(self.squads.values())
    
    def set_status(self, squad_name: str, status: SquadStatus) -> bool:
        """Set squad status."""
        if squad_name in self.squads:
            self.squads[squad_name].status = status
            return True
        return False

def create_squad_manager(config: dict = None) -> SquadManager:
    return SquadManager(config)