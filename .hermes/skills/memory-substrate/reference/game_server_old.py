#!/usr/bin/env python3
"""
Hermes-Corp Game Server — WebSocket Server for Frontend
Connects: Frontend (ws://localhost:8081) ↔ Supervisor (3120) + Memory Substrate (8767)
"""

import asyncio
import json
import logging
import uuid
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from enum import Enum

import aiohttp
from aiohttp import web, WSMsgType

# Import behavior trees
from npc_behaviors import (
    BehaviorTree,
    NPCBlackboard,
    create_behavior_tree_for_role,
    get_agent_status_from_supervisor,
)

# Setup logging
LOG_DIR = Path.home() / "AppData" / "Local" / "hermes" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "game_server.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("game_server")

# Configuration
SUPERVISOR_URL = "http://127.0.0.1:3120/rpc"
SUPERVISOR_WS_URL = "ws://127.0.0.1:3120/ws"
MEMORY_SUBSTRATE_URL = "http://127.0.0.1:8767"
GAME_SERVER_PORT = 8081
WS_PATH = "/ws"

# Game constants
TILE_SIZE = 32
VIEWPORT_W = 1280
VIEWPORT_H = 960
TICK_RATE = 20  # Hz
DELTA_BROADCAST_HZ = 2

# Door coordinates for room transitions
# Dev Room (dev_room) <-> Ops Room (ops_room): door tiles at x=39, y=14,15,16
# Dev Room (dev_room) <-> Reception (reception): door at x=12, y=29
# Ops Room (ops_room) <-> Reception (reception): door at x=49, y=29
# Note: These are in each room's local coordinate system
DOOR_COORDS = {
    "dev_room": {
        "to_ops_room": [{"x": 39, "y": 14}, {"x": 39, "y": 15}, {"x": 39, "y": 16}],
        "to_reception": [{"x": 12, "y": 29}],
    },
    "ops_room": {
        "to_dev_room": [{"x": 0, "y": 14}, {"x": 0, "y": 15}, {"x": 0, "y": 16}],  # Left edge of ops_room
        "to_reception": [{"x": 9, "y": 29}],  # Bottom edge of ops_room (width=20, height=30)
    },
    "reception": {
        "to_dev_room": [{"x": 12, "y": 0}],  # Top edge of reception
        "to_ops_room": [{"x": 49, "y": 0}],  # Top edge of reception
    }
}

# Internal walls for each room (perimeter walls + internal walls)
# Format: [{"x": x, "y": y, "w": width, "h": height}, ...] - all tiles in rect are blocked
INTERNAL_WALLS = {
    "dev_room": [
        # Perimeter walls
        {"x": 0, "y": 0, "w": 40, "h": 1},      # Top
        {"x": 0, "y": 29, "w": 40, "h": 1},     # Bottom
        {"x": 0, "y": 0, "w": 1, "h": 30},      # Left
        {"x": 39, "y": 0, "w": 1, "h": 30},     # Right (except doors at y=14,15,16)
        # Internal walls - desk cluster dividers
        {"x": 13, "y": 1, "w": 1, "h": 9},      # Vertical divider top section (y=1-9)
        {"x": 13, "y": 11, "w": 1, "h": 7},     # Vertical divider middle section (y=11-17)
        {"x": 13, "y": 19, "w": 1, "h": 10},    # Vertical divider bottom section (y=19-28)
        # Horizontal corridor walls (with gap at x=13 for cross-corridor)
        {"x": 1, "y": 10, "w": 12, "h": 1},     # Horizontal wall top section (x=1-12)
        {"x": 14, "y": 10, "w": 25, "h": 1},    # Horizontal wall middle section (x=14-38)
        {"x": 1, "y": 18, "w": 12, "h": 1},     # Horizontal wall lower section (x=1-12)
        {"x": 14, "y": 18, "w": 25, "h": 1},    # Horizontal wall lower middle (x=14-38)
    ],
    "ops_room": [
        # Perimeter walls
        {"x": 0, "y": 0, "w": 20, "h": 1},      # Top
        {"x": 0, "y": 29, "w": 20, "h": 1},     # Bottom (except door at x=9)
        {"x": 0, "y": 0, "w": 1, "h": 30},      # Left (except doors at y=14,15,16)
        {"x": 19, "y": 0, "w": 1, "h": 30},     # Right
        # Internal walls - server rack aisles
        {"x": 5, "y": 1, "w": 1, "h": 28},      # Vertical aisle divider
        {"x": 12, "y": 1, "w": 1, "h": 28},     # Another vertical divider
        # Horizontal dividers
        {"x": 1, "y": 10, "w": 4, "h": 1},      # Top section
        {"x": 6, "y": 10, "w": 6, "h": 1},      # Middle section
        {"x": 13, "y": 10, "w": 6, "h": 1},     # Right section
        {"x": 1, "y": 20, "w": 18, "h": 1},     # Lower divider
    ],
    "reception": [
        # Perimeter walls
        {"x": 0, "y": 0, "w": 60, "h": 1},      # Top (except doors at x=12, x=49)
        {"x": 0, "y": 14, "w": 60, "h": 1},     # Bottom
        {"x": 0, "y": 0, "w": 1, "h": 15},      # Left
        {"x": 59, "y": 0, "w": 1, "h": 15},     # Right
        # Internal walls - reception area dividers
        {"x": 26, "y": 2, "w": 8, "h": 1},      # Reception desk back wall
        {"x": 5, "y": 6, "w": 1, "h": 8},       # Left seating divider
        {"x": 54, "y": 6, "w": 1, "h": 8},      # Right seating divider
    ],
    "meeting_room_1": [
        {"x": 0, "y": 0, "w": 15, "h": 1},
        {"x": 0, "y": 9, "w": 15, "h": 1},
        {"x": 0, "y": 0, "w": 1, "h": 10},
        {"x": 14, "y": 0, "w": 1, "h": 10},
    ],
    "cafe": [
        {"x": 0, "y": 0, "w": 20, "h": 1},
        {"x": 0, "y": 14, "w": 20, "h": 1},
        {"x": 0, "y": 0, "w": 1, "h": 15},
        {"x": 19, "y": 0, "w": 1, "h": 15},
    ],
    "vault": [
        {"x": 0, "y": 0, "w": 18, "h": 1},
        {"x": 0, "y": 13, "w": 18, "h": 1},
        {"x": 0, "y": 0, "w": 1, "h": 14},
        {"x": 17, "y": 0, "w": 1, "h": 14},
    ],
    "lab": [
        {"x": 0, "y": 0, "w": 22, "h": 1},
        {"x": 0, "y": 14, "w": 22, "h": 1},
        {"x": 0, "y": 0, "w": 1, "h": 15},
        {"x": 21, "y": 0, "w": 1, "h": 15},
    ],
}


# ============================================================
# Room Configurations - 3 Room Layout with Internal Walls & Doors
# ============================================================

# World layout (global coordinates):
# Dev Room:      x=0-39,  y=0-29    (width=40, height=30)
# Ops Room:      x=40-59, y=0-29    (width=20, height=30)
# Reception:     x=0-59,  y=30-44   (width=60, height=15)
#
# Internal walls with doors:
# - Dev Room <-> Ops Room: vertical wall at x=39/40, door at y=14-16 (3 tiles)
# - Dev Room <-> Reception: horizontal wall at y=29/30, door at x=12 (1 tile)
# - Ops Room <-> Reception: horizontal wall at y=29/30, door at x=49 (1 tile)

ROOM_CONFIGS = {
    "dev_room": {
        "id": "dev_room",
        "name": "Dev Room (Sala de Desenvolvimento)",
        "width": 40,
        "height": 30,
        "is_meeting": False,
        "capacity": 20,
        "description": "Open-plan developer workspace with 6 desks",
        "furniture": [
            # Desk clusters - 3 rows of 2 clusters each
            {"type": "desk_cluster", "x": 4, "y": 4, "w": 8, "h": 6, "sprite": "furniture_desk_cluster"},
            {"type": "desk_cluster", "x": 16, "y": 4, "w": 8, "h": 6, "sprite": "furniture_desk_cluster"},
            {"type": "desk_cluster", "x": 4, "y": 12, "w": 8, "h": 6, "sprite": "furniture_desk_cluster"},
            {"type": "desk_cluster", "x": 16, "y": 12, "w": 8, "h": 6, "sprite": "furniture_desk_cluster"},
            {"type": "desk_cluster", "x": 4, "y": 20, "w": 8, "h": 6, "sprite": "furniture_desk_cluster"},
            {"type": "desk_cluster", "x": 16, "y": 20, "w": 8, "h": 6, "sprite": "furniture_desk_cluster"},
            # Whiteboards
            {"type": "whiteboard", "x": 35, "y": 4, "w": 4, "h": 2, "sprite": "furniture_whiteboard"},
            {"type": "whiteboard", "x": 35, "y": 12, "w": 4, "h": 2, "sprite": "furniture_whiteboard"},
            {"type": "whiteboard", "x": 35, "y": 20, "w": 4, "h": 2, "sprite": "furniture_whiteboard"},
            # Plants at corners
            {"type": "plant", "x": 2, "y": 2, "w": 1, "h": 1, "sprite": "furniture_plant"},
            {"type": "plant", "x": 37, "y": 2, "w": 1, "h": 1, "sprite": "furniture_plant"},
            {"type": "plant", "x": 2, "y": 27, "w": 1, "h": 1, "sprite": "furniture_plant"},
            {"type": "plant", "x": 37, "y": 27, "w": 1, "h": 1, "sprite": "furniture_plant"},
            # Water cooler
            {"type": "water_cooler", "x": 35, "y": 26, "w": 1, "h": 1, "sprite": "furniture_water_cooler"},
        ],
        "doors": [
            # Dev Room <-> Ops Room: vertical door at x=39 (Dev side), connecting to Ops x=0
            {"x": 39, "y": 14, "target_room": "ops_room", "target_x": 0, "target_y": 14, "width": 1, "label": "To Ops Room"},
            {"x": 39, "y": 15, "target_room": "ops_room", "target_x": 0, "target_y": 15, "width": 1, "label": "To Ops Room"},
            {"x": 39, "y": 16, "target_room": "ops_room", "target_x": 0, "target_y": 16, "width": 1, "label": "To Ops Room"},
            # Dev Room <-> Reception: horizontal door at y=29 (Dev side), connecting to Reception y=0
            {"x": 12, "y": 29, "target_room": "reception", "target_x": 12, "target_y": 0, "width": 1, "label": "To Reception"},
        ],
        "npc_spawns": [
            # 6 Dev desks positions - placed at adjacent walkable tiles (not on desks)
            # Desk cluster 1 at (4,4) w=8,h=6 -> walkable area around it
            {"role": "dev", "x": 7, "y": 3, "sprite": "avatar_dev", "name": "Dev Alice"},    # Top of desk 1
            {"role": "dev", "x": 12, "y": 7, "sprite": "avatar_dev", "name": "Dev Bruno"},   # Right of desk 1
            {"role": "dev", "x": 19, "y": 3, "sprite": "avatar_dev", "name": "Dev Carlos"},  # Top of desk 2
            {"role": "dev", "x": 24, "y": 7, "sprite": "avatar_dev", "name": "Dev Diana"},   # Right of desk 2
            {"role": "dev", "x": 7, "y": 11, "sprite": "avatar_dev", "name": "Dev Eduardo"}, # Bottom of desk 3
            {"role": "dev", "x": 12, "y": 15, "sprite": "avatar_dev", "name": "Dev Fernanda"},# Right of desk 3
        ]
    },
    "ops_room": {
        "id": "ops_room",
        "name": "Ops Room (Sala de Operações)",
        "width": 20,
        "height": 30,
        "is_meeting": False,
        "capacity": 8,
        "description": "Infrastructure monitoring and DevOps workspace - isolated log flow",
        "furniture": [
            # Server racks along east wall
            {"type": "server_rack", "x": 17, "y": 2, "w": 2, "h": 8, "sprite": "furniture_server_rack"},
            {"type": "server_rack", "x": 17, "y": 12, "w": 2, "h": 8, "sprite": "furniture_server_rack"},
            {"type": "server_rack", "x": 17, "y": 22, "w": 2, "h": 8, "sprite": "furniture_server_rack"},
            # Monitoring station
            {"type": "monitoring_station", "x": 5, "y": 2, "w": 8, "h": 4, "sprite": "furniture_monitoring_station"},
            # DevOps desk
            {"type": "desk_cluster", "x": 5, "y": 12, "w": 8, "h": 6, "sprite": "furniture_desk_cluster"},
            # Watchdog station
            {"type": "monitoring_station", "x": 5, "y": 20, "w": 8, "h": 4, "sprite": "furniture_monitoring_station"},
            # UPS units
            {"type": "ups_unit", "x": 1, "y": 2, "w": 2, "h": 2, "sprite": "furniture_ups"},
            {"type": "ups_unit", "x": 1, "y": 26, "w": 2, "h": 2, "sprite": "furniture_ups"},
            # Cooling units
            {"type": "cooling_unit", "x": 0, "y": 10, "w": 1, "h": 2, "sprite": "furniture_cooling"},
            {"type": "cooling_unit", "x": 0, "y": 20, "w": 1, "h": 2, "sprite": "furniture_cooling"},
            # Plants
            {"type": "plant", "x": 1, "y": 1, "w": 1, "h": 1, "sprite": "furniture_plant"},
            {"type": "plant", "x": 1, "y": 28, "w": 1, "h": 1, "sprite": "furniture_plant"},
        ],
        "doors": [
            # Ops Room <-> Dev Room: vertical door at x=0 (Ops side), connecting to Dev x=39
            {"x": 0, "y": 14, "target_room": "dev_room", "target_x": 39, "target_y": 14, "width": 1, "label": "To Dev Room"},
            {"x": 0, "y": 15, "target_room": "dev_room", "target_x": 39, "target_y": 15, "width": 1, "label": "To Dev Room"},
            {"x": 0, "y": 16, "target_room": "dev_room", "target_x": 39, "target_y": 16, "width": 1, "label": "To Dev Room"},
            # Ops Room <-> Reception: horizontal door at y=29 (Ops side), connecting to Reception y=0
            {"x": 9, "y": 29, "target_room": "reception", "target_x": 49, "target_y": 0, "width": 1, "label": "To Reception"},
        ],
        "npc_spawns": [
            {"role": "devops", "x": 9, "y": 15, "sprite": "avatar_devops", "name": "DevOps Bob"},
            {"role": "watchdog", "x": 9, "y": 22, "sprite": "avatar_watchdog", "name": "Watchdog"},
        ]
    },
    "reception": {
        "id": "reception",
        "name": "Reception / Common Area (Recepção / Área Comum)",
        "width": 60,
        "height": 15,
        "is_meeting": False,
        "capacity": 30,
        "description": "Neutral spawn area - player spawns here, connects to Dev Room and Ops Room",
        "furniture": [
            # Reception desk at center-top
            {"type": "reception_desk", "x": 28, "y": 2, "w": 4, "h": 2, "sprite": "furniture_reception"},
            # Sofas on sides
            {"type": "sofa", "x": 4, "y": 8, "w": 4, "h": 2, "sprite": "furniture_sofa"},
            {"type": "sofa", "x": 52, "y": 8, "w": 4, "h": 2, "sprite": "furniture_sofa"},
            # Coffee tables
            {"type": "coffee_table", "x": 6, "y": 10, "w": 2, "h": 1, "sprite": "furniture_coffee_table"},
            {"type": "coffee_table", "x": 52, "y": 10, "w": 2, "h": 1, "sprite": "furniture_coffee_table"},
            # Plants at corners
            {"type": "plant", "x": 2, "y": 1, "w": 1, "h": 1, "sprite": "furniture_plant"},
            {"type": "plant", "x": 57, "y": 1, "w": 1, "h": 1, "sprite": "furniture_plant"},
            {"type": "plant", "x": 2, "y": 13, "w": 1, "h": 1, "sprite": "furniture_plant"},
            {"type": "plant", "x": 57, "y": 13, "w": 1, "h": 1, "sprite": "furniture_plant"},
            # Additional plants near doors
            {"type": "plant", "x": 10, "y": 1, "w": 1, "h": 1, "sprite": "furniture_plant"},
            {"type": "plant", "x": 14, "y": 1, "w": 1, "h": 1, "sprite": "furniture_plant"},
            {"type": "plant", "x": 47, "y": 1, "w": 1, "h": 1, "sprite": "furniture_plant"},
            {"type": "plant", "x": 51, "y": 1, "w": 1, "h": 1, "sprite": "furniture_plant"},
        ],
        "doors": [
            # Reception <-> Dev Room: horizontal door at y=0 (Reception side), connecting to Dev y=29
            {"x": 12, "y": 0, "target_room": "dev_room", "target_x": 12, "target_y": 29, "width": 1, "label": "To Dev Room"},
            # Reception <-> Ops Room: horizontal door at y=0 (Reception side), connecting to Ops y=29
            {"x": 49, "y": 0, "target_room": "ops_room", "target_x": 9, "target_y": 29, "width": 1, "label": "To Ops Room"},
        ],
        "npc_spawns": [
            {"role": "receptionist", "x": 30, "y": 5, "sprite": "avatar_dev", "name": "Receptionist Maya"},
        ]
    },
}


class EntityType(Enum):
    PLAYER = "player"
    NPC = "npc"
    FURNITURE = "furniture"
    ARTIFACT = "artifact"


class MessageType(Enum):
    # Client -> Server
    HELLO = "client.hello"
    ENTITY_MOVE = "entity.move"
    CHAT_MESSAGE = "chat.message"
    MEETING_INVITE_REQ = "meeting.invite"
    MEETING_JOIN = "meeting.join"
    MEETING_LEAVE = "meeting.leave"
    NPC_DIALOGUE_REQUEST = "npc.dialogue.request"
    WORLD_SYNC_REQUEST = "world.sync.request"
    
    # Server -> Client
    WELCOME = "welcome"
    ENTITY_SPAWN = "entity.spawn"
    ENTITY_MOVE_ACK = "entity.move"
    ENTITY_DESPAWN = "entity.despawn"
    CHAT_MESSAGE_RECV = "chat.message"
    MEETING_INVITE = "meeting.invite"
    MEETING_STATE = "meeting.state"
    NPC_DIALOGUE_RESPONSE = "npc.dialogue.response"
    NPC_ACTION = "npc.action"
    WORLD_STATE_DELTA = "world.state.delta"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"

    # NPC Dialogue
    NPC_DIALOGUE_ACTION = "npc.dialogue.action"

    # HUD Metrics
    HUD_METRICS = "hud.metrics"
    HUD_CIRCUIT = "hud.circuit"
    HUD_WATCHDOG = "hud.watchdog"
    HUD_TASKS = "hud.tasks"
    HUD_AGENTS = "hud.agents"

    # Pathfinding
    PATHFIND_REQUEST = "pathfind.request"
    PATHFIND_RESPONSE = "pathfind.response"


@dataclass
class Position:
    x: int
    y: int
    
    def to_dict(self):
        return {"x": self.x, "y": self.y}


@dataclass
class Entity:
    id: str
    type: str  # player, npc, furniture, artifact
    room_id: str
    position: Position
    sprite: str
    meta: Dict = field(default_factory=dict)
    owner_id: Optional[str] = None
    
    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "room_id": self.room_id,
            "position": self.position.to_dict(),
            "sprite": self.sprite,
            "meta": self.meta,
            "owner_id": self.owner_id
        }


@dataclass
class Room:
    id: str
    name: str
    width: int
    height: int
    is_meeting: bool = False
    capacity: int = 8
    entities: Dict[str, Entity] = field(default_factory=dict)
    collision_grid: List[List[bool]] = field(default_factory=list)
    doors: List[Dict] = field(default_factory=list)
    
    def __post_init__(self):
        self._build_collision_grid()
    
    def _build_collision_grid(self):
        """Build collision grid with perimeter walls, internal walls, and furniture.
        Door tiles are kept walkable (False)."""
        # Start with empty grid (all walkable)
        self.collision_grid = [[False for _ in range(self.width)] for _ in range(self.height)]
        
        # Add internal walls (perimeter + internal)
        if self.id in INTERNAL_WALLS:
            for wall in INTERNAL_WALLS[self.id]:
                for wx in range(wall["x"], wall["x"] + wall["w"]):
                    for wy in range(wall["y"], wall["y"] + wall["h"]):
                        if 0 <= wx < self.width and 0 <= wy < self.height:
                            self.collision_grid[wy][wx] = True
        
        # Make door tiles walkable (override walls)
        if self.id in DOOR_COORDS:
            for door_set in DOOR_COORDS[self.id].values():
                for door in door_set:
                    dx, dy = door["x"], door["y"]
                    if 0 <= dx < self.width and 0 <= dy < self.height:
                        self.collision_grid[dy][dx] = False
    
    def rebuild_collision_grid(self):
        """Rebuild collision grid from walls, then add current furniture/entities."""
        self._build_collision_grid()
        # Re-add furniture and entities (but NOT player - player's position should be walkable for pathfinding)
        for entity in self.entities.values():
            if entity.type in ("furniture", "npc"):  # Exclude player
                if 0 <= entity.position.x < self.width and 0 <= entity.position.y < self.height:
                    self.collision_grid[entity.position.y][entity.position.x] = True
        # Explicitly ensure any player in this room is walkable
        for entity in self.entities.values():
            if entity.type == "player" and entity.room_id == self.id:
                px, py = entity.position.x, entity.position.y
                if 0 <= px < self.width and 0 <= py < self.height:
                    self.collision_grid[py][px] = False
    
    def is_walkable(self, x: int, y: int) -> bool:
        """Check if a tile is walkable (not blocked by wall, furniture, or entity)."""
        if not (0 <= x < self.width and 0 <= y < self.height):
            return False
        return not self.collision_grid[y][x]

    def add_entity(self, entity: Entity):
        self.entities[entity.id] = entity
        # Don't add player to collision grid - player position should be walkable
        if entity.type != "player" and 0 <= entity.position.x < self.width and 0 <= entity.position.y < self.height:
            self.collision_grid[entity.position.y][entity.position.x] = True

    def remove_entity(self, entity_id: str):
        if entity_id in self.entities:
            entity = self.entities[entity_id]
            if 0 <= entity.position.x < self.width and 0 <= entity.position.y < self.height:
                self.collision_grid[entity.position.y][entity.position.x] = False
            del self.entities[entity_id]

    def move_entity(self, entity_id: str, new_x: int, new_y: int) -> bool:
        if entity_id not in self.entities:
            return False

        entity = self.entities[entity_id]
        old_x, old_y = entity.position.x, entity.position.y

        if not (0 <= new_x < self.width and 0 <= new_y < self.height):
            return False
        # Allow player to move even if collision_grid marks it (player position is kept walkable)
        if self.collision_grid[new_y][new_x] and entity.type != "player":
            return False

        self.collision_grid[old_y][old_x] = False
        # Only mark new position as blocked for non-player entities
        if entity.type != "player":
            self.collision_grid[new_y][new_x] = True
        entity.position = Position(new_x, new_y)
        return True

    def find_path(self, start_x: int, start_y: int, goal_x: int, goal_y: int) -> List[Position]:
        """A* pathfinding using room-specific collision grid.
        Returns list of Positions from start to goal (inclusive), or empty list if no path."""
        if not (0 <= start_x < self.width and 0 <= start_y < self.height):
            return []
        if not (0 <= goal_x < self.width and 0 <= goal_y < self.height):
            return []
        # Allow start position even if marked as blocked (entity is already there)
        if self.collision_grid[goal_y][goal_x]:
            return []
        if start_x == goal_x and start_y == goal_y:
            return [Position(start_x, start_y)]

        # A* algorithm
        import heapq

        def heuristic(x1, y1, x2, y2):
            return abs(x1 - x2) + abs(y1 - y2)  # Manhattan distance

        open_set = []
        start_key = (start_x, start_y)
        heapq.heappush(open_set, (heuristic(start_x, start_y, goal_x, goal_y), 0, start_x, start_y))

        came_from = {}
        g_score = {start_key: 0}
        f_score = {start_key: heuristic(start_x, start_y, goal_x, goal_y)}
        closed_set = set()

        directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]  # 4-directional movement

        while open_set:
            current_f, current_g, current_x, current_y = heapq.heappop(open_set)
            current_key = (current_x, current_y)

            # Skip if already processed with better score (stale heap entry)
            if current_key in closed_set:
                continue
            if current_g > g_score.get(current_key, float('inf')):
                continue

            if current_x == goal_x and current_y == goal_y:
                # Reconstruct path
                path = []
                curr = current_key
                while curr in came_from:
                    path.append(Position(curr[0], curr[1]))
                    curr = came_from[curr]
                path.append(Position(start_x, start_y))
                path.reverse()
                return path

            closed_set.add(current_key)

            for dx, dy in directions:
                nx, ny = current_x + dx, current_y + dy
                neighbor_key = (nx, ny)

                if not (0 <= nx < self.width and 0 <= ny < self.height):
                    continue
                if self.collision_grid[ny][nx]:  # Blocked
                    continue
                if neighbor_key in closed_set:
                    continue

                tentative_g = current_g + 1

                if neighbor_key not in g_score or tentative_g < g_score[neighbor_key]:
                    came_from[neighbor_key] = current_key
                    g_score[neighbor_key] = tentative_g
                    f = tentative_g + heuristic(nx, ny, goal_x, goal_y)
                    f_score[neighbor_key] = f
                    heapq.heappush(open_set, (f, tentative_g, nx, ny))

        return []  # No path found


@dataclass
class ClientConnection:
    ws: web.WebSocketResponse
    entity_id: Optional[str] = None
    room_id: Optional[str] = None
    seq: int = 0
    last_ping: float = field(default_factory=time.time)


class GameServer:
    def __init__(self):
        self.rooms: Dict[str, Room] = {}
        self.entities: Dict[str, Entity] = {}
        self.clients: Dict[str, ClientConnection] = {}
        self.supervisor_session: Optional[aiohttp.ClientSession] = None
        self.memory_session: Optional[aiohttp.ClientSession] = None
        self.running = False
        self._tick_task: Optional[asyncio.Task] = None
        self._delta_broadcast_task: Optional[asyncio.Task] = None
        self._last_tick = time.time()
        
        # NPC behavior trees
        self.npc_behavior_trees: Dict[str, BehaviorTree] = {}
        
        # Initialize default world
        self._init_world()
    
    def _init_world(self):
        """Create default rooms and NPCs from ROOM_CONFIGS."""
        # Create all rooms from configs
        for room_id, config in ROOM_CONFIGS.items():
            room = Room(
                id=config["id"],
                name=config["name"],
                width=config["width"],
                height=config["height"],
                is_meeting=config["is_meeting"],
                capacity=config["capacity"],
                doors=config.get("doors", [])
            )
            self.rooms[room_id] = room
        
            # Add furniture as entities
            for i, furn in enumerate(config.get("furniture", [])):
                furn_id = f"furn_{room_id}_{furn['type']}_{i}"
                for fx in range(furn["w"]):
                    for fy in range(furn["h"]):
                        furn_entity = Entity(
                            id=f"{furn_id}_{fx}_{fy}",
                            type="furniture",
                            room_id=room_id,
                            position=Position(furn["x"] + fx, furn["y"] + fy),
                            sprite=furn["sprite"],
                            meta={"furniture_type": furn["type"], "parent_id": furn_id}
                        )
                        self.entities[furn_entity.id] = furn_entity
                        room.add_entity(furn_entity)
        
            # Spawn NPCs for this room
            for npc_config in config.get("npc_spawns", []):
                npc_id = f"npc-{npc_config['role']}-{room_id}-{npc_config['x']}-{npc_config['y']}"
                entity = Entity(
                    id=npc_id,
                    type="npc",
                    room_id=room_id,
                    position=Position(npc_config["x"], npc_config["y"]),
                    sprite=npc_config["sprite"],
                    meta={
                        "name": npc_config["name"],
                        "role": npc_config["role"],
                        "status": "idle",
                        "direction": "down",
                        "home_room": room_id,
                        "preferred_rooms": self._get_preferred_rooms(npc_config["role"])
                    }
                )
                self.entities[npc_id] = entity
                room.add_entity(entity)
              
                # Create behavior tree for this NPC
                behavior_tree = create_behavior_tree_for_role(npc_config["role"], entity, self)
                self.npc_behavior_trees[npc_id] = behavior_tree
            
            # Rebuild collision grid after all furniture and NPCs are added
            room.rebuild_collision_grid()

        logger.info(f"World initialized: {len(self.rooms)} rooms, {len(self.entities)} entities")

    def _get_preferred_rooms(self, role: str) -> List[str]:
        """Get preferred rooms for an NPC role."""
        preferences = {
            "dev": ["dev_room", "reception", "ops_room"],
            "devops": ["ops_room", "dev_room", "reception"],
            "watchdog": ["ops_room", "dev_room", "reception"],
            "receptionist": ["reception"],
        }
        return preferences.get(role, ["dev_room"])
    
    async def start(self):
        self.running = True
        self.supervisor_session = aiohttp.ClientSession()
        self.memory_session = aiohttp.ClientSession()
        
        # Start background tasks
        self._tick_task = asyncio.create_task(self._tick_loop())
        self._delta_broadcast_task = asyncio.create_task(self._delta_broadcast_loop())
        
        logger.info("Game Server started")
    
    async def stop(self):
        self.running = False
        
        if self._tick_task:
            self._tick_task.cancel()
        if self._delta_broadcast_task:
            self._delta_broadcast_task.cancel()
        
        for client in list(self.clients.values()):
            await client.ws.close()
        
        if self.supervisor_session:
            await self.supervisor_session.close()
        if self.memory_session:
            await self.memory_session.close()
        
        logger.info("Game Server stopped")
    
    async def _tick_loop(self):
        """Main game loop - physics, NPC behavior, etc."""
        while self.running:
            try:
                start = time.time()
                
                # Update NPCs
                await self._update_npcs()
                
                # Maintain tick rate
                elapsed = time.time() - start
                sleep_time = max(0, (1.0 / TICK_RATE) - elapsed)
                await asyncio.sleep(sleep_time)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Tick loop error: {e}")
                await asyncio.sleep(1)
    
    async def _delta_broadcast_loop(self):
        """Broadcast world state deltas at fixed rate."""
        while self.running:
            try:
                await self._broadcast_delta()
                await asyncio.sleep(1.0 / DELTA_BROADCAST_HZ)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Delta broadcast error: {e}")
                await asyncio.sleep(1)
    
    async def _broadcast_delta(self):
        """Send world state delta to all clients in room."""
        delta = {
            "spawned": [],
            "moved": [],
            "despawned": [],
            "chat": [],
            "meetings": []
        }
        
        for client in self.clients.values():
            if client.ws.closed:
                continue
            try:
                await client.ws.send_json({
                    "msg_id": str(uuid.uuid4()),
                    "type": "world.state.delta",
                    "payload": delta,
                    "ts": int(time.time() * 1000),
                    "seq": client.seq
                })
                client.seq += 1
            except Exception:
                pass
    
    async def _update_npcs(self):
        """Update NPC behavior using behavior trees."""
        # First, sync agent status from supervisor
        await self._sync_agent_status()
        
        # Then tick each NPC's behavior tree
        for entity_id, entity in self.entities.items():
            if entity.type != "npc":
                continue
            
            behavior_tree = self.npc_behavior_trees.get(entity_id)
            if behavior_tree:
                try:
                    await behavior_tree.tick()
                except Exception as e:
                    logger.error(f"Behavior tree error for {entity_id}: {e}")

    async def _sync_agent_status(self):
        """Sync real agent status from Hermes Supervisor to NPC blackboards."""
        try:
            # Call supervisor to get agent statuses
            result = await self._supervisor_call("agents.list", {})
            agents = result.get("agents", [])
        
            # Map supervisor agents to NPCs by role
            agent_by_role = {}
            for agent in agents:
                role = agent.get("role", "").lower()
                if role:
                    agent_by_role[role] = agent
        
            # Update each NPC's blackboard with agent status
            for entity_id, entity in self.entities.items():
                if entity.type != "npc":
                    continue
        
                role = entity.meta.get("role", "").lower()
                behavior_tree = self.npc_behavior_trees.get(entity_id)
        
                if behavior_tree and role in agent_by_role:
                    agent = agent_by_role[role]
                    bb = behavior_tree.blackboard
        
                    # Update blackboard with real agent status
                    bb.set("agent_status", agent.get("status", "idle"))
                    bb.set("agent_current_task", agent.get("current_task"))
                    bb.set("agent_workload", agent.get("workload", 0))
                    bb.set("agent_has_work", agent.get("status") == "working")
                    bb.set("agent_in_meeting", agent.get("status") == "meeting")
                    bb.set("agent_has_incident", agent.get("status") == "incident")
                    bb.set("agent_has_deploy", agent.get("status") == "deploying")
                    bb.set("agent_has_research", agent.get("status") == "researching")
                    bb.set("agent_has_alert", agent.get("status") == "alert")
                    bb.set("agent_alert_active", agent.get("status") == "alert")
                    bb.set("agent_has_decisions", agent.get("status") == "deciding")
                    bb.set("agent_has_delegations", agent.get("status") == "delegating")
        
                    # Update NPC meta status based on agent status
                    agent_status = agent.get("status", "idle")
                    if agent_status == "working":
                        entity.meta["status"] = "working"
                    elif agent_status == "meeting":
                        entity.meta["status"] = "meeting"
                    elif agent_status == "incident" or agent_status == "alert":
                        entity.meta["status"] = "crisis_response"
                    elif agent_status == "idle":
                        entity.meta["status"] = "idle"
                  
        except Exception as e:
            logger.debug(f"Could not sync agent status (supervisor may not be running): {e}")

    # ============================================================
    # Cross-room Pathfinding & Door Transitions
    # ============================================================

    def get_door_transitions(self, room_id: str) -> List[Dict]:
        """Get all door transitions from a room."""
        if room_id not in DOOR_COORDS:
            return []
        transitions = []
        for target_room_key, doors in DOOR_COORDS[room_id].items():
            # Extract target room ID from key (e.g., "to_ops_room" -> "ops_room")
            target_room = target_room_key.replace("to_", "")
            # Get corresponding doors in target room (reverse direction)
            target_doors = DOOR_COORDS.get(target_room, {}).get(f"to_{room_id}", [])
            for i, door in enumerate(doors):
                # Match with corresponding door in target room (by index, or first available)
                target_door = target_doors[i] if i < len(target_doors) else (target_doors[0] if target_doors else door)
                transitions.append({
                    "from_room": room_id,
                    "from_x": door["x"],
                    "from_y": door["y"],
                    "to_room": target_room,
                    "to_x": target_door["x"],
                    "to_y": target_door["y"],
                })
        return transitions

    def find_cross_room_path(self, start_room_id: str, start_x: int, start_y: int, 
                              goal_room_id: str, goal_x: int, goal_y: int) -> List[Dict]:
        """Find path across multiple rooms using door transitions.
        Returns list of {room_id, x, y} steps, or empty list if no path."""
        if start_room_id == goal_room_id:
            room = self.rooms.get(start_room_id)
            if room:
                path = room.find_path(start_x, start_y, goal_x, goal_y)
                return [{"room_id": start_room_id, "x": p.x, "y": p.y} for p in path]
            return []
        
        # For cross-room pathfinding, we need to find a path through doors
        # This is a simplified version - in practice you'd want a graph of rooms
        # For now, find path to nearest door, then to target
        start_room = self.rooms.get(start_room_id)
        goal_room = self.rooms.get(goal_room_id)
        
        if not start_room or not goal_room:
            return []
        
        # Get doors from start room
        start_doors = self.get_door_transitions(start_room_id)
        goal_doors = self.get_door_transitions(goal_room_id)
        
        # Try direct door connection
        for s_door in start_doors:
            for g_door in goal_doors:
                if s_door["to_room"] == goal_room_id and g_door["to_room"] == start_room_id:
                    # Found connecting doors
                    # Path: start -> start_door -> goal_door -> goal
                    path_to_door = start_room.find_path(start_x, start_y, s_door["from_x"], s_door["from_y"])
                    if not path_to_door:
                        continue
                    path_from_door = goal_room.find_path(g_door["from_x"], g_door["from_y"], goal_x, goal_y)
                    if not path_from_door:
                        continue
                    
                    result = []
                    for p in path_to_door:
                        result.append({"room_id": start_room_id, "x": p.x, "y": p.y})
                    for p in path_from_door[1:]:  # Skip duplicate door tile
                        result.append({"room_id": goal_room_id, "x": p.x, "y": p.y})
                    return result
        
        return []

    def find_path_to_room(self, entity_id: str, target_room_id: str, target_x: int = None, target_y: int = None) -> List[Dict]:
        """Find path for entity to reach a target room (and optionally specific coordinates)."""
        entity = self.entities.get(entity_id)
        if not entity:
            return []
        
        start_room_id = entity.room_id
        start_x, start_y = entity.position.x, entity.position.y
        
        # If target coordinates not specified, use room center
        if target_x is None or target_y is None:
            target_room = self.rooms.get(target_room_id)
            if target_room:
                target_x = target_room.width // 2
                target_y = target_room.height // 2
            else:
                return []
        
        return self.find_cross_room_path(start_room_id, start_x, start_y, target_room_id, target_x, target_y)

    # ============================================================
    # WebSocket Handlers
    # ============================================================

    async def handle_websocket(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        client_id = str(uuid.uuid4())
        client = ClientConnection(ws=ws)
        self.clients[client_id] = client
        
        logger.info(f"Client connected: {client_id}")
        
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    await self._handle_message(client_id, msg.data)
                elif msg.type == WSMsgType.ERROR:
                    logger.error(f"WS error: {ws.exception()}")
        finally:
            await self._disconnect_client(client_id)
        
        return ws

    async def _handle_message(self, client_id: str, data: str):
        try:
            message = json.loads(data)
        except json.JSONDecodeError:
            await self._send_error(client_id, "INVALID_JSON", "Invalid JSON")
            return
        
        msg_type = message.get("type")
        payload = message.get("payload", {})
        ref_msg_id = message.get("msg_id")
        
        client = self.clients.get(client_id)
        if not client:
            return
        
        try:
            if msg_type == MessageType.HELLO.value:
                await self._handle_hello(client_id, payload, ref_msg_id)
            elif msg_type == MessageType.ENTITY_MOVE.value:
                await self._handle_entity_move(client_id, payload, ref_msg_id)
            elif msg_type == MessageType.CHAT_MESSAGE_RECV.value:
                await self._handle_chat_message(client_id, payload, ref_msg_id)
            elif msg_type == MessageType.MEETING_INVITE_REQ.value:
                await self._handle_meeting_invite(client_id, payload, ref_msg_id)
            elif msg_type == MessageType.MEETING_JOIN.value:
                await self._handle_meeting_join(client_id, payload, ref_msg_id)
            elif msg_type == MessageType.MEETING_LEAVE.value:
                await self._handle_meeting_leave(client_id, payload, ref_msg_id)
            elif msg_type == MessageType.NPC_DIALOGUE_REQUEST.value:
                await self._handle_npc_dialogue(client_id, payload, ref_msg_id)
            elif msg_type == MessageType.NPC_DIALOGUE_ACTION.value:
                await self._handle_npc_dialogue_action(client_id, payload, ref_msg_id)
            elif msg_type == MessageType.WORLD_SYNC_REQUEST.value:
                await self._handle_world_sync(client_id, payload, ref_msg_id)
            elif msg_type == MessageType.PATHFIND_REQUEST.value:
                await self._handle_pathfind_request(client_id, payload, ref_msg_id)
            elif msg_type == MessageType.PING.value:
                await self._send_pong(client_id, ref_msg_id)
            else:
                await self._send_error(client_id, "UNKNOWN_MESSAGE_TYPE", f"Unknown type: {msg_type}")
              
        except Exception as e:
            logger.error(f"Message handling error: {e}")
            await self._send_error(client_id, "INTERNAL_ERROR", str(e))

    async def _handle_hello(self, client_id: str, payload: Dict, ref_msg_id: str):
            client = self.clients[client_id]
            token = payload.get("token")

            # TODO: Validate JWT token with supervisor
            # For now, auto-assign as player
            entity_id = f"player_{client_id[:8]}"

            # Guard: If client already has an entity, don't re-spawn - just send welcome with current world state
            if client.entity_id and client.entity_id in self.entities:
                logger.info(f"Client {client_id} already has entity {client.entity_id}, sending welcome without re-spawn")
                entity = self.entities[client.entity_id]
            
                # Build welcome payload with existing entity
                welcome_payload = {
                    "entity_id": client.entity_id,
                    "world": {
                        "rooms": [{"id": r.id, "name": r.name, "width": r.width, "height": r.height,
                                  "is_meeting": r.is_meeting, "capacity": r.capacity,
                                  "collision_grid": r.collision_grid,
                                  "doors": r.doors}
                                  for r in self.rooms.values()],
                        "entities": [e.to_dict() for e in self.entities.values()],
                        "npcs": [e.to_dict() for e in self.entities.values() if e.type == "npc"]
                    },
                    "config": {
                        "tick_rate": TICK_RATE,
                        "tile_size": TILE_SIZE
                    }
                }
            
                await self._send_message(client_id, MessageType.WELCOME.value, welcome_payload, ref_msg_id)
                return

            # First time spawn
            client.entity_id = entity_id
            client.room_id = "reception"  # Player spawns in Reception

            # Create player entity
            room = self.rooms["reception"]
            # Spawn at reception area (not on receptionist at 30,5 or furniture)
            # Search for free tile in reception area away from receptionist
            spawn_x, spawn_y = 25, 8  # Default: left seating area

            # Find free spawn position - search wider area in reception
            found_spawn = False
            for y in range(5, 13):
                for x in range(20, 40):
                    if not room.collision_grid[y][x]:
                        spawn_x, spawn_y = x, y
                        found_spawn = True
                        break
                if found_spawn:
                    break

            entity = Entity(
                id=entity_id,
                type="player",
                room_id="reception",
                position=Position(spawn_x, spawn_y),
                sprite="avatar_player",
                meta={"name": f"Player {entity_id[:4]}", "connected_at": datetime.now().isoformat(), "direction": "down"}
            )

            self.entities[entity_id] = entity
            room.add_entity(entity)
            client.room_id = "reception"

            # Build welcome payload
            welcome_payload = {
                "entity_id": entity_id,
                "world": {
                    "rooms": [{"id": r.id, "name": r.name, "width": r.width, "height": r.height, 
                              "is_meeting": r.is_meeting, "capacity": r.capacity,
                              "collision_grid": r.collision_grid,
                              "doors": r.doors} 
                              for r in self.rooms.values()],
                    "entities": [e.to_dict() for e in self.entities.values()],
                    "npcs": [e.to_dict() for e in self.entities.values() if e.type == "npc"]
                },
                "config": {
                    "tick_rate": TICK_RATE,
                    "tile_size": TILE_SIZE
                }
            }

            await self._send_message(client_id, MessageType.WELCOME.value, welcome_payload, ref_msg_id)
            await self._broadcast_entity_spawn(entity)

            logger.info(f"Player spawned: {entity_id} at ({spawn_x}, {spawn_y}) in Reception")

    async def _handle_entity_move(self, client_id: str, payload: Dict, ref_msg_id: str):
            client = self.clients[client_id]
            if not client.entity_id:
                await self._send_error(client_id, "NOT_SPAWNED", "Not spawned yet")
                return

            # Use client's entity_id directly (not from payload for security)
            entity_id = client.entity_id

            target = payload.get("target")
            path = payload.get("path", [])

            if not target:
                await self._send_error(client_id, "INVALID_MOVE", "Missing target")
                return

            room = self.rooms.get(client.room_id)
            if not room:
                await self._send_error(client_id, "INVALID_ROOM", "Not in a room")
                return

            target_x = target.get("x")
            target_y = target.get("y")

            if not room.move_entity(entity_id, target_x, target_y):
                await self._send_error(client_id, "INVALID_MOVE", "Invalid move target")
                return

            entity = self.entities[entity_id]

            # Broadcast move
            move_payload = {
                "entity_id": entity_id,
                "position": entity.position.to_dict(),
                "path": path,
                "arrival_ts": int(time.time() * 1000)
            }

            await self._broadcast_to_room(client.room_id, MessageType.ENTITY_MOVE.value, move_payload, exclude=client_id)
            await self._send_message(client_id, MessageType.ENTITY_MOVE.value, move_payload, ref_msg_id)

    async def _handle_chat_message(self, client_id: str, payload: Dict, ref_msg_id: str):
        client = self.clients[client_id]
        if not client.room_id:
            return
        
        content = payload.get("content", "")
        if not content or len(content) > 500:
            return
        
        msg_id = str(uuid.uuid4())
        chat_payload = {
            "msg_id": msg_id,
            "room_id": client.room_id,
            "sender_id": client.entity_id,
            "sender_name": self.entities.get(client.entity_id, {}).meta.get("name", "Unknown"),
            "content": content,
            "ts": int(time.time() * 1000)
        }
        
        await self._broadcast_to_room(client.room_id, MessageType.CHAT_MESSAGE_RECV.value, chat_payload)

    async def _handle_meeting_invite(self, client_id: str, payload: Dict, ref_msg_id: str):
        # Forward to supervisor
        try:
            await self._supervisor_call("task.create", {
                "title": f"Meeting: {payload.get('topic', 'Meeting')}",
                "description": f"Meeting organized by {client_id}",
                "assignee": "devops",
                "priority": 5,
                "dependencies": [],
                "metadata": {
                    "type": "meeting",
                    "room_id": payload.get("room_id"),
                    "participants": payload.get("participants", []),
                    "organizer": client_id
                }
            })
        except Exception as e:
            logger.error(f"Meeting invite failed: {e}")

    async def _handle_meeting_join(self, client_id: str, payload: Dict, ref_msg_id: str):
        pass  # TODO

    async def _handle_meeting_leave(self, client_id: str, payload: Dict, ref_msg_id: str):
        pass  # TODO

    async def _handle_npc_dialogue(self, client_id: str, payload: Dict, ref_msg_id: str):
        """Handle player -> NPC dialogue via Memory Substrate."""
        npc_id = payload.get("npc_id")
        user_text = payload.get("user_text")
        context = payload.get("context", {})
        
        if not npc_id or not user_text:
            await self._send_error(client_id, "INVALID_REQUEST", "Missing npc_id or user_text")
            return
        
        # Call Memory Substrate dialogue endpoint
        try:
            async with self.memory_session.post(
                f"{MEMORY_SUBSTRATE_URL}/dialogue",
                json={
                    "npc_id": npc_id,
                    "user_text": user_text,
                    "context": context
                }
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    # Execute actions from dialogue response
                    await self._execute_dialogue_actions(npc_id, result.get("actions", []))
                  
                    # Broadcast NPC response
                    dialogue_payload = {
                        "npc_id": npc_id,
                        "text": result.get("text", ""),
                        "emotion": result.get("emotion", "neutral"),
                        "actions": result.get("actions", [])
                    }
                    await self._broadcast_to_room(
                        self.clients[client_id].room_id,
                        MessageType.NPC_DIALOGUE_RESPONSE.value,
                        dialogue_payload
                    )
        except Exception as e:
            logger.error(f"NPC dialogue error: {e}")
            await self._send_error(client_id, "DIALOGUE_FAILED", str(e))

    async def _execute_dialogue_actions(self, npc_id: str, actions: List[Dict]):
        """Execute actions returned by Dialogue Engine."""
        for action in actions:
            action_type = action.get("type")
            
            if action_type == "move":
                target = action.get("target")
                room = self.rooms.get(self.entities.get(npc_id, {}).room_id)
                if room and target:
                    room.move_entity(npc_id, target["x"], target["y"])
            
            elif action_type == "spawn_artifact":
                # Store artifact
                pass
            
            elif action_type == "schedule_meeting":
                pass
            
            elif action_type == "change_behavior":
                if npc_id in self.entities:
                    self.entities[npc_id].meta["status"] = action.get("behavior", "idle")

    async def _handle_npc_dialogue_action(self, client_id: str, payload: Dict, ref_msg_id: str):
        """Handle NPC dialogue action from frontend (button clicks)."""
        npc_id = payload.get("npc_id")
        action = payload.get("action")
        params = payload.get("params", {})
        
        if not npc_id or not action:
            await self._send_error(client_id, "INVALID_ACTION", "Missing npc_id or action")
            return
        
        # Execute action locally
        if npc_id in self.entities:
            if action == "change_behavior":
                self.entities[npc_id].meta["status"] = params.get("behavior", "idle")
                # Broadcast status change
                await self._broadcast_to_room(
                    self.clients[client_id].room_id,
                    MessageType.NPC_ACTION.value,
                    {"npc_id": npc_id, "action": action, "params": params}
                )
            elif action == "move" and "target" in params:
                room = self.rooms.get(self.entities[npc_id].room_id)
                if room:
                    room.move_entity(npc_id, params["target"]["x"], params["target"]["y"])

    async def _handle_world_sync(self, client_id: str, payload: Dict, ref_msg_id: str):
        """Full world state sync for reconnection."""
        client = self.clients[client_id]
        
        sync_payload = {
            "spawned": [e.to_dict() for e in self.entities.values()],
            "moved": [],
            "despawned": [],
            "chat": [],
            "meetings": []
        }
        
        await self._send_message(client_id, MessageType.WORLD_STATE_DELTA.value, sync_payload, ref_msg_id)

    async def _handle_pathfind_request(self, client_id: str, payload: Dict, ref_msg_id: str):
            """Handle pathfinding request from client."""
            client = self.clients[client_id]
            entity_id = client.entity_id

            if not entity_id:
                await self._send_error(client_id, "NOT_SPAWNED", "Not spawned yet")
                return

            target_room_id = payload.get("target_room_id")
            target_x = payload.get("target_x")
            target_y = payload.get("target_y")

            if not target_room_id:
                await self._send_error(client_id, "INVALID_REQUEST", "Missing target_room_id")
                return

            entity = self.entities.get(entity_id)
            if entity:
                logger.info(f"Pathfind request: entity={entity_id} at ({entity.position.x}, {entity.position.y}) room={entity.room_id} -> target=({target_x}, {target_y}) room={target_room_id}")

            # Debug: test room.find_path directly
            if entity:
                room = self.rooms.get(entity.room_id)
                if room:
                    direct_room_path = room.find_path(entity.position.x, entity.position.y, target_x, target_y)
                    logger.info(f"Direct room.find_path: {len(direct_room_path)} steps")
                    if direct_room_path:
                        logger.info(f"  First: ({direct_room_path[0].x}, {direct_room_path[0].y})")

            # Debug: test find_cross_room_path directly
            if entity:
                direct_path = self.find_cross_room_path(entity.room_id, entity.position.x, entity.position.y, target_room_id, target_x, target_y)
                logger.info(f"Direct find_cross_room_path: {len(direct_path)} steps")
                if direct_path:
                    logger.info(f"  First step: {direct_path[0]}")

            path = self.find_path_to_room(entity_id, target_room_id, target_x, target_y)

            if entity:
                logger.info(f"Pathfind result: {len(path)} steps")
                if path:
                    logger.info(f"Path first: {path[0]}, last: {path[-1]}")

            response_payload = {
                "path": path,
                "entity_id": entity_id,
                "target_room_id": target_room_id,
            }

            await self._send_message(client_id, MessageType.PATHFIND_RESPONSE.value, response_payload, ref_msg_id)

    async def _send_pong(self, client_id: str, ref_msg_id: str):
        await self._send_message(client_id, MessageType.PONG.value, {"ts": int(time.time() * 1000)}, ref_msg_id)

    async def _send_message(self, client_id: str, msg_type: str, payload: Dict, ref_msg_id: str = None):
        client = self.clients.get(client_id)
        if not client or client.ws.closed:
            return
        
        msg = {
            "msg_id": ref_msg_id or str(uuid.uuid4()),
            "type": msg_type,
            "payload": payload,
            "ts": int(time.time() * 1000),
            "seq": client.seq
        }
        client.seq += 1
        
        try:
            await client.ws.send_json(msg)
        except Exception as e:
            logger.error(f"Send error to {client_id}: {e}")

    async def _send_error(self, client_id: str, code: str, message: str):
        await self._send_message(client_id, MessageType.ERROR.value, {"code": code, "message": message})

    async def _broadcast_to_room(self, room_id: str, msg_type: str, payload: Dict, exclude: str = None):
        for client_id, client in self.clients.items():
            if client.ws.closed:
                continue
            if client.room_id != room_id:
                continue
            if client_id == exclude:
                continue
            await self._send_message(client_id, msg_type, payload)

    async def _broadcast_entity_spawn(self, entity: Entity):
        payload = {
            "entity": entity.to_dict()
        }
        if entity.room_id:
            await self._broadcast_to_room(entity.room_id, MessageType.ENTITY_SPAWN.value, payload)

    async def _broadcast_entity_despawn(self, entity_id: str, room_id: str, reason: str):
        payload = {"entity_id": entity_id, "reason": reason}
        await self._broadcast_to_room(room_id, MessageType.ENTITY_DESPAWN.value, payload)

    async def _disconnect_client(self, client_id: str):
        client = self.clients.pop(client_id, None)
        if not client:
            return
        
        if client.entity_id and client.entity_id in self.entities:
            entity = self.entities.pop(client.entity_id)
            if client.room_id and client.room_id in self.rooms:
                self.rooms[client.room_id].remove_entity(entity.id)
                await self._broadcast_entity_despawn(entity.id, client.room_id, "disconnect")
        
        logger.info(f"Client disconnected: {client_id}")

    async def _supervisor_call(self, method: str, params: Dict) -> Dict:
        """Call Supervisor JSON-RPC."""
        if not self.supervisor_session:
            raise Exception("Supervisor session not available")
        
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": str(uuid.uuid4())
        }
        
        async with self.supervisor_session.post(SUPERVISOR_URL, json=payload) as resp:
            result = await resp.json()
            if "error" in result:
                raise Exception(f"Supervisor error: {result['error']}")
            return result.get("result", {})

    async def supervisor_ws_proxy(self, ws: web.WebSocketResponse):
        """WebSocket proxy that forwards JSON-RPC messages to supervisor HTTP endpoint."""
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        request = json.loads(msg.data)
                        # Forward to supervisor HTTP RPC
                        payload = {
                            "jsonrpc": "2.0",
                            "method": request.get("method"),
                            "params": request.get("params", {}),
                            "id": request.get("id")
                        }
                        async with self.supervisor_session.post(SUPERVISOR_URL, json=payload) as resp:
                            result = await resp.json()
                        await ws.send_json(result)
                    except json.JSONDecodeError:
                        await ws.send_json({
                            "jsonrpc": "2.0",
                            "id": None,
                            "error": {"code": -32700, "message": "Parse error"}
                        })
                    except Exception as e:
                        await ws.send_json({
                            "jsonrpc": "2.0",
                            "id": request.get("id") if 'request' in locals() else None,
                            "error": {"code": -32603, "message": str(e)}
                        })
        except Exception as e:
            logger.error(f"Supervisor WS proxy error: {e}")
        finally:
            if not ws.closed:
                await ws.close()


# ============================================================
# HTTP Routes
# ============================================================

async def health_check(request):
    return web.json_response({
        "status": "healthy",
        "uptime_seconds": time.time() - game_server._last_tick if 'game_server' in globals() else 0,
        "connections": len(game_server.clients) if 'game_server' in globals() else 0,
        "entities": len(game_server.entities) if 'game_server' in globals() else 0
    })


async def metrics(request):
    if 'game_server' not in globals():
        return web.Response(text="", status=503)
    
    metrics_text = f"""# HELP game_server_uptime_seconds Server uptime
# TYPE game_server_uptime_seconds gauge
game_server_uptime_seconds {time.time() - game_server._last_tick}

# HELP game_server_connections_active Active WebSocket connections
# TYPE game_server_connections_active gauge
game_server_connections_active {len(game_server.clients)}

# HELP game_server_entities_total Total entities in world
# TYPE game_server_entities_total gauge
game_server_entities_total{{type="player"}} {sum(1 for e in game_server.entities.values() if e.type == "player")}
game_server_entities_total{{type="npc"}} {sum(1 for e in game_server.entities.values() if e.type == "npc")}
game_server_entities_total{{type="furniture"}} {sum(1 for e in game_server.entities.values() if e.type == "furniture")}
"""
    return web.Response(text=metrics_text, content_type="text/plain")


# ============================================================
# Main
# ============================================================

game_server: Optional[GameServer] = None


async def create_app():
    global game_server
    game_server = GameServer()
    await game_server.start()
    
    # CORS middleware - handles OPTIONS at middleware level
    @web.middleware
    async def cors_middleware(request, handler):
        # Handle preflight OPTIONS requests before routing
        origin = request.headers.get('Origin', '')
        allowed_origins = ['http://127.0.0.1:8080', 'http://localhost:8080']
        cors_origin = origin if origin in allowed_origins else allowed_origins[0]
        
        if request.method == 'OPTIONS':
            return web.Response(headers={
                'Access-Control-Allow-Origin': cors_origin,
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Max-Age': '86400'
            })
        
        response = await handler(request)
        response.headers['Access-Control-Allow-Origin'] = cors_origin
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
    
    # Add explicit OPTIONS routes so aiohttp matches them
    async def options_handler(request):
        return web.Response(headers={
            'Access-Control-Allow-Origin': 'http://127.0.0.1:8080',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '86400'
        })
    
    app = web.Application(middlewares=[cors_middleware])
    app.router.add_get("/ws", game_server.handle_websocket)
    app.router.add_get("/health", health_check)
    app.router.add_get("/metrics", metrics)
    app.router.add_get("/ws/supervisor", game_server.supervisor_ws_proxy)
    app.router.add_options("/ws", options_handler)
    app.router.add_options("/health", options_handler)
    app.router.add_options("/metrics", options_handler)
    app.router.add_options("/ws/supervisor", options_handler)
    
    # Cleanup on shutdown
    async def cleanup(app):
        await game_server.stop()
    
    app.on_cleanup.append(cleanup)
    return app


if __name__ == "__main__":
    web.run_app(create_app(), host="127.0.0.1", port=8081)