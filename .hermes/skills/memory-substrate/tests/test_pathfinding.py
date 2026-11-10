# -*- coding: utf-8 -*-
"""
tests/test_pathfinding.py — Critério A1 do BLUEPRINT §8.1.

Roda standalone (`python tests/test_pathfinding.py`) ou via pytest.
Não requer servidor rodando.
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathfinding import find_path          # noqa: E402
from rooms import RoomManager, Room, ROOM_CONFIGS  # noqa: E402
from entities import Entity, WALL, FLOOR, VOID  # noqa: E402


class FakeRoom:
    """Room mínima para testes de unidade do BFS (is_walkable only)."""

    def __init__(self, width, height, walls=(), blocked=()):
        self.width, self.height = width, height
        self.walls = set(walls)
        self.blocked = set(blocked)

    def is_walkable(self, col, row):
        if not (0 <= col < self.width and 0 <= row < self.height):
            return False
        if (col, row) in self.walls:
            return False
        return (col, row) not in self.blocked


def test_straight_line():
    # caminho reto de 5 tiles = 5 passos (inclui start)
    room = FakeRoom(10, 10)
    path = find_path(room, (0, 0), (4, 0))
    assert path == [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)], path
    assert len(path) == 5


def test_wall_destination():
    room = FakeRoom(10, 10, walls={(4, 4)})
    assert find_path(room, (0, 0), (4, 4)) is None


def test_blocked_destination():
    # destino em blockedTiles -> None
    room = FakeRoom(10, 10, blocked={(4, 4)})
    assert find_path(room, (0, 0), (4, 4)) is None


def test_out_of_bounds_destination():
    # VOID / fora do grid -> None
    room = FakeRoom(10, 10)
    assert find_path(room, (0, 0), (20, 20)) is None
    assert find_path(room, (0, 0), (-1, 0)) is None


def test_no_path_returns_none():
    # cercado por paredes -> None (no_path)
    walls = {(2, 1), (1, 2), (3, 2), (2, 3)}
    room = FakeRoom(5, 5, walls=walls)
    assert find_path(room, (0, 0), (2, 2)) is None


def test_player_tile_never_blocked():
    # §2.4/§8.1 A1: start = tile do jogador NUNCA é bloqueado.
    # Player em tile "bloqueado" por outro player ainda encontra path.
    manager = RoomManager(with_npcs=False)
    room = manager.spawn_player("p1", "P1", "avatar_player").room_id
    room = manager.get(room)
    p1 = manager.spawn_player("p1", "P1", "avatar_player")
    # dois players no MESMO tile (permitido §2.4) — path não pode falhar
    p2 = manager.spawn_player("p2", "P2", "avatar_player")
    p2.col, p2.row = p1.col, p1.row
    room.add_entity(p2)  # player não bloqueia: nenhuma mudança em blocked_tiles
    key = f"{p1.col},{p1.row}"
    assert key not in room.blocked_tiles
    path = find_path(room, (p1.col, p1.row), (p1.col + 3, p1.row))
    assert path is not None and len(path) == 4


def test_40x40_with_obstacles_fast():
    # sala 40x40 com obstáculos: caminho válido < 50ms
    walls = set()
    for x in range(1, 39):
        walls.add((x, 10))     # parede horizontal com gaps
        walls.add((x, 20))
        walls.add((x, 30))
    walls.discard((5, 10)); walls.discard((35, 20)); walls.discard((20, 30))
    blocked = {(x, y) for x in range(15, 25) for y in range(15, 18)}  # "móveis"
    room = FakeRoom(40, 40, walls=walls, blocked=blocked)
    t0 = time.perf_counter()
    path = find_path(room, (0, 0), (39, 39))
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert path is not None, "deveria existir caminho no 40x40"
    assert elapsed_ms < 50, f"BFS demorou {elapsed_ms:.2f}ms (>50ms)"
    # valida caminho: contíguo 4-dir, todos caminháveis
    for a, b in zip(path, path[1:]):
        assert abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1
    for tile in path:
        assert room.is_walkable(*tile)
    assert path[0] == (0, 0) and path[-1] == (39, 39)


def test_real_room_entrance_to_setor_dev():
    # integração: atravessa entrance -> corridor_left -> setor_dev
    manager = RoomManager(with_npcs=False)
    entrance = manager.get("entrance")
    corridor = manager.get("corridor_left")
    dev = manager.get("setor_dev")
    # spawn na entrance, porta central (39,9) -> corridor (3,0) -> dev (0,5)
    path = find_path(entrance, (39, 5), (39, 9))
    assert path is not None, "entrance to door"
    # corridor
    path = find_path(corridor, (3, 0), (5, 10))
    assert path is not None and path[0] == (3, 0) and path[-1] == (5, 10), f"corridor: {path}"
    for tile in path:
        assert corridor.is_walkable(*tile)
    # setor_dev
    path = find_path(dev, (0, 5), (15, 5))
    assert path is not None and path[0] == (0, 5) and path[-1] == (15, 5), f"dev: {path}"
    for tile in path:
        assert dev.is_walkable(*tile)


def test_real_room_ceo_office_reachable():
    # gabinete CEO acessível a partir do top_corridor
    manager = RoomManager(with_npcs=False)
    top = manager.get("top_corridor")
    ceo = manager.get("ceo_office")
    path = find_path(top, (32, 2), (32, 2))
    assert path == [(32, 2)]
    # porta (0,6) -> tile caminhável no corredor (8,6) (mesma linha da porta, livre)
    path = find_path(ceo, (0, 6), (8, 6))
    assert path is not None and path[0] == (0, 6) and path[-1] == (8, 6), f"path: {path}"
    for tile in path:
        assert ceo.is_walkable(*tile)


def test_start_equals_goal():
    room = FakeRoom(5, 5)
    assert find_path(room, (2, 2), (2, 2)) == [(2, 2)]


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
