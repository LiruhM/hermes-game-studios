# mock_server.py — Mock do protocolo §5 p/ testes LOCAIS do cliente (C1-C7).
# IMPLEMENTADOR C: uso exclusivo; não faz parte do jogo.
# Finge o servidor autoritativo: welcome, move.path, entity.move (âncoras),
# move.rejected, world.sync, world.state.delta, chat.message.
# Requisito: `pip install websockets` (ou py -3.11). Roda em 127.0.0.1:8080/ws.
import asyncio, json, time, random
import websockets

W, H = 20, 20
MOVE_TIME_MS = 350
TICK_HZ = 10

# tileMap: perímetro WALL, resto FLOOR
TILE_MAP = [[0 if (r in (0, H-1) or c in (0, W-1)) else 1
             for c in range(W)] for r in range(H)]
BLOCKED = {(10, 10), (10, 11), (5, 5)}          # "col,row" tiles de móveis
NPCS = [f"npc_{i}" for i in range(12)]

def tkey(c, r): return f"{c},{r}"

def is_walkable(c, r):
    if not (0 <= r < H and 0 <= c < W): return False
    if TILE_MAP[r][c] == 0: return False
    return tkey(c, r) not in BLOCKED

def bfs(start, goal):
    if start == goal: return [start]
    if not is_walkable(*goal): return None
    from collections import deque
    came = {start: None}; q = deque([start])
    while q:
        cur = q.popleft()
        if cur == goal:
            path = []
            while cur is not None:
                path.append(cur); cur = came[cur]
            return path[::-1]
        for d in ((0,-1),(0,1),(-1,0),(1,0)):
            nxt = (cur[0]+d[0], cur[1]+d[1])
            if nxt not in came and is_walkable(*nxt):
                came[nxt] = cur; q.append(nxt)
    return None

# Estado por conexão: { id, col, row, path, seg_start, moving, conn }
ENTS = {}   # id -> state
LOCK = asyncio.Lock()

def now(): return int(time.time() * 1000)

def ent_msg(e):
    return {"id": e["id"], "type": e["type"], "name": e["id"],
            "col": e["col"], "row": e["row"], "characterKey": "player_default", "meta": {}}

def broadcast(msg):
    data = json.dumps(msg)
    dead = []
    for eid, e in ENTS.items():
        if e.get("conn") is None: dead.append(eid); continue
        try:
            asyncio.ensure_future(e["conn"].send(data))
        except Exception:
            dead.append(eid)
    for eid in dead: ENTS.pop(eid, None)

async def tick_loop():
    # Simula §3.3: avança 1 tile por MOVE_TIME_MS, emite âncora a cada tile
    while True:
        await asyncio.sleep(1 / TICK_HZ)
        t = now()
        async with LOCK:
            for e in ENTS.values():
                if not e.get("moving") or not e.get("path"): continue
                while e["path"] and t - e["seg_start"] >= MOVE_TIME_MS:
                    e["path"].pop(0)
                    e["seg_start"] += MOVE_TIME_MS
                    if len(e["path"]) == 0:
                        e["moving"] = False
                        break
                    e["col"], e["row"] = e["path"][0]
                    if len(e["path"]) > 1:
                        d = (e["path"][1][0] - e["col"], e["path"][1][1] - e["row"])
                        dirn = "e" if d[0] > 0 else "w" if d[0] < 0 else "s" if d[1] > 0 else "n"
                        broadcast({"type": "entity.move", "entityId": e["id"],
                                    "col": e["col"], "row": e["row"], "moving": True,
                                    "dir": dirn, "serverTime": t})
                    else:
                        e["moving"] = False
                        broadcast({"type": "entity.move", "entityId": e["id"],
                                   "col": e["col"], "row": e["row"], "moving": False,
                                   "dir": "s", "serverTime": t})

async def handle(ws):
    # websockets 15+: path não é mais argumento de serve(); filtra manualmente
    if getattr(ws, "request", None) is not None and getattr(ws.request, "path", "/ws") != "/ws":
        return
    eid = None
    try:
        async for raw in ws:
            msg = json.loads(raw)
            t = now()
            typ = msg.get("type")
            if typ == "client.hello":
                eid = f"player_{random.randint(1000, 9999)}"
                async with LOCK:
                    ENTS[eid] = {"id": eid, "type": "player", "col": 3, "row": 3,
                                 "path": None, "seg_start": 0, "moving": False, "conn": ws}
                    # NPCs de exemplo no snapshot
                    for i, nid in enumerate(NPCS):
                        ENTS[nid] = {"id": nid, "type": "npc", "col": 4 + i, "row": 5,
                                     "path": None, "seg_start": 0, "moving": False, "conn": None}
                await ws.send(json.dumps({
                    "type": "welcome",
                    "entityId": eid, "name": msg.get("name", "Jogador"),
                    "room": {"id": "main_office", "name": "Escritório", "width": W, "height": H,
                             "tileMap": TILE_MAP,
                             "blockedTiles": [tkey(*b) for b in BLOCKED],
                             "doors": [], "furniture": [
                               {"id": "desk1", "type": "desk", "col": 10, "row": 10,
                                "characterKey": "desk_wood", "meta": {"footprintW": 1, "footprintH": 2}},
                               {"id": "plant1", "type": "plant", "col": 5, "row": 5,
                                "characterKey": "plant_small", "meta": {}}],
                             "carpetTiles": [{"col": 7, "row": 7}, {"col": 8, "row": 7}]},
                    "entities": [ent_msg(e) for e in ENTS.values()],
                    "moveTimeMs": MOVE_TIME_MS, "serverTime": t}))
                broadcast({"type": "entity.spawn", "entity": ent_msg(ENTS[eid])})
            elif typ == "move.request":
                e = ENTS.get(msg.get("entityId"))
                if not e: continue
                goal = (msg["targetCol"], msg["targetRow"])
                path = bfs((e["col"], e["row"]), goal)
                if path is None:
                    reason = "destination_blocked" if not is_walkable(*goal) else "no_path"
                    await ws.send(json.dumps({"type": "move.rejected", "entityId": e["id"],
                                              "targetCol": goal[0], "targetRow": goal[1],
                                              "reason": reason}))
                else:
                    e["path"] = path; e["seg_start"] = t; e["moving"] = True
                    broadcast({"type": "move.path", "entityId": e["id"], "path": path,
                                "startedAt": t, "moveTimeMs": MOVE_TIME_MS})
            elif typ == "ping":
                await ws.send(json.dumps({"type": "pong", "serverTime": t}))
            elif typ == "chat.message":
                broadcast({"type": "chat.message", "from": eid, "fromName": eid,
                           "content": msg.get("content", ""), "timestamp": t})
            elif typ == "npc.dialogue.request":
                await ws.send(json.dumps({"type": "npc.dialogue.response", "npc_id": msg.get("npcId"),
                                          "npc_name": "Mock NPC", "text": "Olá!", "actions": []}))
            else:
                await ws.send(json.dumps({"type": "error", "code": "unknown_type",
                                          "message": typ}))
    finally:
        async with LOCK:
            if eid and eid in ENTS:
                ENTS.pop(eid, None)
                broadcast({"type": "entity.despawn", "entityId": eid, "reason": "left"})

async def main():
    async with websockets.serve(handle, "127.0.0.1", 8080):
        print("mock_server listening ws://127.0.0.1:8080/ws")
        await tick_loop()

if __name__ == "__main__":
    asyncio.run(main())
