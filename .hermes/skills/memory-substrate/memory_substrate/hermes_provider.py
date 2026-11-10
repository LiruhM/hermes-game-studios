"""
HermesProvider - Adapts pixel-agents HookProvider interface for Hermes ecosystem.
Connects to Supervisor JSON-RPC (port 3120) and Memory Substrate REST (port 8767).
Maps Hermes agents (CEO, Dev, DevOps, Researcher, Reviewer, Watchdog) to NPC entities.
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from pathlib import Path

import aiohttp

# Configuration
SUPERVISOR_URL = "http://127.0.0.1:3120/rpc"
MEMORY_SUBSTRATE_URL = "http://127.0.0.1:8767"

# Setup logging
LOG_DIR = Path.home() / "AppData" / "Local" / "hermes" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "hermes_provider.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("hermes_provider")


class AgentRole(Enum):
    """Hermes agent roles mapped to NPC types."""
    CEO = "ceo"
    DEV = "dev"
    DEVOPS = "devops"
    RESEARCHER = "researcher"
    REVIEWER = "reviewer"
    WATCHDOG = "watchdog"


class AgentStatus(Enum):
    """Agent status states."""
    IDLE = "idle"
    BUSY = "busy"
    ACTIVE = "active"
    OFFLINE = "offline"
    ERROR = "error"


@dataclass
class HermesAgent:
    """Represents a Hermes agent with its state."""
    agent_id: str
    name: str
    role: AgentRole
    status: AgentStatus = AgentStatus.IDLE
    capabilities: List[str] = field(default_factory=list)
    current_task: Optional[str] = None
    last_heartbeat: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role.value,
            "status": self.status.value,
            "capabilities": self.capabilities,
            "current_task": self.current_task,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "metadata": self.metadata
        }


@dataclass
class Task:
    """Represents a task in the Hermes system."""
    task_id: str
    title: str
    description: str
    assignee: Optional[str] = None
    status: str = "pending"
    priority: int = 5
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "description": self.description,
            "assignee": self.assignee,
            "status": self.status,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata
        }


@dataclass
class Artifact:
    """Represents an artifact produced by an agent."""
    artifact_id: str
    name: str
    type: str
    creator_id: str
    content: Any
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "name": self.name,
            "type": self.type,
            "creator_id": self.creator_id,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata
        }


class EventType(Enum):
    """Event types for subscription."""
    AGENT_STATUS_CHANGED = "agent.status_changed"
    TASK_CREATED = "task.created"
    TASK_ASSIGNED = "task.assigned"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    ARTIFACT_CREATED = "artifact.created"
    NPC_DIALOGUE = "npc.dialogue"


class HermesProvider:
    """
    HookProvider implementation for Hermes ecosystem.
    Connects to Supervisor (JSON-RPC) and Memory Substrate (REST).
    Maps agents to NPC entities in game server.
    """
    
    # Agent role to NPC mapping
    ROLE_TO_NPC = {
        AgentRole.CEO: {"sprite": "avatar_ceo", "name": "CEO", "npc_id": "npc-ceo-01"},
        AgentRole.DEV: {"sprite": "avatar_dev", "name": "Dev Alice", "npc_id": "npc-dev-01"},
        AgentRole.DEVOPS: {"sprite": "avatar_devops", "name": "DevOps Bob", "npc_id": "npc-devops-01"},
        AgentRole.RESEARCHER: {"sprite": "avatar_researcher", "name": "Researcher Carol", "npc_id": "npc-researcher-01"},
        AgentRole.REVIEWER: {"sprite": "avatar_reviewer", "name": "Reviewer Dave", "npc_id": "npc-reviewer-01"},
        AgentRole.WATCHDOG: {"sprite": "avatar_watchdog", "name": "Watchdog", "npc_id": "npc-watchdog-01"},
    }
    
    # NPC to role reverse mapping
    NPC_TO_ROLE = {v["npc_id"]: k for k, v in ROLE_TO_NPC.items()}
    
    def __init__(
        self,
        supervisor_url: str = SUPERVISOR_URL,
        memory_substrate_url: str = MEMORY_SUBSTRATE_URL,
        auto_connect: bool = True
    ):
        self.supervisor_url = supervisor_url
        self.memory_substrate_url = memory_substrate_url
        
        self._supervisor_session: Optional[aiohttp.ClientSession] = None
        self._memory_session: Optional[aiohttp.ClientSession] = None
        
        self._agents: Dict[str, HermesAgent] = {}
        self._tasks: Dict[str, Task] = {}
        self._artifacts: Dict[str, Artifact] = {}
        
        self._event_subscribers: Dict[EventType, List[Callable]] = {et: [] for et in EventType}
        
        self._running = False
        self._sync_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        
        # Default agent definitions
        self._default_agents = [
            HermesAgent(
                agent_id="ceo-01",
                name="CEO",
                role=AgentRole.CEO,
                capabilities=["planning", "decision_making", "coordination", "prioritization"],
                metadata={"department": "executive"}
            ),
            HermesAgent(
                agent_id="dev-01",
                name="Dev Alice",
                role=AgentRole.DEV,
                capabilities=["coding", "debugging", "refactoring", "testing", "code_review"],
                metadata={"specialization": "backend", "languages": ["python", "javascript", "typescript"]}
            ),
            HermesAgent(
                agent_id="devops-01",
                name="DevOps Bob",
                role=AgentRole.DEVOPS,
                capabilities=["deployment", "ci_cd", "infrastructure", "monitoring", "docker", "kubernetes"],
                metadata={"specialization": "cloud_native"}
            ),
            HermesAgent(
                agent_id="researcher-01",
                name="Researcher Carol",
                role=AgentRole.RESEARCHER,
                capabilities=["research", "analysis", "benchmarking", "literature_review", "data_analysis"],
                metadata={"specialization": "ai_optimization"}
            ),
            HermesAgent(
                agent_id="reviewer-01",
                name="Reviewer Dave",
                role=AgentRole.REVIEWER,
                capabilities=["code_review", "security_audit", "performance_review", "architecture_review"],
                metadata={"specialization": "quality_assurance"}
            ),
            HermesAgent(
                agent_id="watchdog-01",
                name="Watchdog",
                role=AgentRole.WATCHDOG,
                capabilities=["monitoring", "alerting", "health_checks", "incident_response", "security_scanning"],
                metadata={"specialization": "observability"}
            ),
        ]
        
        if auto_connect:
            asyncio.create_task(self._initialize())
    
    async def _initialize(self):
        """Initialize connections and sync agents."""
        try:
            await self.connect()
            await self.sync_agents()
            self._running = True
            self._sync_task = asyncio.create_task(self._sync_loop())
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            logger.info("HermesProvider initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize HermesProvider: {e}")
    
    async def connect(self):
        """Establish connections to Supervisor and Memory Substrate."""
        self._supervisor_session = aiohttp.ClientSession()
        self._memory_session = aiohttp.ClientSession()
        
        # Test connections
        try:
            await self._supervisor_call("system.health", {})
            logger.info("Connected to Supervisor at %s", self.supervisor_url)
        except Exception as e:
            logger.warning("Supervisor connection failed: %s", e)
        
        try:
            async with self._memory_session.get(f"{self.memory_substrate_url}/health") as resp:
                if resp.status == 200:
                    logger.info("Connected to Memory Substrate at %s", self.memory_substrate_url)
        except Exception as e:
            logger.warning("Memory Substrate connection failed: %s", e)
    
    async def disconnect(self):
        """Close connections and stop background tasks."""
        self._running = False
        
        if self._sync_task:
            self._sync_task.cancel()
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        
        if self._supervisor_session:
            await self._supervisor_session.close()
        if self._memory_session:
            await self._memory_session.close()
        
        logger.info("HermesProvider disconnected")
    
    async def _supervisor_call(self, method: str, params: Dict) -> Dict:
        """Call Supervisor JSON-RPC endpoint."""
        if not self._supervisor_session:
            raise Exception("Supervisor session not available")
        
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": str(uuid.uuid4())
        }
        
        async with self._supervisor_session.post(self.supervisor_url, json=payload) as resp:
            result = await resp.json()
            if "error" in result:
                raise Exception(f"Supervisor error: {result['error']}")
            return result.get("result", {})
    
    async def _memory_call(self, method: str, path: str, data: Dict = None) -> Dict:
        """Call Memory Substrate REST endpoint."""
        if not self._memory_session:
            raise Exception("Memory session not available")
        
        url = f"{self.memory_substrate_url}{path}"
        
        if method.upper() == "GET":
            async with self._memory_session.get(url, params=data) as resp:
                return await resp.json()
        else:
            async with self._memory_session.request(method, url, json=data) as resp:
                return await resp.json()
    
    # ============================================================
    # HookProvider Interface Methods
    # ============================================================
    
    async def get_agents(self) -> List[Dict[str, Any]]:
        """
        Get all agents with their current status.
        Returns list of agent dicts compatible with HookProvider interface.
        """
        # Try to fetch from supervisor first
        try:
            result = await self._supervisor_call("agents.list", {})
            agents_data = result.get("agents", [])
            
            # Update local cache with supervisor data
            for agent_data in agents_data:
                agent_id = agent_data.get("agent_id") or agent_data.get("id")
                if agent_id and agent_id in self._agents:
                    agent = self._agents[agent_id]
                    agent.status = AgentStatus(agent_data.get("status", "idle"))
                    agent.current_task = agent_data.get("current_task")
                    agent.last_heartbeat = datetime.now()
                    
        except Exception as e:
            logger.debug("Could not fetch agents from supervisor: %s", e)
        
        # Return all agents (including defaults if supervisor unavailable)
        return [agent.to_dict() for agent in self._agents.values()]
    
    async def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific agent."""
        agent = self._agents.get(agent_id)
        if not agent:
            return None
        
        # Try to get fresh status from supervisor
        try:
            result = await self._supervisor_call("agents.get", {"agent_id": agent_id})
            if result:
                agent.status = AgentStatus(result.get("status", agent.status.value))
                agent.current_task = result.get("current_task")
                agent.last_heartbeat = datetime.now()
        except Exception:
            pass  # Use cached status
        
        return agent.to_dict()
    
    async def execute_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a task via the Supervisor.
        task_data should contain: title, description, assignee (role), priority, metadata
        """
        # Map role to agent_id if needed
        assignee = task_data.get("assignee")
        if assignee and isinstance(assignee, str) and assignee in AgentRole.__members__:
            # Find agent with this role
            role = AgentRole(assignee)
            agent = next((a for a in self._agents.values() if a.role == role), None)
            if agent:
                task_data["assignee"] = agent.agent_id
        
        # Create task locally
        task = Task(
            task_id=str(uuid.uuid4())[:8],
            title=task_data.get("title", "Untitled Task"),
            description=task_data.get("description", ""),
            assignee=task_data.get("assignee"),
            priority=task_data.get("priority", 5),
            metadata=task_data.get("metadata", {})
        )
        self._tasks[task.task_id] = task
        
        # Try to create via supervisor
        try:
            result = await self._supervisor_call("task.create", {
                "title": task.title,
                "description": task.description,
                "assignee": task.assignee,
                "priority": task.priority,
                "dependencies": task_data.get("dependencies", []),
                "metadata": task.metadata
            })
            
            # Update with supervisor response
            if "task_id" in result:
                task.task_id = result["task_id"]
            if "status" in result:
                task.status = result["status"]
                
        except Exception as e:
            logger.error(f"Supervisor task creation failed: {e}")
            task.status = "failed"
            task.error = str(e)
        
        # Notify subscribers
        await self._emit_event(EventType.TASK_CREATED, task.to_dict())
        
        return task.to_dict()
    
    async def get_artifacts(self, agent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get artifacts from Memory Substrate.
        Optionally filter by agent_id (creator).
        """
        try:
            # Query Memory Substrate for artifacts
            query = "artifacts"
            if agent_id:
                query += f" created by {agent_id}"
            
            result = await self._memory_call("POST", "/query", {
                "query": query,
                "max_results": 50,
                "synthesize": False
            })
            
            # Parse results into artifacts
            artifacts = []
            for source in result.get("sources", []):
                metadata = source.get("metadata", {})
                artifact = Artifact(
                    artifact_id=metadata.get("artifact_id", str(uuid.uuid4())[:8]),
                    name=metadata.get("name", "Unknown Artifact"),
                    type=metadata.get("type", "document"),
                    creator_id=metadata.get("creator_id", "unknown"),
                    content=source.get("content", ""),
                    metadata=metadata
                )
                artifacts.append(artifact)
                self._artifacts[artifact.artifact_id] = artifact
            
            return [a.to_dict() for a in artifacts]
            
        except Exception as e:
            logger.error(f"Failed to fetch artifacts: {e}")
            # Return local cache
            artifacts = list(self._artifacts.values())
            if agent_id:
                artifacts = [a for a in artifacts if a.creator_id == agent_id]
            return [a.to_dict() for a in artifacts]
    
    async def subscribe_events(self, event_types: List[str], callback: Callable) -> str:
        """
        Subscribe to events from the Hermes system.
        Returns subscription ID.
        """
        subscription_id = str(uuid.uuid4())[:8]
        
        for event_type_str in event_types:
            try:
                event_type = EventType(event_type_str)
                self._event_subscribers[event_type].append(callback)
            except ValueError:
                logger.warning(f"Unknown event type: {event_type_str}")
        
        logger.info(f"Subscribed {subscription_id} to events: {event_types}")
        return subscription_id
    
    async def unsubscribe_events(self, subscription_id: str):
        """Unsubscribe from events (placeholder - would need subscription tracking)."""
        # In a full implementation, we'd track subscription_id -> callbacks
        logger.info(f"Unsubscribed {subscription_id}")
    
    # ============================================================
    # NPC Mapping Methods
    # ============================================================
    
    def get_npc_mapping(self) -> Dict[str, Dict[str, Any]]:
        """Get the mapping of agent roles to NPC configurations."""
        return {
            role.value: {
                "npc_id": config["npc_id"],
                "name": config["name"],
                "sprite": config["sprite"],
                "role": role.value
            }
            for role, config in self.ROLE_TO_NPC.items()
        }
    
    def get_agent_for_npc(self, npc_id: str) -> Optional[HermesAgent]:
        """Get the Hermes agent associated with an NPC."""
        role = self.NPC_TO_ROLE.get(npc_id)
        if not role:
            return None
        return next((a for a in self._agents.values() if a.role == role), None)
    
    def get_npc_for_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get NPC configuration for an agent."""
        agent = self._agents.get(agent_id)
        if not agent:
            return None
        return self.ROLE_TO_NPC.get(agent.role)
    
    def update_npc_status_from_agent(self, npc_id: str, entity_meta: Dict) -> Dict:
            """
            Update NPC entity metadata based on agent status.
            Returns updated metadata dict.
            """
            # Try to get role from entity meta first
            role_str = entity_meta.get("role", "").lower()
        
            # If not in meta, try to look up by NPC ID
            if not role_str:
                role = self.NPC_TO_ROLE.get(npc_id)
                if role:
                    role_str = role.value
        
            if not role_str:
                return entity_meta
        
            # Find agent with this role
            agent = next((a for a in self._agents.values() if a.role.value == role_str), None)
            if not agent:
                return entity_meta

            # Map agent status to NPC behavior
            status_map = {
                AgentStatus.IDLE: "idle",
                AgentStatus.BUSY: "working",
                AgentStatus.ACTIVE: "active",
                AgentStatus.OFFLINE: "offline",
                AgentStatus.ERROR: "error"
            }

            entity_meta["status"] = status_map.get(agent.status, "idle")
            entity_meta["agent_status"] = agent.status.value
            entity_meta["current_task"] = agent.current_task
            entity_meta["last_update"] = datetime.now().isoformat()

            # Add role-specific behavior hints
            if agent.role == AgentRole.DEV and agent.status == AgentStatus.BUSY:
                entity_meta["activity"] = "coding"
            elif agent.role == AgentRole.DEVOPS and agent.status == AgentStatus.BUSY:
                entity_meta["activity"] = "deploying"
            elif agent.role == AgentRole.RESEARCHER and agent.status == AgentStatus.BUSY:
                entity_meta["activity"] = "researching"
            elif agent.role == AgentRole.WATCHDOG and agent.status == AgentStatus.BUSY:
                entity_meta["activity"] = "monitoring"
            elif agent.role == AgentRole.REVIEWER and agent.status == AgentStatus.BUSY:
                entity_meta["activity"] = "reviewing"
            elif agent.role == AgentRole.CEO and agent.status == AgentStatus.BUSY:
                entity_meta["activity"] = "planning"

            return entity_meta
    
    # ============================================================
    # Background Sync Loops
    # ============================================================
    
    async def _sync_loop(self):
        """Periodically sync agent states from supervisor."""
        while self._running:
            try:
                await self.sync_agents()
            except Exception as e:
                logger.error(f"Sync loop error: {e}")
            await asyncio.sleep(10)  # Sync every 10 seconds
    
    async def _heartbeat_loop(self):
        """Send heartbeats and check agent health."""
        while self._running:
            try:
                await self._check_agent_health()
            except Exception as e:
                logger.error(f"Heartbeat loop error: {e}")
            await asyncio.sleep(30)  # Check every 30 seconds
    
    async def sync_agents(self):
        """Sync agent list and status from supervisor."""
        try:
            result = await self._supervisor_call("agents.list", {})
            agents_data = result.get("agents", [])
            
            for agent_data in agents_data:
                agent_id = agent_data.get("agent_id") or agent_data.get("id")
                if not agent_id:
                    continue
                
                if agent_id in self._agents:
                    # Update existing
                    agent = self._agents[agent_id]
                    old_status = agent.status
                    agent.status = AgentStatus(agent_data.get("status", "idle"))
                    agent.current_task = agent_data.get("current_task")
                    agent.last_heartbeat = datetime.now()
                    agent.metadata.update(agent_data.get("metadata", {}))
                    
                    # Emit status change event if status changed
                    if old_status != agent.status:
                        await self._emit_event(EventType.AGENT_STATUS_CHANGED, agent.to_dict())
                else:
                    # New agent from supervisor
                    role_str = agent_data.get("role", "dev")
                    try:
                        role = AgentRole(role_str)
                    except ValueError:
                        role = AgentRole.DEV
                    
                    agent = HermesAgent(
                        agent_id=agent_id,
                        name=agent_data.get("name", agent_id),
                        role=role,
                        status=AgentStatus(agent_data.get("status", "idle")),
                        capabilities=agent_data.get("capabilities", []),
                        current_task=agent_data.get("current_task"),
                        last_heartbeat=datetime.now(),
                        metadata=agent_data.get("metadata", {})
                    )
                    self._agents[agent_id] = agent
                    await self._emit_event(EventType.AGENT_STATUS_CHANGED, agent.to_dict())
            
            logger.debug(f"Synced {len(agents_data)} agents from supervisor")
            
        except Exception as e:
            logger.debug(f"Could not sync from supervisor, using defaults: {e}")
            # Ensure default agents are registered
            for agent in self._default_agents:
                if agent.agent_id not in self._agents:
                    self._agents[agent.agent_id] = agent
    
    async def _check_agent_health(self):
        """Check agent health via heartbeats."""
        now = datetime.now()
        for agent in self._agents.values():
            if agent.last_heartbeat:
                elapsed = (now - agent.last_heartbeat).total_seconds()
                if elapsed > 60 and agent.status != AgentStatus.OFFLINE:
                    old_status = agent.status
                    agent.status = AgentStatus.OFFLINE
                    await self._emit_event(EventType.AGENT_STATUS_CHANGED, agent.to_dict())
                    logger.warning(f"Agent {agent.agent_id} marked offline (no heartbeat for {elapsed}s)")
    
    async def _emit_event(self, event_type: EventType, data: Dict):
        """Emit event to all subscribers."""
        for callback in self._event_subscribers.get(event_type, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                logger.error(f"Event callback error for {event_type}: {e}")
    
    # ============================================================
    # Convenience Methods
    # ============================================================
    
    async def get_agent_by_role(self, role: AgentRole) -> Optional[HermesAgent]:
        """Get the first agent with the given role."""
        return next((a for a in self._agents.values() if a.role == role), None)
    
    async def get_available_agents(self, capability: str = None) -> List[HermesAgent]:
        """Get agents that are idle and optionally have a capability."""
        agents = [a for a in self._agents.values() if a.status == AgentStatus.IDLE]
        if capability:
            agents = [a for a in agents if capability in a.capabilities]
        return agents
    
    async def assign_task_to_role(self, role: AgentRole, task_data: Dict) -> Dict:
        """Assign a task to an agent with the specified role."""
        agent = await self.get_agent_by_role(role)
        if not agent:
            raise Exception(f"No agent found for role: {role.value}")
        
        task_data["assignee"] = agent.agent_id
        return await self.execute_task(task_data)
    
    async def get_npc_dialogue_context(self, npc_id: str) -> Dict[str, Any]:
        """Get context for NPC dialogue from Memory Substrate."""
        agent = self.get_agent_for_npc(npc_id)
        if not agent:
            return {}
        
        try:
            result = await self._memory_call("POST", "/query", {
                "query": f"NPC {npc_id} {agent.role.value} personality knowledge context",
                "max_results": 5,
                "synthesize": True,
                "filters": {"entity": npc_id}
            })
            return {
                "npc_id": npc_id,
                "agent_role": agent.role.value,
                "knowledge": result.get("answer", ""),
                "sources": result.get("sources", []),
                "capabilities": agent.capabilities
            }
        except Exception as e:
            logger.error(f"Failed to get NPC dialogue context: {e}")
            return {
                "npc_id": npc_id,
                "agent_role": agent.role.value,
                "knowledge": "",
                "sources": [],
                "capabilities": agent.capabilities
            }


# Global provider instance
_provider: Optional[HermesProvider] = None


async def get_provider() -> HermesProvider:
    """Get or create the global HermesProvider instance."""
    global _provider
    if _provider is None:
        _provider = HermesProvider(auto_connect=False)
        await _provider._initialize()
    return _provider


async def close_provider():
    """Close the global provider."""
    global _provider
    if _provider:
        await _provider.disconnect()
        _provider = None


if __name__ == "__main__":
    # Test the provider
    async def test():
        provider = HermesProvider()
        await asyncio.sleep(2)  # Wait for initialization
        
        print("=== Agents ===")
        agents = await provider.get_agents()
        for a in agents:
            print(f"  {a['name']} ({a['role']}): {a['status']}")
        
        print("\n=== NPC Mapping ===")
        mapping = provider.get_npc_mapping()
        for role, config in mapping.items():
            print(f"  {role} -> {config['npc_id']} ({config['name']})")
        
        print("\n=== Test Task Creation ===")
        task = await provider.execute_task({
            "title": "Test Task",
            "description": "A test task for Dev",
            "assignee": "dev",
            "priority": 3
        })
        print(f"  Created task: {task['task_id']} - {task['title']}")
        
        print("\n=== Test Artifacts ===")
        artifacts = await provider.get_artifacts()
        print(f"  Found {len(artifacts)} artifacts")
        
        await provider.disconnect()
    
    asyncio.run(test())