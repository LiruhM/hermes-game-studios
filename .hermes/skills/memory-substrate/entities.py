# -*- coding: utf-8 -*-
"""
entities.py — Entidades do mundo (BLUEPRINT §6.1).

Entity carrega os campos do protocolo §5 (col, row, characterKey) e mantém
compatibilidade com o npc_behaviors.py existente via property `position`
(x==col, y==row). Jogadores NUNCA entram em blockedTiles (§2.4).
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

# Tipos de tile (§2.1) — ints serializáveis direto no welcome
WALL = 0
FLOOR = 1
VOID = 255

# Constantes de movimento compartilhadas com o cliente (welcome §5)
MOVE_TIME_MS = 350       # ms por tile (§3.3)
TICK_HZ = 10             # tick de lógica do servidor (§3.3)
TILE_SIZE = 32


@dataclass
class Position:
    """Posição em tiles (x=col, y=row). Compat com game_server antigo."""
    x: int
    y: int

    def to_dict(self):
        return {"x": self.x, "y": self.y}


class _PositionView:
    """Visão mutável de position (x<->col, y<->row) para o npc_behaviors."""
    __slots__ = ("ent",)

    def __init__(self, ent):
        self.ent = ent

    @property
    def x(self):
        return self.ent.col

    @x.setter
    def x(self, v):
        self.ent.col = int(v)

    @property
    def y(self):
        return self.ent.row

    @y.setter
    def y(self, v):
        self.ent.row = int(v)

    def to_dict(self):
        return {"x": self.ent.col, "y": self.ent.row}


@dataclass
class Entity:
    """Entidade do mundo — §6.1: id, type, name, col, row, characterKey, meta, path, step_progress."""
    id: str
    type: str                        # "player" | "npc"
    name: str = ""
    room_id: str = "reception"
    col: int = 0
    row: int = 0
    characterKey: str = "avatar_player"   # §5: characterKey
    meta: Dict[str, Any] = field(default_factory=dict)
    owner_id: Optional[str] = None
    # Estado de movimento server-side (§3.3)
    path: List = field(default_factory=list)          # [(col,row), ...] restante
    step_progress: float = 0.0                        # 0..1 dentro do tile atual
    state: str = "idle"                               # idle | walking
    move_started_at: float = 0.0                     # time.time() do início do path

    # ---- compatibilidade npc_behaviors: entity.position.x / .y ----
    @property
    def position(self) -> _PositionView:
        return _PositionView(self)

    @position.setter
    def position(self, p):
        self.col, self.row = int(p.x), int(p.y)

    @property
    def sprite(self) -> str:
        """Compat: sprite antigo == characterKey novo."""
        return self.characterKey

    @sprite.setter
    def sprite(self, v):
        self.characterKey = v

    # direção derivada do último delta de tile (§5: n/s/e/w)
    def direction(self) -> str:
        if len(self.path) >= 1:
            nxt = self.path[0]
            dx, dy = nxt[0] - self.col, nxt[1] - self.row
            if dy < 0:
                return "n"
            if dy > 0:
                return "s"
            if dx > 0:
                return "e"
            if dx < 0:
                return "w"
        return self.meta.get("direction", "s")

    def to_dict(self) -> Dict:
        """Superset: campos §5 (col,row,characterKey) + legado (position,sprite,room_id)."""
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "col": self.col,
            "row": self.row,
            "characterKey": self.characterKey,
            "meta": self.meta,
            # legado (npc_behaviors/frontend antigo)
            "room_id": self.room_id,
            "position": {"x": self.col, "y": self.row},
            "sprite": self.characterKey,
            "owner_id": self.owner_id,
        }
