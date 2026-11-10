#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
server.py — Main do servidor Hermes-Corp (BLUEPRINT §6.1, §7.1).

Loop aiohttp/websockets, conexões, ping/pong, tick 10Hz (§3.3) e
despacho via protocol.Protocol. Substitui game_server.py (apagado).
"""
import argparse
import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

import aiohttp
from aiohttp import web, WSMsgType

from entities import TICK_HZ
from protocol import Protocol, SUPERVISOR_URL, now_ms
from conversation import ConversationManager

# ---------------- logging (migrado intacto) ----------------
LOG_DIR = Path.home() / "AppData" / "Local" / "hermes" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_DIR / "game_server.log"), logging.StreamHandler()],
)


@dataclass
class ClientConnection:
    ws: web.WebSocketResponse
    entity_id: Optional[str] = None
    room_id: Optional[str] = None
    seq: int = 0
    last_ping: float = field(default_factory=time.time)


class GameServer:
    """Núcleo de conexão + loop. Lógica de sala: rooms.py; despacho: protocol.py."""

    def __init__(self, with_npcs: bool = True):
        import rooms as rooms_mod
        self.logger = logging.getLogger("server")
        self.manager = rooms_mod.RoomManager(with_npcs=with_npcs)
        self.protocol = Protocol(self)
        # Conversa NPC<->NPC (BLUEPRINT-P1): máquina de estados + gate LLM.
        # Vive no tick 10Hz mas só consome resultados prontos (R5).
        self.conversation_mgr = ConversationManager(self.manager)
        self.clients: Dict[str, ClientConnection] = {}
        self.supervisor_session: Optional[aiohttp.ClientSession] = None
        self.memory_session: Optional[aiohttp.ClientSession] = None
        self.running = False
        self._tick_task: Optional[asyncio.Task] = None
        self._last_tick = time.time()

    # ---------------- ciclo de vida ----------------

    async def start(self):
        self.running = True
        self.supervisor_session = aiohttp.ClientSession()
        self.memory_session = aiohttp.ClientSession()
        self._tick_task = asyncio.create_task(self._tick_loop())
        self.logger.info("Game Server started")

    async def stop(self):
        self.running = False
        if self._tick_task:
            self._tick_task.cancel()
        for client in list(self.clients.values()):
            await client.ws.close()
        if self.supervisor_session:
            await self.supervisor_session.close()
        if self.memory_session:
            await self.memory_session.close()
        self.logger.info("Game Server stopped")

    async def _tick_loop(self):
        """Tick 10Hz (§3.3): NPC behaviors + avanço de movimento + âncoras."""
        while self.running:
            try:
                start = time.time()
                self._last_tick = start

                # NPCs (behaviors legados, tick intacto)
                for entity_id, tree in list(self.manager.npc_behavior_trees.items()):
                    try:
                        await tree.tick()
                    except Exception as e:
                        self.logger.error(f"Behavior tree error for {entity_id}: {e}")

                # Conversa NPC<->NPC (BLUEPRINT-P1 §7): tick comportamental
                # interno (~1 Hz) — síncrono, zero I/O, nunca espera LLM (R5).
                self.conversation_mgr.tick(time.time())

                # Avanço server-side de movimento + âncoras entity.move (§5.2)
                for room in self.manager.rooms.values():
                    for anchor in room.tick(time.time()):
                        ent = anchor["entity"]
                        await self.broadcast_to_room(ent.room_id, "entity.move", {
                            "entityId": ent.id,
                            "col": ent.col, "row": ent.row,
                            "moving": anchor["moving"],
                            "dir": ent.direction(),
                            "serverTime": now_ms(),
                        })
                    # world.state.delta: mudanças de blockedTiles (§5.2)
                    deltas = room.pop_deltas()
                    if deltas:
                        await self.broadcast_to_room(room.id, "world.state.delta", {
                            "changes": deltas,
                            "serverTime": now_ms(),
                        })

                # Conversa NPC<->NPC: drena fila de mensagens prontas
                # (npc.conversation.state / npc.conversation.line) — sem I/O no tick
                for room_id, msg_type, payload in self.conversation_mgr.drain_outbox():
                    await self.broadcast_to_room(room_id, msg_type, payload)

                elapsed = time.time() - start
                await asyncio.sleep(max(0, (1.0 / TICK_HZ) - elapsed))
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Tick loop error: {e}")
                await asyncio.sleep(1)

    # ---------------- websocket ----------------

    async def handle_websocket(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        client_id = str(uuid.uuid4())
        self.clients[client_id] = ClientConnection(ws=ws)
        self.logger.info(f"Client connected: {client_id}")
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    await self.protocol.dispatch(client_id, msg.data)
                elif msg.type == WSMsgType.ERROR:
                    self.logger.error(f"WS error: {ws.exception()}")
        finally:
            await self._disconnect_client(client_id)
        return ws

    async def _disconnect_client(self, client_id: str):
        client = self.clients.pop(client_id, None)
        if not client:
            return
        if client.entity_id:
            entity = self.manager.despawn(client.entity_id)
            if entity:
                await self.broadcast_to_room(entity.room_id, "entity.despawn",
                                             {"entityId": entity.id, "reason": "left"})
        self.logger.info(f"Client disconnected: {client_id}")

    # ---------------- envio ----------------

    async def send_message(self, client_id: str, msg_type: str, payload: dict, ref_msg_id: str = None):
        client = self.clients.get(client_id)
        if not client or client.ws.closed:
            return
        msg = {
            "msg_id": ref_msg_id or str(uuid.uuid4()),
            "type": msg_type,
            "payload": payload,
            "ts": now_ms(),
            "seq": client.seq,
        }
        client.seq += 1
        try:
            await client.ws.send_json(msg)
        except Exception as e:
            self.logger.error(f"Send error to {client_id}: {e}")

    async def send_error(self, client_id: str, code: str, message: str):
        await self.send_message(client_id, "error", {"code": code, "message": message})

    async def broadcast_to_room(self, room_id: str, msg_type: str, payload: dict, exclude: str = None):
        for cid, client in self.clients.items():
            if client.ws.closed or client.room_id != room_id or cid == exclude:
                continue
            await self.send_message(cid, msg_type, payload)

    async def supervisor_call(self, method: str, params: dict) -> dict:
        """JSON-RPC ao Supervisor — copy-migrate intacto."""
        if not self.supervisor_session:
            raise Exception("Supervisor session not available")
        rpc = {"jsonrpc": "2.0", "method": method, "params": params, "id": str(uuid.uuid4())}
        async with self.supervisor_session.post(SUPERVISOR_URL, json=rpc) as resp:
            result = await resp.json()
            if "error" in result:
                raise Exception(f"Supervisor error: {result['error']}")
            return result.get("result", {})

    async def supervisor_ws_proxy(self, ws: web.WebSocketResponse):
        """Proxy WS -> Supervisor RPC — copy-migrate intacto."""
        import json as _json
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    request = None
                    try:
                        request = _json.loads(msg.data)
                        payload = {
                            "jsonrpc": "2.0",
                            "method": request.get("method"),
                            "params": request.get("params", {}),
                            "id": request.get("id"),
                        }
                        async with self.supervisor_session.post(SUPERVISOR_URL, json=payload) as resp:
                            result = await resp.json()
                        await ws.send_json(result)
                    except _json.JSONDecodeError:
                        await ws.send_json({"jsonrpc": "2.0", "id": None,
                                             "error": {"code": -32700, "message": "Parse error"}})
                    except Exception as e:
                        await ws.send_json({"jsonrpc": "2.0",
                                             "id": request.get("id") if request else None,
                                             "error": {"code": -32603, "message": str(e)}})
        except Exception as e:
            self.logger.error(f"Supervisor WS proxy error: {e}")
        finally:
            if not ws.closed:
                await ws.close()


# ---------------- HTTP routes (migradas intactas) ----------------

async def health_check(request):
    gs = request.app["game_server"]
    return web.json_response({
        "status": "healthy",
        "uptime_seconds": time.time() - gs._last_tick,
        "connections": len(gs.clients),
        "entities": len(gs.manager.entities),
    })


async def metrics(request):
    gs = request.app["game_server"]
    ents = gs.manager.entities
    text = (
        f"# HELP game_server_uptime_seconds Server uptime\n# TYPE game_server_uptime_seconds gauge\n"
        f"game_server_uptime_seconds {time.time() - gs._last_tick}\n\n"
        f"# HELP game_server_connections_active Active WebSocket connections\n"
        f"# TYPE game_server_connections_active gauge\n"
        f"game_server_connections_active {len(gs.clients)}\n\n"
        f"# HELP game_server_entities_total Total entities in world\n"
        f"# TYPE game_server_entities_total gauge\n"
        f'game_server_entities_total{{type="player"}} {sum(1 for e in ents.values() if e.type == "player")}\n'
        f'game_server_entities_total{{type="npc"}} {sum(1 for e in ents.values() if e.type == "npc")}\n'
    )
    return web.Response(text=text, content_type="text/plain")


async def create_app(with_npcs: bool = True):
    game_server = GameServer(with_npcs=with_npcs)
    await game_server.start()

    @web.middleware
    async def cors_middleware(request, handler):
        origin = request.headers.get("Origin", "")
        allowed = ["http://127.0.0.1:8080", "http://localhost:8080"]
        cors_origin = origin if origin in allowed else allowed[0]
        if request.method == "OPTIONS":
            return web.Response(headers={
                "Access-Control-Allow-Origin": cors_origin,
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Max-Age": "86400",
            })
        response = await handler(request)
        response.headers["Access-Control-Allow-Origin"] = cors_origin
        return response

    async def options_handler(request):
        return web.Response(headers={
            "Access-Control-Allow-Origin": "http://127.0.0.1:8080",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "86400",
        })

    app = web.Application(middlewares=[cors_middleware])
    app["game_server"] = game_server
    app.router.add_get("/ws", game_server.handle_websocket)
    app.router.add_get("/health", health_check)
    app.router.add_get("/metrics", metrics)
    app.router.add_get("/ws/supervisor", game_server.supervisor_ws_proxy)
    for p in ("/ws", "/health", "/metrics", "/ws/supervisor"):
        app.router.add_options(p, options_handler)

    async def cleanup(app):
        await game_server.stop()

    app.on_cleanup.append(cleanup)
    return app


def main():
    parser = argparse.ArgumentParser(description="Hermes-Corp Game Server")
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--no-npcs", action="store_true", help="sobe sem NPCs (testes)")
    args = parser.parse_args()

    async def run():
        app = await create_app(with_npcs=not args.no_npcs)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, args.host, args.port)
        await site.start()
        print(f"listening ws://{args.host}:{args.port}/ws")
        await asyncio.Event().wait()

    asyncio.run(run())


if __name__ == "__main__":
    main()
