# -*- coding: utf-8 -*-
"""
pathfinding.py — BFS 4-direções puro (BLUEPRINT §3).

Função pura: recebe `room` (qualquer objeto com is_walkable(col,row)),
start e goal como (col,row). Sem estado, sem heapq, sem numpy.
O tile do jogador NUNCA é bloqueado (§2.4) — start não entra no check.
"""
from collections import deque

# Vizinhança 4-direções (§3.1): N, S, O, L — sem diagonais
DIRS4 = ((0, -1), (0, 1), (-1, 0), (1, 0))


def find_path(room, start, goal):
    """BFS 4-dir. start/goal = (col, row).

    Retorna lista [(col,row), ...] incluindo start e goal, ou None se:
      - goal não é caminhável (-> move.rejected: destination_blocked)
      - start não é caminhável (defensivo; não deve ocorrer, §2.4)
      - não existe caminho (-> move.rejected: no_path)
    """
    start, goal = tuple(start), tuple(goal)
    if start == goal:
        return [start]
    if not _walkable(room, goal):
        return None
    if not _walkable(room, start):
        return None  # defensivo (§3.1)

    came_from = {start: None}
    queue = deque([start])
    while queue:
        cur = queue.popleft()
        if cur == goal:
            path = []
            while cur is not None:
                path.append(cur)
                cur = came_from[cur]
            path.reverse()
            return path
        for d in DIRS4:
            nxt = (cur[0] + d[0], cur[1] + d[1])
            if nxt not in came_from and _walkable(room, nxt):
                came_from[nxt] = cur
                queue.append(nxt)
    return None  # no_path


def _walkable(room, tile):
    """Wrapper defensivo: rooms.Room.is_walkable(col, row)."""
    try:
        return room.is_walkable(tile[0], tile[1])
    except Exception:
        return False
