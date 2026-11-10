#!/usr/bin/env python3
"""
NPC Behavior Trees for Hermes-Corp Game Server.

Provides base BehaviorTree infrastructure with Selector, Sequence, Condition, Action nodes
and role-specific behavior trees for Dev, DevOps, Researcher, Watchdog, and CEO NPCs.
"""

import asyncio
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set


class NodeStatus(Enum):
    """Behavior tree node execution status."""
    SUCCESS = "success"
    FAILURE = "failure"
    RUNNING = "running"


@dataclass
class Blackboard:
    """Shared state for behavior tree nodes."""
    data: Dict[str, Any] = field(default_factory=dict)
    
    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
    
    def has(self, key: str) -> bool:
        return key in self.data


class BehaviorNode(ABC):
    """Base class for all behavior tree nodes."""
    
    def __init__(self, name: str = ""):
        self.name = name or self.__class__.__name__
        self.children: List[BehaviorNode] = []
        self.parent: Optional[BehaviorNode] = None
    
    def add_child(self, child: "BehaviorNode") -> "BehaviorNode":
        child.parent = self
        self.children.append(child)
        return child
    
    @abstractmethod
    async def tick(self, blackboard: Blackboard) -> NodeStatus:
        pass
    
    def __repr__(self):
        return f"{self.name}()"


class CompositeNode(BehaviorNode):
    """Base class for composite nodes (Selector, Sequence)."""
    
    def __init__(self, name: str = "", children: List[BehaviorNode] = None):
        super().__init__(name)
        if children:
            for child in children:
                self.add_child(child)


class Selector(CompositeNode):
    """
    Selector node - runs children in order until one succeeds.
    Returns SUCCESS if any child succeeds, FAILURE if all fail.
    """
    
    async def tick(self, blackboard: Blackboard) -> NodeStatus:
        for child in self.children:
            status = await child.tick(blackboard)
            if status == NodeStatus.SUCCESS:
                return NodeStatus.SUCCESS
            elif status == NodeStatus.RUNNING:
                return NodeStatus.RUNNING
        return NodeStatus.FAILURE


class Sequence(CompositeNode):
    """
    Sequence node - runs children in order until one fails.
    Returns FAILURE if any child fails, SUCCESS if all succeed.
    """
    
    async def tick(self, blackboard: Blackboard) -> NodeStatus:
        for child in self.children:
            status = await child.tick(blackboard)
            if status == NodeStatus.FAILURE:
                return NodeStatus.FAILURE
            elif status == NodeStatus.RUNNING:
                return NodeStatus.RUNNING
        return NodeStatus.SUCCESS


class Condition(BehaviorNode):
    """
    Condition node - evaluates a predicate function.
    Returns SUCCESS if true, FAILURE if false.
    """
    
    def __init__(self, name: str, predicate: Callable[[Blackboard], bool]):
        super().__init__(name)
        self.predicate = predicate
    
    async def tick(self, blackboard: Blackboard) -> NodeStatus:
        try:
            result = self.predicate(blackboard)
            if asyncio.iscoroutine(result):
                result = await result
            return NodeStatus.SUCCESS if result else NodeStatus.FAILURE
        except Exception:
            return NodeStatus.FAILURE


class Action(BehaviorNode):
    """
    Action node - executes an action function.
    Returns the status returned by the action (SUCCESS, FAILURE, or RUNNING).
    """
    
    def __init__(self, name: str, action: Callable[[Blackboard], Any]):
        super().__init__(name)
        self.action = action
    
    async def tick(self, blackboard: Blackboard) -> NodeStatus:
        try:
            result = self.action(blackboard)
            if asyncio.iscoroutine(result):
                result = await result
            if isinstance(result, NodeStatus):
                return result
            return NodeStatus.SUCCESS if result else NodeStatus.FAILURE
        except Exception as e:
            return NodeStatus.FAILURE


class DecoratorNode(BehaviorNode):
    """Base class for decorator nodes (Inverter, Repeater, etc.)."""
    
    def __init__(self, name: str = "", child: BehaviorNode = None):
        super().__init__(name)
        if child:
            self.add_child(child)


class Inverter(DecoratorNode):
    """Inverts the result of its child (SUCCESS <-> FAILURE)."""
    
    async def tick(self, blackboard: Blackboard) -> NodeStatus:
        if not self.children:
            return NodeStatus.FAILURE
        status = await self.children[0].tick(blackboard)
        if status == NodeStatus.SUCCESS:
            return NodeStatus.FAILURE
        elif status == NodeStatus.FAILURE:
            return NodeStatus.SUCCESS
        return NodeStatus.RUNNING


class Repeater(DecoratorNode):
    """Repeats its child until it returns FAILURE or max_count reached."""
    
    def __init__(self, name: str = "", child: BehaviorNode = None, max_count: int = -1):
        super().__init__(name, child)
        self.max_count = max_count
        self.count = 0
    
    async def tick(self, blackboard: Blackboard) -> NodeStatus:
        if not self.children:
            return NodeStatus.FAILURE
        
        if self.max_count > 0 and self.count >= self.max_count:
            return NodeStatus.SUCCESS
        
        status = await self.children[0].tick(blackboard)
        
        if status == NodeStatus.SUCCESS:
            self.count += 1
            if self.max_count > 0 and self.count >= self.max_count:
                return NodeStatus.SUCCESS
            return NodeStatus.RUNNING  # Continue repeating
        elif status == NodeStatus.FAILURE:
            return NodeStatus.FAILURE
        return NodeStatus.RUNNING


class BehaviorTree:
    """
    Behavior tree executor with blackboard and tick management.
    """
    
    def __init__(self, root: BehaviorNode, name: str = ""):
        self.root = root
        self.name = name or root.name
        self.blackboard = Blackboard()
        self._last_status = NodeStatus.FAILURE
        self._tick_count = 0
    
    async def tick(self) -> NodeStatus:
        """Execute one tick of the behavior tree."""
        self._tick_count += 1
        self._last_status = await self.root.tick(self.blackboard)
        return self._last_status
    
    def reset(self) -> None:
        """Reset the behavior tree state."""
        self.blackboard = Blackboard()
        self._last_status = NodeStatus.FAILURE
        self._tick_count = 0
    
    @property
    def last_status(self) -> NodeStatus:
        return self._last_status
    
    @property
    def tick_count(self) -> int:
        return self._tick_count


# ============================================================
# NPC Role-Specific Behavior Trees
# ============================================================

class NPCBlackboard(Blackboard):
    """Extended blackboard for NPC-specific data with internal state machine."""

    def __init__(self, npc_entity, game_server):
        super().__init__()
        self.npc = npc_entity
        self.game_server = game_server
        self.current_room = npc_entity.room_id
        self.target_room: Optional[str] = None
        self.target_position: Optional[tuple] = None
        self.work_state = "idle"  # idle, working, moving, meeting, crisis
        self.last_state_change = time.time()
        self.path: List[tuple] = []
        self.path_index = 0

        # --- NEW: Internal State Machine for Autonomous Behavior ---
        self.npc_state = "IDLE"  # WORKING, BREAK, MEETING, IDLE
        # Random initial offset so NPCs don't all transition at once
        self.state_timer = time.time() - random.uniform(0, 30)
        self.state_duration = random.uniform(30, 120)  # IDLE duration

        # Timing configuration (in seconds)
        self.work_duration_min = 300    # 5 minutes
        self.work_duration_max = 600    # 10 minutes
        self.break_duration_min = 60    # 1 minute
        self.break_duration_max = 120   # 2 minutes
        self.meeting_duration_min = 300 # 5 minutes
        self.meeting_duration_max = 900 # 15 minutes
        self.idle_duration_min = 30     # 30 seconds
        self.idle_duration_max = 120    # 2 minutes

        # Probability of transitioning to meeting from working
        self.meeting_probability = 0.15  # 15% chance per work cycle

        # Meeting scheduling
        self.meeting_room_id = "meeting_room_1"
        # Initialize to a random future time (5-30 minutes from now)
        self.scheduled_meeting_time = time.time() + random.uniform(300, 1800)
        self.in_scheduled_meeting = False

        # Break location preferences
        self.break_rooms = ["cafe", "lobby"]  # Cafe or lounge for breaks
        self.current_break_room = None

        # Work progress tracking
        self.work_cycles_completed = 0
        self.total_work_time = 0.0
        self.total_break_time = 0.0
        self.total_meeting_time = 0.0

        # --- Watchdog Alert Rate Limiting ---
        self.last_alert_time = 0.0
        self.alert_cooldown = 30.0  # seconds between alert generations
        self.alerts_this_tick = 0
        self.max_alerts_per_tick = 3
        self.alert_log_ttl = 60.0  # seconds before alert logs auto-expire
        self.alert_logs: List[Dict] = []  # track generated alert logs with timestamps


# ---- Helper Functions ----

def get_room_positions(game_server, room_id: str) -> Dict[str, tuple]:
    """Get key positions in a room."""
    room = game_server.rooms.get(room_id)
    if not room:
        return {}
    w, h = room.width, room.height
    return {
        "center": (w // 2, h // 2),
        "desk_area": (w // 2, h - 3),
        "meeting_table": (w // 2, h // 2),
        "entrance": (w // 2, 1),
        "server_rack": (w - 3, h // 2),
        "cafe": (3, h // 2),
        "patrol_points": [
            (5, 5), (w - 5, 5), (w - 5, h - 5), (5, h - 5),
            (w // 2, 5), (w // 2, h - 5), (5, h // 2), (w - 5, h // 2)
        ]
    }


async def find_path(game_server, start_room: str, start_pos: tuple, target_room: str, target_pos: tuple) -> List[tuple]:
    """
    Simple pathfinding - returns list of (room_id, x, y) waypoints.
    For now, direct path within same room or room-to-room via entrance.
    """
    path = []
    
    if start_room == target_room:
        # Simple direct path within room
        sx, sy = start_pos
        tx, ty = target_pos
        steps = max(abs(tx - sx), abs(ty - sy))
        for i in range(steps + 1):
            x = sx + (tx - sx) * i // max(1, steps)
            y = sy + (ty - sy) * i // max(1, steps)
            path.append((target_room, x, y))
    else:
        # Path through entrance
        start_room_obj = game_server.rooms.get(start_room)
        target_room_obj = game_server.rooms.get(target_room)
        
        if start_room_obj and target_room_obj:
            # Go to entrance of start room
            entrance = (start_room_obj.width // 2, 1)
            sx, sy = start_pos
            steps = max(abs(entrance[0] - sx), abs(entrance[1] - sy))
            for i in range(steps + 1):
                x = sx + (entrance[0] - sx) * i // max(1, steps)
                y = sy + (entrance[1] - sy) * i // max(1, steps)
                path.append((start_room, x, y))
            
            # Transition to target room entrance
            target_entrance = (target_room_obj.width // 2, 1)
            path.append((target_room, target_entrance[0], target_entrance[1]))
            
            # Go to target position in target room
            tx, ty = target_pos
            steps = max(abs(tx - target_entrance[0]), abs(ty - target_entrance[1]))
            for i in range(steps + 1):
                x = target_entrance[0] + (tx - target_entrance[0]) * i // max(1, steps)
                y = target_entrance[1] + (ty - target_entrance[1]) * i // max(1, steps)
                path.append((target_room, x, y))
    
    return path


def get_agent_status_from_supervisor(game_server, role: str) -> Dict:
    """
    Get real agent status from Hermes Supervisor.
    Returns dict with: status, current_task, workload, etc.
    """
    # This will be called async from the game server
    # For now return mock - actual implementation calls supervisor RPC
    return {
        "status": "idle",
        "current_task": None,
        "workload": 0,
        "last_heartbeat": time.time()
    }


# ---- Condition Functions ----

def is_idle(bb: NPCBlackboard) -> bool:
    return bb.npc.meta.get("status") == "idle"


def is_working(bb: NPCBlackboard) -> bool:
    return bb.npc.meta.get("status") == "working"


def is_moving(bb: NPCBlackboard) -> bool:
    return bb.npc.meta.get("status") == "moving"


def is_in_meeting(bb: NPCBlackboard) -> bool:
    return bb.npc.meta.get("status") == "meeting"


def is_crisis(bb: NPCBlackboard) -> bool:
    return bb.npc.meta.get("status") == "crisis_response"


def has_target_room(bb: NPCBlackboard) -> bool:
    return bb.target_room is not None


def at_target_position(bb: NPCBlackboard) -> bool:
    if bb.target_position is None:
        return True
    pos = bb.npc.position
    return pos.x == bb.target_position[0] and pos.y == bb.target_position[1]


def has_path(bb: NPCBlackboard) -> bool:
    return len(bb.path) > 0 and bb.path_index < len(bb.path)


def agent_has_work(bb: NPCBlackboard) -> bool:
    """Check if real agent has work via supervisor."""
    role = bb.npc.meta.get("role", "")
    # This would call supervisor in real implementation
    return bb.get("agent_has_work", False)


def agent_in_meeting(bb: NPCBlackboard) -> bool:
    """Check if real agent is in meeting."""
    return bb.get("agent_in_meeting", False)


def agent_alert_active(bb: NPCBlackboard) -> bool:
    """Check if watchdog agent has active alert."""
    return bb.get("agent_alert_active", False)


def room_is_meeting_room(bb: NPCBlackboard) -> bool:
    room = bb.game_server.rooms.get(bb.npc.room_id)
    return room and room.is_meeting


def at_desk(bb: NPCBlackboard) -> bool:
    """Check if NPC is at their desk position."""
    positions = get_room_positions(bb.game_server, bb.npc.room_id)
    desk = positions.get("desk_area")
    if desk:
        return bb.npc.position.x == desk[0] and bb.npc.position.y == desk[1]
    return False


def at_cafe(bb: NPCBlackboard) -> bool:
    """Check if NPC is at cafe."""
    positions = get_room_positions(bb.game_server, bb.npc.room_id)
    cafe = positions.get("cafe")
    if cafe:
        return bb.npc.position.x == cafe[0] and bb.npc.position.y == cafe[1]
    return False


def at_server_room(bb: NPCBlackboard) -> bool:
    """Check if NPC is at server rack."""
    positions = get_room_positions(bb.game_server, bb.npc.room_id)
    server = positions.get("server_rack")
    if server:
        return bb.npc.position.x == server[0] and bb.npc.position.y == server[1]
    return False


# ---- NEW: State Machine Condition Functions ----

def is_state_working(bb: NPCBlackboard) -> bool:
    """Check if NPC internal state is WORKING."""
    return bb.npc_state == "WORKING"


def is_state_break(bb: NPCBlackboard) -> bool:
    """Check if NPC internal state is BREAK."""
    return bb.npc_state == "BREAK"


def is_state_meeting(bb: NPCBlackboard) -> bool:
    """Check if NPC internal state is MEETING."""
    return bb.npc_state == "MEETING"


def is_state_idle(bb: NPCBlackboard) -> bool:
    """Check if NPC internal state is IDLE."""
    return bb.npc_state == "IDLE"


def state_timer_expired(bb: NPCBlackboard) -> bool:
    """Check if current state timer has expired."""
    return time.time() - bb.state_timer >= bb.state_duration


def should_transition_to_meeting(bb: NPCBlackboard) -> bool:
    """Check if NPC should transition from WORKING to MEETING based on probability."""
    if bb.npc_state != "WORKING":
        return False
    return random.random() < bb.meeting_probability


def should_schedule_meeting(bb: NPCBlackboard) -> bool:
    """Check if it's time for a scheduled meeting."""
    return time.time() >= bb.scheduled_meeting_time and not bb.in_scheduled_meeting


def at_break_location(bb: NPCBlackboard) -> bool:
    """Check if NPC is at a break location (cafe or lobby)."""
    room = bb.game_server.rooms.get(bb.npc.room_id)
    if not room:
        return False
    return room.id in bb.break_rooms


def at_meeting_room(bb: NPCBlackboard) -> bool:
    """Check if NPC is in the meeting room."""
    return bb.npc.room_id == bb.meeting_room_id


def at_desk_area(bb: NPCBlackboard) -> bool:
    """Check if NPC is at their desk area."""
    positions = get_room_positions(bb.game_server, bb.npc.room_id)
    desk = positions.get("desk_area")
    if desk:
        return bb.npc.position.x == desk[0] and bb.npc.position.y == desk[1]
    return False


# ---- Watchdog Alert Rate Limiting Functions ----

def alert_cooldown_ready(bb: NPCBlackboard) -> bool:
    """Check if enough time has passed since last alert generation."""
    return time.time() - bb.last_alert_time >= bb.alert_cooldown


def alert_rate_limit_ok(bb: NPCBlackboard) -> bool:
    """Check if we haven't exceeded max alerts per tick."""
    current_time = time.time()
    # Reset counter if a second has passed
    if current_time - getattr(bb, '_last_tick_time', 0) >= 1.0:
        bb.alerts_this_tick = 0
        bb._last_tick_time = current_time
    return bb.alerts_this_tick < bb.max_alerts_per_tick


async def cleanup_expired_alert_logs(bb: NPCBlackboard) -> NodeStatus:
    """Remove alert logs older than TTL."""
    current_time = time.time()
    bb.alert_logs = [
        log for log in bb.alert_logs
        if current_time - log.get('timestamp', 0) < bb.alert_log_ttl
    ]
    return NodeStatus.SUCCESS


# ---- Action Functions ----

async def action_wander(bb: NPCBlackboard) -> NodeStatus:
    """NPC wanders randomly in current room."""
    room = bb.game_server.rooms.get(bb.npc.room_id)
    if not room:
        return NodeStatus.FAILURE
    
    directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
    random.shuffle(directions)
    
    for dx, dy in directions:
        new_x = bb.npc.position.x + dx
        new_y = bb.npc.position.y + dy
        if room.move_entity(bb.npc.id, new_x, new_y):
            bb.npc.meta["status"] = "moving"
            bb.npc.meta["direction"] = "down" if dy > 0 else "up" if dy < 0 else "right" if dx > 0 else "left"
            return NodeStatus.SUCCESS
    
    return NodeStatus.FAILURE


async def action_investigate_alert(bb: NPCBlackboard) -> NodeStatus:
    """Watchdog investigates an alert - updates activity and tracks alert generation."""
    bb.npc.meta.update({"activity": "investigating"})
    bb.last_alert_time = time.time()
    bb.alerts_this_tick += 1
    bb._last_tick_time = time.time()
    # Track this alert log for TTL expiration
    bb.alert_logs.append({
        'timestamp': time.time(),
        'activity': 'investigating',
        'npc': bb.npc.id
    })
    return NodeStatus.RUNNING


async def action_socialize_at_cafe(bb: NPCBlackboard) -> NodeStatus:
    """NPC goes to cafe and socializes."""
    positions = get_room_positions(bb.game_server, bb.npc.room_id)
    cafe = positions.get("cafe")
    
    if not cafe:
        return NodeStatus.FAILURE
    
    if not at_cafe(bb):
        # Move toward cafe
        bb.target_position = cafe
        bb.target_room = bb.npc.room_id
        return await action_move_to_target(bb)
    
    # At cafe - socialize
    bb.npc.meta["status"] = "idle"
    bb.npc.meta["activity"] = "socializing"
    return NodeStatus.SUCCESS


async def action_move_to_target(bb: NPCBlackboard) -> NodeStatus:
    """Move NPC toward target position along path."""
    if not bb.target_position or not bb.target_room:
        return NodeStatus.FAILURE
    
    # If target is in different room, need to transition
    if bb.target_room != bb.npc.room_id:
        # Find the door to the target room
        current_room = bb.game_server.rooms.get(bb.npc.room_id)
        if not current_room:
            return NodeStatus.FAILURE
        
        # Look up door position from ROOM_CONFIGS
        from rooms import ROOM_CONFIGS
        room_config = ROOM_CONFIGS.get(bb.npc.room_id, {})
        door_pos = None
        for door in room_config.get("doors", []):
            if door.get("target_room") == bb.target_room:
                door_pos = (door["x"], door["y"])
                break
        
        if door_pos is None:
            # Fallback to center top
            door_pos = (current_room.width // 2, 1)
        
        if (bb.npc.position.x, bb.npc.position.y) != door_pos:
            bb.target_position = door_pos
            bb.target_room = bb.npc.room_id
        else:
            # At door, transition rooms
            target_room_obj = bb.game_server.rooms.get(bb.target_room)
            if not target_room_obj:
                return NodeStatus.FAILURE
            
            # Find target room's door back to current room
            target_config = ROOM_CONFIGS.get(bb.target_room, {})
            target_door_pos = None
            for door in target_config.get("doors", []):
                if door.get("target_room") == bb.npc.room_id:
                    # The door's x,y are the coordinates IN the target room
                    target_door_pos = (door["x"], door["y"])
                    break
            
            if target_door_pos is None:
                target_door_pos = (target_room_obj.width // 2, 1)
            
            # Remove from current room
            current_room.remove_entity(bb.npc.id)
            # Add to target room
            bb.npc.room_id = bb.target_room
            bb.npc.position = Position(target_door_pos[0], target_door_pos[1])
            target_room_obj.add_entity(bb.npc)
            bb.current_room = bb.target_room
            
            # Broadcast room change
            await bb.game_server._broadcast_entity_spawn(bb.npc)
            return NodeStatus.RUNNING
    
    # Move within room toward target
    room = bb.game_server.rooms.get(bb.npc.room_id)
    if not room:
        return NodeStatus.FAILURE
    
    tx, ty = bb.target_position
    cx, cy = bb.npc.position.x, bb.npc.position.y
    
    if cx == tx and cy == ty:
        bb.npc.meta["status"] = "idle"
        bb.target_position = None
        bb.target_room = None
        return NodeStatus.SUCCESS
    
    # Calculate next step
    dx = 0 if cx == tx else (1 if tx > cx else -1)
    dy = 0 if cy == ty else (1 if ty > cy else -1)
    
    new_x = cx + dx
    new_y = cy + dy
    
    if room.move_entity(bb.npc.id, new_x, new_y):
        bb.npc.meta["status"] = "moving"
        if dx > 0:
            bb.npc.meta["direction"] = "right"
        elif dx < 0:
            bb.npc.meta["direction"] = "left"
        elif dy > 0:
            bb.npc.meta["direction"] = "down"
        elif dy < 0:
            bb.npc.meta["direction"] = "up"
        return NodeStatus.RUNNING
    
    return NodeStatus.FAILURE


async def action_work_at_desk(bb: NPCBlackboard) -> NodeStatus:
    """NPC works at their desk."""
    if not at_desk(bb):
        positions = get_room_positions(bb.game_server, bb.npc.room_id)
        desk = positions.get("desk_area")
        if desk:
            bb.target_position = desk
            bb.target_room = bb.npc.room_id
            return await action_move_to_target(bb)
    
    bb.npc.meta["status"] = "working"
    bb.npc.meta["activity"] = "typing"
    # Simulate work progress
    bb.set("work_progress", bb.get("work_progress", 0) + 1)
    return NodeStatus.RUNNING


async def action_attend_meeting(bb: NPCBlackboard) -> NodeStatus:
    """NPC attends meeting in meeting room."""
    meeting_room_id = "meeting_room_1"
    
    if bb.npc.room_id != meeting_room_id:
        # Move to meeting room
        room = bb.game_server.rooms.get(meeting_room_id)
        if room:
            positions = get_room_positions(bb.game_server, meeting_room_id)
            table = positions.get("meeting_table", (room.width // 2, room.height // 2))
            bb.target_position = table
            bb.target_room = meeting_room_id
            return await action_move_to_target(bb)
    
    bb.npc.meta["status"] = "meeting"
    bb.npc.meta["activity"] = "meeting"
    return NodeStatus.RUNNING


async def action_patrol(bb: NPCBlackboard) -> NodeStatus:
    """Watchdog patrols the office."""
    positions = get_room_positions(bb.game_server, bb.npc.room_id)
    patrol_points = positions.get("patrol_points", [])
    
    if not patrol_points:
        return NodeStatus.FAILURE
    
    if not bb.has("patrol_index"):
        bb.set("patrol_index", 0)
    
    idx = bb.get("patrol_index")
    target = patrol_points[idx]
    
    if (bb.npc.position.x, bb.npc.position.y) != target:
        bb.target_position = target
        bb.target_room = bb.npc.room_id
        return await action_move_to_target(bb)
    
    # At patrol point, move to next
    bb.set("patrol_index", (idx + 1) % len(patrol_points))
    bb.npc.meta["status"] = "patrolling"
    return NodeStatus.RUNNING


async def action_respond_to_crisis(bb: NPCBlackboard) -> NodeStatus:
    """Watchdog responds to crisis - runs to server room."""
    server_room_id = "server_room"  # Would need to exist
    room = bb.game_server.rooms.get(server_room_id)
    
    if not room:
        # Fallback: go to server rack in main office
        positions = get_room_positions(bb.game_server, bb.npc.room_id)
        server = positions.get("server_rack")
        if server:
            bb.target_position = server
            bb.target_room = bb.npc.room_id
            return await action_move_to_target(bb)
    
    if bb.npc.room_id != server_room_id:
        bb.target_room = server_room_id
        positions = get_room_positions(bb.game_server, server_room_id)
        server = positions.get("server_rack", (room.width // 2, room.height // 2))
        bb.target_position = server
        return await action_move_to_target(bb)
    
    bb.npc.meta["status"] = "crisis_response"
    bb.npc.meta["activity"] = "recovering"
    return NodeStatus.RUNNING


async def action_ceo_decide(bb: NPCBlackboard) -> NodeStatus:
    """CEO makes decisions."""
    bb.npc.meta["status"] = "working"
    bb.npc.meta["activity"] = "deciding"
    return NodeStatus.SUCCESS


async def action_ceo_delegate(bb: NPCBlackboard) -> NodeStatus:
    """CEO delegates tasks."""
    bb.npc.meta["status"] = "working"
    bb.npc.meta["activity"] = "delegating"
    return NodeStatus.SUCCESS


async def action_update_agent_status(bb: NPCBlackboard) -> NodeStatus:
    """Sync NPC state with real agent status from supervisor."""
    role = bb.npc.meta.get("role", "")
    # In real implementation, this would call supervisor RPC
    # For now, we'll simulate based on NPC's own state
    agent_status = {
        "dev": {"status": "working" if is_working(bb) else "idle"},
        "devops": {"status": "working" if is_working(bb) else "idle"},
        "researcher": {"status": "working" if is_working(bb) else "idle"},
        "watchdog": {"status": "patrolling" if is_idle(bb) else "crisis_response"},
        "ceo": {"status": "meeting" if is_in_meeting(bb) else "working"},
    }

    status_info = agent_status.get(role, {"status": "idle"})
    bb.set("agent_status", status_info)
    return NodeStatus.SUCCESS


# ---- NEW: State Machine Action Functions ----

async def action_enter_working(bb: NPCBlackboard) -> NodeStatus:
    """Transition NPC to WORKING state."""
    bb.npc_state = "WORKING"
    bb.state_timer = time.time()
    bb.state_duration = random.uniform(bb.work_duration_min, bb.work_duration_max)
    bb.npc.meta["status"] = "working"
    bb.npc.meta["activity"] = "working"
    return NodeStatus.SUCCESS


async def action_enter_break(bb: NPCBlackboard) -> NodeStatus:
    """Transition NPC to BREAK state - move to cafe/lounge."""
    bb.npc_state = "BREAK"
    bb.state_timer = time.time()
    bb.state_duration = random.uniform(bb.break_duration_min, bb.break_duration_max)
    bb.npc.meta["status"] = "break"
    bb.npc.meta["activity"] = "break"
    
    # Choose a break room (cafe or lobby)
    bb.current_break_room = random.choice(bb.break_rooms)
    bb.target_room = bb.current_break_room
    
    # Get position in break room
    room = bb.game_server.rooms.get(bb.current_break_room)
    if room:
        # Find a good break spot (near cafe or sofa)
        from rooms import ROOM_CONFIGS
        room_config = ROOM_CONFIGS.get(bb.current_break_room, {})
        break_pos = None
        for furn in room_config.get("furniture", []):
            if furn["type"] in ["cafe", "coffee_machine", "sofa", "table", "counter"]:
                break_pos = (furn["x"] + furn["w"] // 2, furn["y"] + furn["h"] // 2)
                break
        if break_pos is None:
            break_pos = (room.width // 2, room.height // 2)
        bb.target_position = break_pos
    else:
        # Fallback to cafe
        bb.current_break_room = "cafe"
        bb.target_room = "cafe"
        positions = get_room_positions(bb.game_server, "cafe")
        cafe = positions.get("cafe", (3, 7))
        bb.target_position = cafe
    
    return NodeStatus.SUCCESS


async def action_enter_meeting(bb: NPCBlackboard) -> NodeStatus:
    """Transition NPC to MEETING state - move to meeting room."""
    bb.npc_state = "MEETING"
    bb.state_timer = time.time()
    bb.state_duration = random.uniform(bb.meeting_duration_min, bb.meeting_duration_max)
    bb.npc.meta["status"] = "meeting"
    bb.npc.meta["activity"] = "meeting"
    bb.in_scheduled_meeting = True
    bb.target_room = bb.meeting_room_id
    
    # Get meeting table position
    room = bb.game_server.rooms.get(bb.meeting_room_id)
    if room:
        positions = get_room_positions(bb.game_server, bb.meeting_room_id)
        table = positions.get("meeting_table", (room.width // 2, room.height // 2))
        bb.target_position = table
    
    return NodeStatus.SUCCESS


async def action_enter_idle(bb: NPCBlackboard) -> NodeStatus:
    """Transition NPC to IDLE state - wander or stay at desk."""
    bb.npc_state = "IDLE"
    bb.state_timer = time.time()
    bb.state_duration = random.uniform(bb.idle_duration_min, bb.idle_duration_max)
    bb.npc.meta["status"] = "idle"
    bb.npc.meta["activity"] = "idle"
    bb.in_scheduled_meeting = False
    return NodeStatus.SUCCESS


async def action_work_at_desk_state(bb: NPCBlackboard) -> NodeStatus:
    """NPC works at desk during WORKING state."""
    if not at_desk_area(bb):
        # Move to desk
        positions = get_room_positions(bb.game_server, bb.npc.room_id)
        desk = positions.get("desk_area")
        if desk:
            bb.target_position = desk
            bb.target_room = bb.npc.room_id
            return await action_move_to_target(bb)
    
    # At desk - work
    bb.npc.meta["status"] = "working"
    bb.npc.meta["activity"] = "typing"
    bb.set("work_progress", bb.get("work_progress", 0) + 1)
    bb.total_work_time += 1.0 / 20.0  # Assuming 20 ticks/second
    return NodeStatus.RUNNING


async def action_take_break(bb: NPCBlackboard) -> NodeStatus:
    """NPC takes break at cafe/lounge."""
    # If not at break location, move there
    if bb.npc.room_id != bb.current_break_room:
        bb.target_room = bb.current_break_room
        room = bb.game_server.rooms.get(bb.current_break_room)
        if room:
            positions = get_room_positions(bb.game_server, bb.current_break_room)
            # Try to find cafe/coffee area
            break_pos = positions.get("cafe", (room.width // 2, room.height // 2))
            bb.target_position = break_pos
            return await action_move_to_target(bb)
    elif not at_break_location(bb):
        # In break room but not at break spot - move to it
        room = bb.game_server.rooms.get(bb.current_break_room)
        if room:
            positions = get_room_positions(bb.game_server, bb.current_break_room)
            break_pos = positions.get("cafe", (room.width // 2, room.height // 2))
            bb.target_position = break_pos
            bb.target_room = bb.current_break_room
            return await action_move_to_target(bb)
    
    # At break location
    bb.npc.meta["status"] = "break"
    bb.npc.meta["activity"] = "break"
    bb.total_break_time += 1.0 / 20.0
    return NodeStatus.RUNNING


async def action_attend_meeting_state(bb: NPCBlackboard) -> NodeStatus:
    """NPC attends meeting in meeting room."""
    if bb.npc.room_id != bb.meeting_room_id:
        # Move to meeting room
        room = bb.game_server.rooms.get(bb.meeting_room_id)
        if room:
            positions = get_room_positions(bb.game_server, bb.meeting_room_id)
            table = positions.get("meeting_table", (room.width // 2, room.height // 2))
            bb.target_position = table
            bb.target_room = bb.meeting_room_id
            return await action_move_to_target(bb)
    
    # In meeting room
    bb.npc.meta["status"] = "meeting"
    bb.npc.meta["activity"] = "meeting"
    bb.total_meeting_time += 1.0 / 20.0
    return NodeStatus.RUNNING


async def action_idle_behavior(bb: NPCBlackboard) -> NodeStatus:
    """NPC idle behavior - wander or socialize."""
    # If at cafe, socialize
    if at_cafe(bb):
        bb.npc.meta["status"] = "idle"
        bb.npc.meta["activity"] = "socializing"
        return NodeStatus.RUNNING
    
    # Otherwise wander
    return await action_wander(bb)


async def action_update_state_machine(bb: NPCBlackboard) -> NodeStatus:
    """Main state machine update - handles timed transitions only."""
    current_time = time.time()
    
    # Check if NPC is currently moving to a target
    is_moving_to_target = bb.target_position is not None and bb.target_room is not None
    
    # If moving to target, check if we've arrived
    if is_moving_to_target:
        if bb.target_room == bb.npc.room_id:
            # Same room - check position
            tx, ty = bb.target_position
            if bb.npc.position.x == tx and bb.npc.position.y == ty:
                # Arrived! Start the state timer now
                bb.state_timer = time.time()
                bb.target_position = None
                bb.target_room = None
        else:
            # Different room - moving through doors, wait for room change to complete
            pass
        return NodeStatus.SUCCESS  # Still moving, let state sequences handle it
    
    # Not moving to target - check if current state timer expired
    if current_time - bb.state_timer >= bb.state_duration:
        # State expired - transition based on current state
        if bb.npc_state == "WORKING":
            # After working, chance to go to meeting or break
            if random.random() < bb.meeting_probability:
                # Schedule a meeting
                await action_enter_meeting(bb)
            else:
                # Take a break
                await action_enter_break(bb)
        
        elif bb.npc_state == "BREAK":
            # After break, go back to working
            await action_enter_working(bb)
        
        elif bb.npc_state == "MEETING":
            # After meeting, go back to working
            await action_enter_working(bb)
        
        elif bb.npc_state == "IDLE":
            # After idle, start working
            await action_enter_working(bb)
    
    # Also check for scheduled meetings (only when working and not moving)
    if bb.npc_state == "WORKING" and not is_moving_to_target and should_schedule_meeting(bb):
        await action_enter_meeting(bb)
    
    return NodeStatus.SUCCESS


async def action_schedule_random_meeting(bb: NPCBlackboard) -> NodeStatus:
    """Schedule a random future meeting."""
    # Schedule meeting in 5-30 minutes
    delay = random.uniform(300, 1800)
    bb.scheduled_meeting_time = time.time() + delay
    return NodeStatus.SUCCESS


def create_dev_behavior_tree(npc_entity, game_server) -> BehaviorTree:
    """
    Dev behavior: WORKING -> BREAK -> MEETING -> IDLE with timed transitions.
    """
    bb = NPCBlackboard(npc_entity, game_server)

    # Initialize state machine - start in IDLE, then transition to WORKING
    enter_working_action = Action("EnterWorking", action_enter_working)

    # State machine update - handles timed transitions
    update_state_machine = Action("UpdateStateMachine", action_update_state_machine)

    # Working behavior - work at desk
    work_sequence = Sequence("WorkSequence", [
        Action("WorkAtDesk", action_work_at_desk_state),
    ])

    # Break behavior - go to cafe/lounge
    break_sequence = Sequence("BreakSequence", [
        Action("TakeBreak", action_take_break),
    ])

    # Meeting behavior - attend meeting in meeting room
    meeting_sequence = Sequence("MeetingSequence", [
        Action("AttendMeeting", action_attend_meeting_state),
    ])

    # Idle behavior - wander or socialize
    idle_sequence = Sequence("IdleSequence", [
        Action("IdleBehavior", action_idle_behavior),
    ])

    # Main root selector - state machine drives behavior
    # First run state machine update, then state-specific sequences
    root = Sequence("DevBehaviorRoot", [
        # Crisis response takes priority (inline in sequence)
        Selector("CrisisOrStateMachine", [
            Sequence("CrisisResponse", [
                Condition("IsCrisis", is_crisis),
                Action("RespondToCrisis", action_respond_to_crisis),
            ]),
            # Update state machine (always runs if no crisis)
            update_state_machine,
        ]),
        # State-specific behaviors (Selector runs one matching state)
        Selector("StateBehaviors", [
            # Working state
            Sequence("Working", [
                Condition("IsStateWorking", is_state_working),
                work_sequence,
            ]),
            # Break state
            Sequence("Break", [
                Condition("IsStateBreak", is_state_break),
                break_sequence,
            ]),
            # Meeting state
            Sequence("Meeting", [
                Condition("IsStateMeeting", is_state_meeting),
                meeting_sequence,
            ]),
            # Idle state
            Sequence("Idle", [
                Condition("IsStateIdle", is_state_idle),
                idle_sequence,
            ]),
        ]),
        # Fallback: if no state set, enter working
        enter_working_action,
        # Sync with real agent
        Action("UpdateAgentStatus", action_update_agent_status),
    ])

    tree = BehaviorTree(root, "DevBehaviorTree")
    tree.blackboard = bb
    return tree


def create_devops_behavior_tree(npc_entity, game_server) -> BehaviorTree:
    """
    DevOps behavior: WORKING -> BREAK -> MEETING -> IDLE with timed transitions.
    Focus on monitoring, deployments, and incident response during WORKING state.
    """
    bb = NPCBlackboard(npc_entity, game_server)

    # Initialize state machine
    enter_working_action = Action("EnterWorking", action_enter_working)
    update_state_machine = Action("UpdateStateMachine", action_update_state_machine)

    # Working behavior - monitor systems, check deployments
    work_sequence = Sequence("WorkSequence", [
        Action("MonitorSystems", lambda bb: (bb.npc.meta.update({"activity": "monitoring"}), NodeStatus.RUNNING)[1]),
        Action("CheckDeployments", lambda bb: (bb.npc.meta.update({"activity": "checking_deploys"}), NodeStatus.RUNNING)[1]),
        Action("RespondToIncidents", lambda bb: (bb.npc.meta.update({"activity": "incident_response"}), NodeStatus.RUNNING)[1]),
    ])

    # Break behavior
    break_sequence = Sequence("BreakSequence", [
        Action("TakeBreak", action_take_break),
    ])

    # Meeting behavior
    meeting_sequence = Sequence("MeetingSequence", [
        Action("AttendMeeting", action_attend_meeting_state),
    ])

    # Idle behavior
    idle_sequence = Sequence("IdleSequence", [
        Action("IdleBehavior", action_idle_behavior),
    ])

    root = Selector("DevOpsBehavior", [
        # Crisis response takes priority
        Sequence("CrisisResponse", [
            Condition("IsCrisis", is_crisis),
            Action("RespondToCrisis", action_respond_to_crisis),
        ]),
        # Update state machine
        update_state_machine,
        # Working state
        Sequence("Working", [
            Condition("IsStateWorking", is_state_working),
            work_sequence,
        ]),
        # Break state
        Sequence("Break", [
            Condition("IsStateBreak", is_state_break),
            break_sequence,
        ]),
        # Meeting state
        Sequence("Meeting", [
            Condition("IsStateMeeting", is_state_meeting),
            meeting_sequence,
        ]),
        # Idle state
        Sequence("Idle", [
            Condition("IsStateIdle", is_state_idle),
            idle_sequence,
        ]),
        # Fallback
        enter_working_action,
        Action("UpdateAgentStatus", action_update_agent_status),
    ])

    tree = BehaviorTree(root, "DevOpsBehaviorTree")
    tree.blackboard = bb
    return tree


def create_researcher_behavior_tree(npc_entity, game_server) -> BehaviorTree:
    """
    Researcher behavior: WORKING -> BREAK -> MEETING -> IDLE with timed transitions.
    Focus on reading, analyzing, writing during WORKING state.
    """
    bb = NPCBlackboard(npc_entity, game_server)

    enter_working_action = Action("EnterWorking", action_enter_working)
    update_state_machine = Action("UpdateStateMachine", action_update_state_machine)

    work_sequence = Sequence("WorkSequence", [
        Action("ReadPapers", lambda bb: (bb.npc.meta.update({"activity": "reading"}), NodeStatus.RUNNING)[1]),
        Action("AnalyzeData", lambda bb: (bb.npc.meta.update({"activity": "analyzing"}), NodeStatus.RUNNING)[1]),
        Action("WriteReport", lambda bb: (bb.npc.meta.update({"activity": "writing"}), NodeStatus.RUNNING)[1]),
    ])

    break_sequence = Sequence("BreakSequence", [
        Action("TakeBreak", action_take_break),
    ])

    meeting_sequence = Sequence("MeetingSequence", [
        Action("AttendMeeting", action_attend_meeting_state),
    ])

    idle_sequence = Sequence("IdleSequence", [
        Action("IdleBehavior", action_idle_behavior),
    ])

    root = Selector("ResearcherBehavior", [
        Sequence("CrisisResponse", [
            Condition("IsCrisis", is_crisis),
            Action("RespondToCrisis", action_respond_to_crisis),
        ]),
        update_state_machine,
        Sequence("Working", [
            Condition("IsStateWorking", is_state_working),
            work_sequence,
        ]),
        Sequence("Break", [
            Condition("IsStateBreak", is_state_break),
            break_sequence,
        ]),
        Sequence("Meeting", [
            Condition("IsStateMeeting", is_state_meeting),
            meeting_sequence,
        ]),
        Sequence("Idle", [
            Condition("IsStateIdle", is_state_idle),
            idle_sequence,
        ]),
        enter_working_action,
        Action("UpdateAgentStatus", action_update_agent_status),
    ])

    tree = BehaviorTree(root, "ResearcherBehaviorTree")
    tree.blackboard = bb
    return tree


def create_watchdog_behavior_tree(npc_entity, game_server) -> BehaviorTree:
    """
    Watchdog behavior: WORKING -> BREAK -> MEETING -> IDLE with timed transitions.
    Focus on patrolling, investigating alerts during WORKING state.
    """
    bb = NPCBlackboard(npc_entity, game_server)

    enter_working_action = Action("EnterWorking", action_enter_working)
    update_state_machine = Action("UpdateStateMachine", action_update_state_machine)

    work_sequence = Sequence("WorkSequence", [
        Action("Patrol", action_patrol),
        Condition("AlertCooldownReady", alert_cooldown_ready),
        Condition("AlertRateLimitOk", alert_rate_limit_ok),
        Action("CleanupExpiredAlertLogs", cleanup_expired_alert_logs),
        Action("InvestigateAlert", action_investigate_alert),
        Action("AssessThreat", lambda bb: (bb.npc.meta.update({"activity": "assessing"}), NodeStatus.RUNNING)[1]),
    ])

    break_sequence = Sequence("BreakSequence", [
        Action("TakeBreak", action_take_break),
    ])

    meeting_sequence = Sequence("MeetingSequence", [
        Action("AttendMeeting", action_attend_meeting_state),
    ])

    idle_sequence = Sequence("IdleSequence", [
        Action("IdleBehavior", action_idle_behavior),
    ])

    root = Selector("WatchdogBehavior", [
        # Crisis/Alert takes highest priority
        Sequence("CrisisResponse", [
            Condition("AgentAlertActive", agent_alert_active),
            Action("RespondToCrisis", action_respond_to_crisis),
        ]),
        update_state_machine,
        Sequence("Working", [
            Condition("IsStateWorking", is_state_working),
            work_sequence,
        ]),
        Sequence("Break", [
            Condition("IsStateBreak", is_state_break),
            break_sequence,
        ]),
        Sequence("Meeting", [
            Condition("IsStateMeeting", is_state_meeting),
            meeting_sequence,
        ]),
        Sequence("Idle", [
            Condition("IsStateIdle", is_state_idle),
            idle_sequence,
        ]),
        enter_working_action,
        Action("UpdateAgentStatus", action_update_agent_status),
    ])

    tree = BehaviorTree(root, "WatchdogBehaviorTree")
    tree.blackboard = bb
    return tree


def create_ceo_behavior_tree(npc_entity, game_server) -> BehaviorTree:
    """
    CEO behavior: WORKING -> BREAK -> MEETING -> IDLE with timed transitions.
    Focus on meetings, decisions, delegations during WORKING state.
    """
    bb = NPCBlackboard(npc_entity, game_server)

    enter_working_action = Action("EnterWorking", action_enter_working)
    update_state_machine = Action("UpdateStateMachine", action_update_state_machine)

    work_sequence = Sequence("WorkSequence", [
        Action("ReviewMetrics", lambda bb: (bb.npc.meta.update({"activity": "reviewing"}), NodeStatus.RUNNING)[1]),
        Action("MakeDecision", action_ceo_decide),
        Action("DelegateTasks", action_ceo_delegate),
        Action("FollowUp", lambda bb: (bb.npc.meta.update({"activity": "following_up"}), NodeStatus.RUNNING)[1]),
    ])

    break_sequence = Sequence("BreakSequence", [
        Action("TakeBreak", action_take_break),
    ])

    meeting_sequence = Sequence("MeetingSequence", [
        Action("AttendMeeting", action_attend_meeting_state),
    ])

    idle_sequence = Sequence("IdleSequence", [
        Action("IdleBehavior", action_idle_behavior),
    ])

    root = Selector("CEOBehavior", [
        Sequence("CrisisResponse", [
            Condition("IsCrisis", is_crisis),
            Action("RespondToCrisis", action_respond_to_crisis),
        ]),
        update_state_machine,
        Sequence("Working", [
            Condition("IsStateWorking", is_state_working),
            work_sequence,
        ]),
        Sequence("Break", [
            Condition("IsStateBreak", is_state_break),
            break_sequence,
        ]),
        Sequence("Meeting", [
            Condition("IsStateMeeting", is_state_meeting),
            meeting_sequence,
        ]),
        Sequence("Idle", [
            Condition("IsStateIdle", is_state_idle),
            idle_sequence,
        ]),
        enter_working_action,
        Action("UpdateAgentStatus", action_update_agent_status),
    ])

    tree = BehaviorTree(root, "CEOBehaviorTree")
    tree.blackboard = bb
    return tree


# ---- Factory Function ----

def create_behavior_tree_for_role(role: str, npc_entity, game_server) -> BehaviorTree:
    """Create the appropriate behavior tree for an NPC role."""
    trees = {
        "dev": create_dev_behavior_tree,
        "devops": create_devops_behavior_tree,
        "researcher": create_researcher_behavior_tree,
        "watchdog": create_watchdog_behavior_tree,
        "ceo": create_ceo_behavior_tree,
    }
    
    factory = trees.get(role.lower())
    if factory:
        return factory(npc_entity, game_server)
    
    # Default: simple idle/wander tree
    bb = NPCBlackboard(npc_entity, game_server)
    root = Selector("DefaultBehavior", [
        Action("Wander", action_wander),
    ])
    tree = BehaviorTree(root, "DefaultBehaviorTree")
    tree.blackboard = bb
    return tree


# Position class (imported locally to avoid circular dependency)
@dataclass
class Position:
    x: int
    y: int
    
    def to_dict(self):
        return {"x": self.x, "y": self.y}