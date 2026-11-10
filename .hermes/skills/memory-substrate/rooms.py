# -*- coding: utf-8 -*-
"""
rooms.py — Room (tileMap + blockedTiles, §2) e RoomManager (§6.1).

EXTINTO: collision_grid (§2.5) — a classe Room NÃO possui esse atributo.
- tile_map[row][col]: ints (WALL=0, FLOOR=1, VOID=255), imutável pós-build
- blocked_tiles: set de "col,row" — móveis (footprint menos backgroundTiles,
  via manifest) + NPCs parados. JOGADOR NUNCA ENTRA (§2.4).
- Tick 10Hz de movimento server-side (§3.3) avança entidades por MOVE_TIME.
"""
import random
import time
from typing import Dict, List, Optional, Set

from entities import Entity, Position, WALL, FLOOR, VOID, MOVE_TIME_MS, TICK_HZ
import pathfinding

# ============================================================
# Configuração de salas (migrada intacta de game_server.py)
# ============================================================

# Portas por sala (cada tile de porta é FLOOR no tileMap — §2.3)
DOOR_COORDS = {
    "entrance": {
        "to_corridor_left": [{"x": 12, "y": 9}, {"x": 13, "y": 9}],
        "to_corridor_right": [{"x": 66, "y": 9}, {"x": 67, "y": 9}],
    },
    "corridor_left": {
        "to_entrance": [{"x": 3, "y": 0}],
        "to_setor_dev": [{"x": 5, "y": 10}],
        "to_setor_ops": [{"x": 5, "y": 22}],
        "to_setor_watchdog": [{"x": 5, "y": 34}],
    },
    "setor_dev": {
        "to_corridor_left": [{"x": 0, "y": 5}],
    },
    "setor_ops": {
        "to_corridor_left": [{"x": 0, "y": 5}],
    },
    "setor_watchdog": {
        "to_corridor_left": [{"x": 0, "y": 5}],
    },
    "corridor_right": {
        "to_entrance": [{"x": 2, "y": 0}],
        "to_setor_creative": [{"x": 0, "y": 10}],
        "to_setor_biz": [{"x": 0, "y": 22}],
        "to_setor_research": [{"x": 0, "y": 34}],
        "to_top_corridor": [{"x": 5, "y": 2}],
    },
    "setor_creative": {
        "to_corridor_right": [{"x": 29, "y": 5}],
    },
    "setor_biz": {
        "to_corridor_right": [{"x": 29, "y": 5}],
    },
    "setor_research": {
        "to_corridor_right": [{"x": 29, "y": 5}],
    },
    "top_corridor": {
        "to_corridor_right": [{"x": 0, "y": 2}],
        "to_meeting_room": [{"x": 19, "y": 2}],
        "to_ceo_office": [{"x": 32, "y": 2}],
    },
    "meeting_room": {
        "to_top_corridor": [{"x": 9, "y": 7}],
    },
    "ceo_office": {
        "to_top_corridor": [{"x": 0, "y": 6}],
    },
}

# Paredes por sala: retângulos gravados como WALL no tileMap NO BUILD (§2.1)
INTERNAL_WALLS = {
    "entrance": [
        {"x": 0, "y": 0, "w": 80, "h": 1},
        {"x": 0, "y": 0, "w": 1, "h": 10},
        {"x": 79, "y": 0, "w": 1, "h": 10},
        {"x": 0, "y": 9, "w": 12, "h": 1},
        {"x": 14, "y": 9, "w": 25, "h": 1},
        {"x": 41, "y": 9, "w": 25, "h": 1},
        {"x": 68, "y": 9, "w": 12, "h": 1},
    ],
    "corridor_left": [
        {"x": 0, "y": 0, "w": 6, "h": 1},
        {"x": 0, "y": 0, "w": 1, "h": 40},
        {"x": 5, "y": 0, "w": 1, "h": 9},
        {"x": 5, "y": 10, "w": 1, "h": 1},
        {"x": 5, "y": 11, "w": 1, "h": 10},
        {"x": 5, "y": 22, "w": 1, "h": 1},
        {"x": 5, "y": 23, "w": 1, "h": 10},
        {"x": 5, "y": 34, "w": 1, "h": 1},
        {"x": 5, "y": 35, "w": 1, "h": 5},
        {"x": 0, "y": 39, "w": 6, "h": 1},
        {"x": 1, "y": 10, "w": 4, "h": 1},
        {"x": 1, "y": 20, "w": 4, "h": 1},
        {"x": 1, "y": 30, "w": 4, "h": 1},
    ],
    "setor_dev": [
        {"x": 0, "y": 0, "w": 30, "h": 1},
        {"x": 0, "y": 0, "w": 1, "h": 5},
        {"x": 0, "y": 6, "w": 1, "h": 4},
        {"x": 29, "y": 0, "w": 1, "h": 10},
        {"x": 0, "y": 9, "w": 30, "h": 1},
    ],
    "setor_ops": [
        {"x": 0, "y": 0, "w": 30, "h": 1},
        {"x": 0, "y": 0, "w": 1, "h": 5},
        {"x": 0, "y": 6, "w": 1, "h": 4},
        {"x": 29, "y": 0, "w": 1, "h": 10},
        {"x": 0, "y": 9, "w": 30, "h": 1},
    ],
    "setor_watchdog": [
        {"x": 0, "y": 0, "w": 30, "h": 1},
        {"x": 0, "y": 0, "w": 1, "h": 5},
        {"x": 0, "y": 6, "w": 1, "h": 4},
        {"x": 29, "y": 0, "w": 1, "h": 10},
        {"x": 0, "y": 9, "w": 30, "h": 1},
    ],
    "corridor_right": [
        {"x": 0, "y": 0, "w": 6, "h": 1},
        {"x": 0, "y": 0, "w": 1, "h": 10},
        {"x": 0, "y": 11, "w": 1, "h": 11},
        {"x": 0, "y": 23, "w": 1, "h": 11},
        {"x": 0, "y": 35, "w": 1, "h": 5},
        {"x": 5, "y": 0, "w": 1, "h": 2},
        {"x": 5, "y": 3, "w": 1, "h": 37},
        {"x": 0, "y": 39, "w": 6, "h": 1},
        {"x": 1, "y": 10, "w": 4, "h": 1},
        {"x": 1, "y": 20, "w": 4, "h": 1},
        {"x": 1, "y": 30, "w": 4, "h": 1},
    ],
    "setor_creative": [
        {"x": 0, "y": 0, "w": 30, "h": 1},
        {"x": 0, "y": 0, "w": 1, "h": 10},
        {"x": 29, "y": 0, "w": 1, "h": 5},
        {"x": 29, "y": 6, "w": 1, "h": 4},
        {"x": 0, "y": 9, "w": 30, "h": 1},
    ],
    "setor_biz": [
        {"x": 0, "y": 0, "w": 30, "h": 1},
        {"x": 0, "y": 0, "w": 1, "h": 10},
        {"x": 29, "y": 0, "w": 1, "h": 5},
        {"x": 29, "y": 6, "w": 1, "h": 4},
        {"x": 0, "y": 9, "w": 30, "h": 1},
    ],
    "setor_research": [
        {"x": 0, "y": 0, "w": 30, "h": 1},
        {"x": 0, "y": 0, "w": 1, "h": 10},
        {"x": 29, "y": 0, "w": 1, "h": 5},
        {"x": 29, "y": 6, "w": 1, "h": 4},
        {"x": 0, "y": 9, "w": 30, "h": 1},
    ],
    "meeting_room": [
        {"x": 0, "y": 0, "w": 20, "h": 1},
        {"x": 0, "y": 0, "w": 1, "h": 8},
        {"x": 19, "y": 0, "w": 1, "h": 8},
        {"x": 0, "y": 7, "w": 9, "h": 1},
        {"x": 10, "y": 7, "w": 10, "h": 1},
    ],
    "ceo_office": [
        {"x": 0, "y": 0, "w": 18, "h": 1},
        {"x": 0, "y": 0, "w": 1, "h": 6},
        {"x": 0, "y": 7, "w": 1, "h": 5},
        {"x": 17, "y": 0, "w": 1, "h": 12},
        {"x": 0, "y": 11, "w": 18, "h": 1},
    ],
    "top_corridor": [
        {"x": 0, "y": 0, "w": 50, "h": 1},
        {"x": 0, "y": 0, "w": 1, "h": 2},
        {"x": 0, "y": 3, "w": 1, "h": 1},
        {"x": 49, "y": 0, "w": 1, "h": 4},
        {"x": 0, "y": 3, "w": 50, "h": 1},
    ],
}

ROOM_CONFIGS = {
    "entrance": {
        "id": "entrance",
        "name": "Entrada",
        "width": 80, "height": 10,
        "is_meeting": False, "capacity": 20,
        "description": "Hall de entrada principal com balcão de recepção e sofás de espera.",
        "furniture": [
            {"type": "reception_desk", "x": 37, "y": 2, "w": 4, "h": 2, "sprite": "furniture_reception"},
            {"type": "sofa", "x": 4, "y": 6, "w": 4, "h": 2, "sprite": "furniture_sofa"},
            {"type": "coffee_table", "x": 6, "y": 8, "w": 2, "h": 1, "sprite": "furniture_coffee_table"},
            {"type": "sofa", "x": 72, "y": 6, "w": 4, "h": 2, "sprite": "furniture_sofa"},
            {"type": "coffee_table", "x": 72, "y": 8, "w": 2, "h": 1, "sprite": "furniture_coffee_table"},
            {"type": "plant", "x": 1, "y": 1, "w": 1, "h": 1, "sprite": "furniture_plant"},
            {"type": "plant", "x": 78, "y": 1, "w": 1, "h": 1, "sprite": "furniture_plant"},
        ],
        "doors": [
            {"x": 12, "y": 9, "target_room": "corridor_left", "target_x": 5, "target_y": 0, "width": 2, "label": "To Corridor Left"},
            {"x": 39, "y": 9, "target_room": "corridor_left", "target_x": 3, "target_y": 0, "width": 2, "label": "To Center"},
            {"x": 66, "y": 9, "target_room": "corridor_right", "target_x": 2, "target_y": 0, "width": 2, "label": "To Corridor Right"},
        ],
        "npc_spawns": [
            {"role": "receptionist", "x": 39, "y": 7, "sprite": "avatar_dev", "name": "Receptionist Maya"},
        ],
    },
    "corridor_left": {
        "id": "corridor_left",
        "name": "Corredor Esquerdo",
        "width": 6, "height": 40,
        "is_meeting": False, "capacity": 5,
        "description": "Corredor de circulação vertical esquerdo.",
        "furniture": [],
        "doors": [
            {"x": 3, "y": 0, "target_room": "entrance", "target_x": 39, "target_y": 9, "width": 1, "label": "To Entrance"},
            {"x": 5, "y": 10, "target_room": "setor_dev", "target_x": 0, "target_y": 5, "width": 1, "label": "To Setor Dev"},
            {"x": 5, "y": 22, "target_room": "setor_ops", "target_x": 0, "target_y": 5, "width": 1, "label": "To Setor Ops"},
            {"x": 5, "y": 34, "target_room": "setor_watchdog", "target_x": 0, "target_y": 5, "width": 1, "label": "To Setor Watchdog"},
        ],
        "npc_spawns": [],
    },
    "setor_dev": {
        "id": "setor_dev",
        "name": "Setor DEV",
        "width": 30, "height": 10,
        "is_meeting": False, "capacity": 4,
        "description": "Setor de desenvolvimento de software.",
        "furniture": [
            {"type": "desk_cluster", "x": 4, "y": 2, "w": 8, "h": 6, "sprite": "furniture_desk_cluster"},
            {"type": "whiteboard", "x": 26, "y": 2, "w": 4, "h": 2, "sprite": "furniture_whiteboard"},
            {"type": "plant", "x": 1, "y": 8, "w": 1, "h": 1, "sprite": "furniture_plant"},
        ],
        "doors": [
            {"x": 0, "y": 5, "target_room": "corridor_left", "target_x": 5, "target_y": 10, "width": 1, "label": "To Corridor Left"},
        ],
        "npc_spawns": [
            {"role": "dev", "x": 10, "y": 5, "sprite": "avatar_dev", "name": "Alice"},
            {"role": "dev", "x": 12, "y": 5, "sprite": "avatar_dev", "name": "Bruno"},
        ],
    },
    "setor_ops": {
        "id": "setor_ops",
        "name": "Setor OPS",
        "width": 30, "height": 10,
        "is_meeting": False, "capacity": 4,
        "description": "Setor de operações e infraestrutura.",
        "furniture": [
            {"type": "monitoring_station", "x": 4, "y": 2, "w": 8, "h": 4, "sprite": "furniture_monitoring_station"},
            {"type": "server_rack", "x": 26, "y": 2, "w": 2, "h": 6, "sprite": "furniture_server_rack"},
            {"type": "plant", "x": 1, "y": 8, "w": 1, "h": 1, "sprite": "furniture_plant"},
        ],
        "doors": [
            {"x": 0, "y": 5, "target_room": "corridor_left", "target_x": 5, "target_y": 22, "width": 1, "label": "To Corridor Left"},
        ],
        "npc_spawns": [
            {"role": "devops", "x": 10, "y": 5, "sprite": "avatar_devops", "name": "Morgana"},
            {"role": "devops", "x": 12, "y": 5, "sprite": "avatar_devops", "name": "Liruh"},
        ],
    },
    "setor_watchdog": {
        "id": "setor_watchdog",
        "name": "Setor Watchdog/Sec",
        "width": 30, "height": 10,
        "is_meeting": False, "capacity": 4,
        "description": "Setor de segurança e monitoramento de sistemas.",
        "furniture": [
            {"type": "terminal", "x": 4, "y": 2, "w": 8, "h": 4, "sprite": "furniture_terminal"},
            {"type": "terminal", "x": 26, "y": 2, "w": 2, "h": 6, "sprite": "furniture_terminal"},
            {"type": "plant", "x": 1, "y": 8, "w": 1, "h": 1, "sprite": "furniture_plant"},
        ],
        "doors": [
            {"x": 0, "y": 5, "target_room": "corridor_left", "target_x": 5, "target_y": 34, "width": 1, "label": "To Corridor Left"},
        ],
        "npc_spawns": [
            {"role": "watchdog", "x": 10, "y": 5, "sprite": "avatar_watchdog", "name": "Debora"},
            {"role": "watchdog", "x": 12, "y": 5, "sprite": "avatar_watchdog", "name": "Nephy"},
        ],
    },
    "corridor_right": {
        "id": "corridor_right",
        "name": "Corredor Direito",
        "width": 6, "height": 40,
        "is_meeting": False, "capacity": 5,
        "description": "Corredor de circulação vertical direito.",
        "furniture": [],
        "doors": [
            {"x": 2, "y": 0, "target_room": "entrance", "target_x": 66, "target_y": 9, "width": 1, "label": "To Entrance"},
            {"x": 0, "y": 10, "target_room": "setor_creative", "target_x": 29, "target_y": 5, "width": 1, "label": "To Setor Creative"},
            {"x": 0, "y": 22, "target_room": "setor_biz", "target_x": 29, "target_y": 5, "width": 1, "label": "To Setor Biz"},
            {"x": 0, "y": 34, "target_room": "setor_research", "target_x": 29, "target_y": 5, "width": 1, "label": "To Setor Research"},
            {"x": 5, "y": 2, "target_room": "top_corridor", "target_x": 0, "target_y": 2, "width": 1, "label": "To Top Corridor"},
        ],
        "npc_spawns": [],
    },
    "setor_creative": {
        "id": "setor_creative",
        "name": "Setor Creative/Design",
        "width": 30, "height": 10,
        "is_meeting": False, "capacity": 4,
        "description": "Setor criativo e de design.",
        "furniture": [
            {"type": "whiteboard", "x": 4, "y": 2, "w": 4, "h": 2, "sprite": "furniture_whiteboard"},
            {"type": "whiteboard", "x": 26, "y": 2, "w": 4, "h": 2, "sprite": "furniture_whiteboard"},
            {"type": "plant", "x": 1, "y": 8, "w": 1, "h": 1, "sprite": "furniture_plant"},
        ],
        "doors": [
            {"x": 29, "y": 5, "target_room": "corridor_right", "target_x": 0, "target_y": 10, "width": 1, "label": "To Corridor Right"},
        ],
        "npc_spawns": [
            {"role": "dev", "x": 10, "y": 5, "sprite": "avatar_dev", "name": "Nephy Creative"},
            {"role": "dev", "x": 12, "y": 5, "sprite": "avatar_dev", "name": "Alice Creative"},
        ],
    },
    "setor_biz": {
        "id": "setor_biz",
        "name": "Setor Biz/Comms",
        "width": 30, "height": 10,
        "is_meeting": False, "capacity": 4,
        "description": "Setor de negócios e comunicações.",
        "furniture": [
            {"type": "coffee_table", "x": 4, "y": 2, "w": 2, "h": 1, "sprite": "furniture_coffee_table"},
            {"type": "sofa", "x": 26, "y": 2, "w": 4, "h": 2, "sprite": "furniture_sofa"},
            {"type": "plant", "x": 1, "y": 8, "w": 1, "h": 1, "sprite": "furniture_plant"},
        ],
        "doors": [
            {"x": 29, "y": 5, "target_room": "corridor_right", "target_x": 0, "target_y": 22, "width": 1, "label": "To Corridor Right"},
        ],
        "npc_spawns": [
            {"role": "biz", "x": 10, "y": 5, "sprite": "avatar_dev", "name": "Agent_B1"},
            {"role": "biz", "x": 12, "y": 5, "sprite": "avatar_dev", "name": "Agent_B2"},
        ],
    },
    "setor_research": {
        "id": "setor_research",
        "name": "Setor Research",
        "width": 30, "height": 10,
        "is_meeting": False, "capacity": 4,
        "description": "Setor de pesquisa e desenvolvimento avançado.",
        "furniture": [
            {"type": "bookshelf", "x": 4, "y": 2, "w": 8, "h": 4, "sprite": "furniture_bookshelf"},
            {"type": "terminal", "x": 26, "y": 2, "w": 4, "h": 4, "sprite": "furniture_terminal"},
            {"type": "plant", "x": 1, "y": 8, "w": 1, "h": 1, "sprite": "furniture_plant"},
        ],
        "doors": [
            {"x": 29, "y": 5, "target_room": "corridor_right", "target_x": 0, "target_y": 34, "width": 1, "label": "To Corridor Right"},
        ],
        "npc_spawns": [
            {"role": "research", "x": 10, "y": 5, "sprite": "avatar_dev", "name": "Agent_R1"},
            {"role": "research", "x": 12, "y": 5, "sprite": "avatar_dev", "name": "Agent_R2"},
        ],
    },
    "meeting_room": {
        "id": "meeting_room",
        "name": "Sala de Reunião",
        "width": 20, "height": 8,
        "is_meeting": True, "capacity": 8,
        "description": "Sala principal para reuniões de equipe.",
        "furniture": [
            {"type": "desk_cluster", "x": 4, "y": 2, "w": 12, "h": 4, "sprite": "furniture_desk_cluster"},
            {"type": "whiteboard", "x": 4, "y": 2, "w": 4, "h": 2, "sprite": "furniture_whiteboard"},
        ],
        "doors": [
            {"x": 9, "y": 7, "target_room": "top_corridor", "target_x": 19, "target_y": 2, "width": 1, "label": "To Top Corridor"},
        ],
        "npc_spawns": [],
    },
    "ceo_office": {
        "id": "ceo_office",
        "name": "Gabinete CEO",
        "width": 18, "height": 12,
        "is_meeting": False, "capacity": 2,
        "description": "Gabinete da liderança executiva.",
        "furniture": [
            {"type": "desk_cluster", "x": 4, "y": 2, "w": 10, "h": 4, "sprite": "furniture_desk_cluster"},
            {"type": "bookshelf", "x": 1, "y": 1, "w": 2, "h": 4, "sprite": "furniture_bookshelf"},
            {"type": "plant", "x": 16, "y": 1, "w": 1, "h": 1, "sprite": "furniture_plant"},
            {"type": "sofa", "x": 12, "y": 8, "w": 4, "h": 2, "sprite": "furniture_sofa"},
        ],
        "doors": [
            {"x": 0, "y": 6, "target_room": "top_corridor", "target_x": 32, "target_y": 2, "width": 1, "label": "To Top Corridor"},
        ],
        "npc_spawns": [
            {"role": "ceo", "x": 8, "y": 3, "sprite": "avatar_dev", "name": "CEO"},
            {"role": "hermes", "x": 10, "y": 3, "sprite": "avatar_dev", "name": "Hermes"},
        ],
    },
    "top_corridor": {
        "id": "top_corridor",
        "name": "Corredor Superior",
        "width": 50, "height": 4,
        "is_meeting": False, "capacity": 10,
        "description": "Corredor superior de conexão com diretoria e reuniões.",
        "furniture": [],
        "doors": [
            {"x": 0, "y": 2, "target_room": "corridor_right", "target_x": 5, "target_y": 2, "width": 1, "label": "To Corridor Right"},
            {"x": 19, "y": 2, "target_room": "meeting_room", "target_x": 9, "target_y": 7, "width": 1, "label": "To Meeting Room"},
            {"x": 32, "y": 2, "target_room": "ceo_office", "target_x": 0, "target_y": 6, "width": 1, "label": "To CEO Office"},
        ],
        "npc_spawns": [],
    },
}


# ============================================================
# Footprints de móveis por sprite, a partir do manifest (§2.2).
# backgroundTiles = fileiras do TOPO do footprint que NÃO bloqueiam.
# Manifest não define footprint para estes sprites legados; usamos
# w/h do layout, com backgroundTiles=1 para mesas/estações (§2.2).
# ============================================================
_BACKGROUND_ROWS = {
    "furniture_desk_cluster": 1,
    "furniture_desk": 1,
    "furniture_research_desk": 1,
    "furniture_lab_bench": 1,
    "furniture_reception": 1,
    "furniture_counter": 1,
    "furniture_table": 1,
    "furniture_coffee_table": 1,
    # monitoring_station não tem backgroundTiles: com bg=1 a fileira superior
    # (ex. 6..11,2 no ops_room) fica caminhável porém ilhada entre paredes
}


def _background_rows_for(sprite: str) -> int:
    return _BACKGROUND_ROWS.get(sprite, 0)


class Room:
    """Sala com tileMap (imutável) + blockedTiles (§2). SEM collision_grid."""

    def __init__(self, room_id: str, name: str, width: int, height: int,
                 is_meeting: bool = False, capacity: int = 8,
                 doors: Optional[List[Dict]] = None,
                 furniture: Optional[List[Dict]] = None):
        self.id = room_id
        self.name = name
        self.width = width
        self.height = height
        self.is_meeting = is_meeting
        self.capacity = capacity
        self.entities: Dict[str, Entity] = {}
        self.doors: List[Dict] = doors or []
        self.furniture: List[Dict] = furniture or []
        # Tapetes: visual LAYER_FLOOR, ZERO efeito em colisão (§2.3)
        self.carpet_tiles: List[List[int]] = []
        # backgroundTiles de móveis (fileiras visuais de fundo) para o cliente
        self.background_tiles: List[str] = []

        # tileMap: ints (WALL/FLOOR/VOID), imutável pós-build (§2.1)
        self.tile_map: List[List[int]] = [[FLOOR] * width for _ in range(height)]
        # blockedTiles: "col,row" — móveis + NPCs parados (§2.2)
        self.blocked_tiles: Set[str] = set()
        # deltas de blockedTiles acumulados no tick, p/ world.state.delta (§5.2)
        self.pending_deltas: List[Dict] = []

        self._build_tile_map()
        self._add_furniture_blocked()

    # ---------------- tileMap (build único) ----------------

    def _build_tile_map(self):
        """Grava paredes como WALL no build; portas ficam FLOOR (§2.3)."""
        for wall in INTERNAL_WALLS.get(self.id, []):
            for wx in range(wall["x"], wall["x"] + wall["w"]):
                for wy in range(wall["y"], wall["y"] + wall["h"]):
                    if 0 <= wx < self.width and 0 <= wy < self.height:
                        self.tile_map[wy][wx] = WALL
        # Tiles de porta são FLOOR, nunca WALL (§2.3)
        for door in self.doors:
            dx, dy = door.get("x"), door.get("y")
            if dx is not None and 0 <= dx < self.width and 0 <= dy < self.height:
                self.tile_map[dy][dx] = FLOOR

    def _add_furniture_blocked(self):
        """Preenche blocked_tiles a partir dos móveis, PULANDO backgroundTiles (§2.2)."""
        for furn in self.furniture:
            bg = _background_rows_for(furn.get("sprite", ""))
            for fx in range(furn["x"], furn["x"] + furn["w"]):
                for fy in range(furn["y"], furn["y"] + furn["h"]):
                    if not (0 <= fx < self.width and 0 <= fy < self.height):
                        continue
                    if fy < furn["y"] + bg:
                        # fileira de fundo: visual na frente, caminhável (§1.3)
                        self.background_tiles.append(f"{fx},{fy}")
                        continue
                    self.blocked_tiles.add(f"{fx},{fy}")

    # ---------------- colisão (§2) ----------------

    def is_walkable(self, col: int, row: int) -> bool:
        """tileMap ∈ FLOORS **E** fora de blockedTiles (§2.2). VOID/WALL explícitos."""
        if not (0 <= row < self.height and 0 <= col < self.width):
            return False
        t = self.tile_map[row][col]
        if t == WALL or t == VOID:
            return False
        return f"{col},{row}" not in self.blocked_tiles

    # ---------------- entidades ----------------

    def add_entity(self, entity: Entity):
        self.entities[entity.id] = entity
        # NPC parado bloqueia; JOGADOR NUNCA bloqueia (§2.4)
        if entity.type == "npc" and 0 <= entity.col < self.width and 0 <= entity.row < self.height:
            self.blocked_tiles.add(f"{entity.col},{entity.row}")

    def remove_entity(self, entity_id: str):
        entity = self.entities.pop(entity_id, None)
        if entity is not None and entity.type == "npc":
            self.blocked_tiles.discard(f"{entity.col},{entity.row}")

    def move_entity(self, entity_id: str, new_col: int, new_row: int) -> bool:
        """Movimento instantâneo (usado pelo npc_behaviors legado).
        NPC: remove origem ANTES, adiciona destino DEPOIS (§2.2).
        Jogador: nunca toca blockedTiles (§2.4)."""
        entity = self.entities.get(entity_id)
        if entity is None:
            return False
        if not (0 <= new_col < self.width and 0 <= new_row < self.height):
            return False
        old_col, old_row = entity.col, entity.row
        if (new_col, new_row) == (old_col, old_row):
            return True
        if not self.is_walkable(new_col, new_row) and entity.type != "player":
            return False
        if entity.type == "npc":
            self.blocked_tiles.discard(f"{old_col},{old_row}")
            self.blocked_tiles.add(f"{new_col},{new_row}")
            self.pending_deltas.append(
                {"op": "remove", "kind": "blockedTile", "col": old_col, "row": old_row})
            self.pending_deltas.append(
                {"op": "add", "kind": "blockedTile", "col": new_col, "row": new_row})
        entity.col, entity.row = new_col, new_row
        entity.path, entity.step_progress, entity.state = [], 0.0, "idle"
        return True

    # ---------------- pathfinding (§3) ----------------

    def find_path(self, start_col, start_row, goal_col, goal_row):
        p = pathfinding.find_path(self, (start_col, start_row), (goal_col, goal_row))
        if p is None:
            return []
        return [Position(t[0], t[1]) for t in p]

    def request_move(self, entity_id: str, goal_col: int, goal_row: int):
        """move.request (§3.2): retorna (path, reason). path=None + reason em falha.
        NPC parado bloqueia o próprio tile (§2.2) — a origem é liberada
        ANTES do BFS (padrão remove-origem-antes do §3.3) e o tick volta a
        bloquear no tile onde o NPC parar. Nunca deve fazer o path do
        próprio NPC falhar pelo seu tile de origem."""
        entity = self.entities.get(entity_id)
        if entity is None:
            return None, "unknown_entity"
        start = (entity.col, entity.row)
        goal = (int(goal_col), int(goal_row))
        if start == goal:
            return [start], None
        if not self.is_walkable(*goal):
            return None, "destination_blocked"
        origin_key = f"{start[0]},{start[1]}"
        origin_blocked = entity.type == "npc" and origin_key in self.blocked_tiles
        if origin_blocked:
            self.blocked_tiles.discard(origin_key)
        path = pathfinding.find_path(self, start, goal)
        if origin_blocked:
            # devolve origem ao estado anterior (parado ali até o tick andar)
            self.blocked_tiles.add(origin_key)
        if path is None:
            # distingue destino-em-si do que é caminhável (defensivo)
            return None, "destination_blocked" if not self.is_walkable(*goal) else "no_path"
        # path já começa em start; guarda o restante e inicia estado walking
        entity.path = path[1:]
        entity.step_progress = 0.0
        entity.state = "walking"
        entity.move_started_at = time.time()
        return path, None

    # ---------------- tick de movimento (§3.3) ----------------

    def tick(self, now: float) -> List[Dict]:
        """Avança entidades walking. Retorna âncoras entity.move a transmitir.
        Também acumula world.state.delta de blockedTiles (§5.2) em self.pending_deltas."""
        anchors = []
        for entity in list(self.entities.values()):
            if entity.state != "walking" or not entity.path:
                continue
            elapsed = (now - entity.move_started_at) * 1000.0
            step = int(elapsed // MOVE_TIME_MS)
            if step <= 0:
                continue
            entity.move_started_at += (step * MOVE_TIME_MS) / 1000.0
            for _ in range(step):
                old_col, old_row = entity.col, entity.row
                nxt = entity.path.pop(0)
                if entity.type == "npc":
                    # §2.2/§3.3: remove origem ANTES, adiciona destino DEPOIS
                    self.blocked_tiles.discard(f"{old_col},{old_row}")
                    self.blocked_tiles.add(f"{nxt[0]},{nxt[1]}")
                    self.pending_deltas.append(
                        {"op": "remove", "kind": "blockedTile", "col": old_col, "row": old_row})
                    self.pending_deltas.append(
                        {"op": "add", "kind": "blockedTile", "col": nxt[0], "row": nxt[1]})
                entity.col, entity.row = nxt
                entity.meta["direction"] = entity.direction()
                if entity.path:
                    anchors.append({"entity": entity, "moving": True})
                else:
                    entity.state = "idle"
                    entity.step_progress = 0.0
                    anchors.append({"entity": entity, "moving": False})
                    break
        return anchors

    def pop_deltas(self) -> List[Dict]:
        """Drena deltas acumulados p/ world.state.delta broadcast (§5.2)."""
        deltas, self.pending_deltas = self.pending_deltas, []
        return deltas

    # ---------------- spawn helper ----------------

    def find_free_spawn(self) -> (int, int):
        """Acha tile caminhável para spawn (nunca um tile de jogador, §2.4)."""
        if self.is_walkable(25, 8):
            return 25, 8
        for row in range(self.height):
            for col in range(self.width):
                if self.is_walkable(col, row):
                    return col, row
        return self.width // 2, self.height // 2


class RoomManager:
    """Gerencia salas + entidades globais (migrado de GameServer._init_world)."""

    def __init__(self, with_npcs: bool = True):
        self.rooms: Dict[str, Room] = {}
        self.entities: Dict[str, Entity] = {}
        self.npc_behavior_trees: Dict[str, object] = {}
        self._init_world(with_npcs)

    def _init_world(self, with_npcs: bool):
        from npc_behaviors import create_behavior_tree_for_role  # local pós-mundo
        for room_id, config in ROOM_CONFIGS.items():
            room = Room(
                room_id=config["id"], name=config["name"],
                width=config["width"], height=config["height"],
                is_meeting=config.get("is_meeting", False),
                capacity=config.get("capacity", 8),
                doors=config.get("doors", []),
                furniture=config.get("furniture", []),
            )
            self.rooms[room_id] = room
            for npc_cfg in config.get("npc_spawns", []) if with_npcs else []:
                npc_id = f"npc-{npc_cfg['role']}-{room_id}-{npc_cfg['x']}-{npc_cfg['y']}"
                npc = Entity(
                    id=npc_id, type="npc", name=npc_cfg["name"],
                    room_id=room_id, col=npc_cfg["x"], row=npc_cfg["y"],
                    characterKey=npc_cfg["sprite"],
                    meta={"name": npc_cfg["name"], "role": npc_cfg["role"],
                          "status": "idle", "direction": "down",
                          "home_room": room_id,
                          "preferred_rooms": self._preferred_rooms(npc_cfg["role"])},
                )
                self.entities[npc_id] = npc
                room.add_entity(npc)
                if with_npcs:
                    self.npc_behavior_trees[npc_id] = create_behavior_tree_for_role(
                        npc_cfg["role"], npc, self)
            # atualiza referência de rooms p/ spawn de NPCs usada pelo hello
            for e in room.entities.values():
                self.entities.setdefault(e.id, e)

    @staticmethod
    def _preferred_rooms(role: str) -> List[str]:
        prefs = {
            "dev": ["setor_dev", "entrance", "setor_creative", "top_corridor"],
            "devops": ["setor_ops", "entrance", "corridor_left", "top_corridor"],
            "watchdog": ["setor_watchdog", "entrance", "corridor_left", "top_corridor"],
            "receptionist": ["entrance"],
            "biz": ["setor_biz", "entrance", "corridor_right", "top_corridor"],
            "research": ["setor_research", "entrance", "corridor_right", "top_corridor"],
            "ceo": ["ceo_office", "top_corridor"],
            "hermes": ["ceo_office", "top_corridor"],
        }
        return prefs.get(role, ["entrance"])

    def get(self, room_id: str) -> Optional[Room]:
        return self.rooms.get(room_id)

    def spawn_player(self, entity_id: str, name: str, character_key: str) -> Entity:
        """Spawna player na entrance. Jogador nunca bloqueia (§2.4)."""
        room = self.rooms["entrance"]
        col, row = room.find_free_spawn()
        entity = Entity(id=entity_id, type="player", name=name,
                        room_id="entrance", col=col, row=row,
                        characterKey=character_key,
                        meta={"name": name, "direction": "down"})
        self.entities[entity_id] = entity
        room.add_entity(entity)
        return entity

    def despawn(self, entity_id: str):
        entity = self.entities.pop(entity_id, None)
        if entity is not None:
            room = self.rooms.get(entity.room_id)
            if room:
                room.remove_entity(entity_id)
        return entity
