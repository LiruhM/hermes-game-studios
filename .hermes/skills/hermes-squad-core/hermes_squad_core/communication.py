"""
Communication Bus - Message passing between agents
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import uuid
from datetime import datetime
from collections import defaultdict

class MessageType(Enum):
    REQUEST = "request"
    RESPONSE = "response"
    EVENT = "event"
    BROADCAST = "broadcast"
    COMMAND = "command"

@dataclass
class Message:
    message_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    message_type: MessageType = MessageType.REQUEST
    sender: str = ""
    recipient: str = ""
    subject: str = ""
    payload: Any = None
    timestamp: datetime = field(default_factory=datetime.now)
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None

class CommunicationBus:
    """Message bus for agent communication."""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.subscriptions: Dict[str, List[str]] = defaultdict(list)  # topic -> [agent_ids]
        self.message_queue: List[Message] = []
        self.message_history: List[Message] = []
        self.handlers: Dict[str, List[callable]] = defaultdict(list)  # agent_id -> [handlers]
    
    def subscribe(self, agent_id: str, topic: str) -> bool:
        """Subscribe agent to topic."""
        if agent_id not in self.subscriptions[topic]:
            self.subscriptions[topic].append(agent_id)
            return True
        return False
    
    def unsubscribe(self, agent_id: str, topic: str) -> bool:
        """Unsubscribe agent from topic."""
        if agent_id in self.subscriptions[topic]:
            self.subscriptions[topic].remove(agent_id)
            return True
        return False
    
    def publish(self, message: Message) -> List[str]:
        """Publish message to topic/recipient."""
        self.message_history.append(message)
        
        delivered = []
        if message.recipient:
            # Direct message
            self.message_queue.append(message)
            delivered.append(message.recipient)
        else:
            # Broadcast to topic subscribers
            for agent_id in self.subscriptions.get(message.subject, []):
                self.message_queue.append(message)
                delivered.append(agent_id)
        
        return delivered
    
    def receive(self, agent_id: str, limit: int = 10) -> List[Message]:
        """Receive messages for agent."""
        messages = []
        remaining = []
        
        for msg in self.message_queue:
            if msg.recipient == agent_id or msg.recipient == "":
                messages.append(msg)
            else:
                remaining.append(msg)
        
        self.message_queue = remaining
        return messages[:limit]
    
    def register_handler(self, agent_id: str, handler: callable):
        """Register message handler for agent."""
        self.handlers[agent_id].append(handler)
    
    def get_history(self, agent_id: str = None, limit: int = 100) -> List[Message]:
        """Get message history."""
        if agent_id:
            return [m for m in self.message_history if m.sender == agent_id or m.recipient == agent_id][-limit:]
        return self.message_history[-limit:]

def create_communication_bus(config: dict = None) -> CommunicationBus:
    return CommunicationBus(config)