# -*- coding: utf-8 -*-
"""
protocol.py — Despacho de mensagens + serialização (BLUEPRINT §5, §6.1).

HANDLERS: dicionário {type: handler}. Handlers legados (chat.message,
meeting.*, npc.dialogue.*) foram copy-migrados SEM refatoração de lógica.
Novos: client.hello (welcome §5.2), move.request (§3.2), world.sync.
type desconhecido -> error code=unknown_type, conexão NÃO cai (§5.3).
"""
import json
import time
import uuid
from typing import Any, Dict, Optional

from entities import MOVE_TIME_MS, TILE_SIZE, TICK_HZ
from rooms import ROOM_CONFIGS, RoomManager

# Constantes de integração (migradas intactas)
SUPERVISOR_URL = "http://127.0.0.1:3120/rpc"
MEMORY_SUBSTRATE_URL = "http://127.0.0.1:8767"

# Lazy wake do Memory Substrate (economia de ~1GB RAM no boot da stack):
# o serviço só sobe quando o primeiro diálogo NPC acontece.
_mem_substrate_booting = False


def _memory_substrate_alive() -> bool:
    """True se a porta 8767 responde (serviço de pé).
    Timeout GENEROSO (10s): o health calcula stats de 750k+ chunks e
    pode levar >2s sob throttling — timeout curto dava falso 'down'."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"{MEMORY_SUBSTRATE_URL}/health", timeout=10) as r:
            return r.status == 200
    except Exception:
        return False


async def ensure_memory_substrate(logger) -> bool:
    """
    Garante que o Memory Substrate esteja de pé, acordando-o se necessário.
    Chamado apenas pelo handler de diálogo NPC (único consumidor do jogo).
    ASSÍNCRONA: espera com asyncio.sleep — NUNCA bloquear o event loop.
    Retorna True quando o serviço responde, False se falhar/timeout.
    """
    global _mem_substrate_booting
    if _memory_substrate_alive():
        return True
    if not _mem_substrate_booting:
        _mem_substrate_booting = True
        logger.info("Memory Substrate down — acordando (lazy wake, ~15-30s no 5700U)...")
        import subprocess, sys, os
        try:
            # detached: o processo sobrevive ao game server
            subprocess.Popen(
                [
                    sys.executable, "-c",
                    "import uvicorn\n"
                    "from memory_substrate.api_gateway import app\n"
                    "uvicorn.run(app, host='127.0.0.1', port=8767, log_level='info', reload=False)",
                ],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "DETACHED_PROCESS", 0) |
                            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
        except Exception as e:
            logger.error(f"Falha ao acordar Memory Substrate: {e}")
            _mem_substrate_booting = False
            return False
    # Espera o boot (timeout 150s — índice de 750k+ chunks/6GB em hardware
    # modesto; medido: pode passar de 60s no 5700U sob throttling).
    # asyncio.sleep deixa o event loop respirar — o servidor inteiro
    # continua respondendo ping/movimento durante o cold start.
    import time
    import asyncio
    deadline = time.time() + 150
    while time.time() < deadline:
        if _memory_substrate_alive():
            _mem_substrate_booting = False
            logger.info("Memory Substrate acordou — diálogo pode prosseguir")
            return True
        await asyncio.sleep(2)
    _mem_substrate_booting = False
    return False


def now_ms() -> int:
    return int(time.time() * 1000)


class Protocol:
    """Camada de protocolo: valida payloads, serializa welcome/delta,
    e despacha mensagens C->S para o GameServer (server.py)."""

    def __init__(self, server):
        # server = GameServer (server.py) — contém manager, clients, broadcast
        self.server = server

    # ---------------- serialização §5.2 ----------------

    def build_welcome(self, entity, manager: RoomManager) -> Dict:
        """welcome conforme §5.2 — tileMap UMA vez, blockedTiles como array."""
        room = manager.rooms[entity.room_id]
        return {
            "entityId": entity.id,
            "name": entity.name,
            "room": self.build_room_payload(room),
            "entities": [e.to_dict() for e in room.entities.values()],
            "moveTimeMs": MOVE_TIME_MS,
            "serverTime": now_ms(),
        }

    @staticmethod
    def build_room_payload(room) -> Dict:
        """Serializa sala: tileMap (ints), blockedTiles ("col,row"), doors,
        furniture, carpetTiles. PROIBIDO boolean-grid (§5.3)."""
        return {
            "id": room.id,
            "name": room.name,
            "width": room.width,
            "height": room.height,
            "is_meeting": room.is_meeting,
            "capacity": room.capacity,
            "tileMap": room.tile_map,
            "blockedTiles": sorted(room.blocked_tiles),
            "backgroundTiles": sorted(room.background_tiles),
            "doors": room.doors,
            "furniture": room.furniture,
            "carpetTiles": room.carpet_tiles,
        }

    def build_world_sync(self, manager: RoomManager, room_id: str) -> Dict:
        room = manager.rooms.get(room_id)
        return {
            "entities": [e.to_dict() for e in room.entities.values()] if room else [],
            "serverTime": now_ms(),
        }

    # ---------------- despacho §5.1 ----------------

    async def dispatch(self, client_id: str, data: str):
        """Ponto único de entrada de mensagens C->S."""
        try:
            message = json.loads(data)
        except json.JSONDecodeError:
            await self.server.send_error(client_id, "invalid_json", "Invalid JSON")
            return
        if not isinstance(message, dict):
            await self.server.send_error(client_id, "invalid_json", "Message must be an object")
            return

        msg_type = message.get("type")
        payload = message.get("payload", message)
        if not isinstance(payload, dict):
            payload = {}

        handler = self.HANDLERS.get(msg_type)
        try:
            if handler is None:
                # §5.3: type desconhecido NÃO derruba a conexão
                await self.server.send_error(client_id, "unknown_type", f"Unknown type: {msg_type}")
                return
            await handler(self, client_id, payload)
        except Exception as e:
            self.server.logger.error(f"Handler error ({msg_type}): {e}")
            await self.server.send_error(client_id, "internal_error", str(e))

    # ============================================================
    # Handlers — legacy copy-migrate (comportamento intacto)
    # ============================================================

    async def handle_hello(self, client_id: str, payload: Dict):
        server, manager = self.server, self.server.manager
        client = server.clients[client_id]

        # Guard legado: cliente já tem entidade — só re-manda welcome
        if client.entity_id and client.entity_id in manager.entities:
            entity = manager.entities[client.entity_id]
            client.room_id = entity.room_id
            await server.send_message(client_id, "welcome", self.build_welcome(entity, manager))
            return

        # client.hello §5.1: name + characterKey (fallbacks legado: token)
        name = payload.get("name") or f"Player {client_id[:4]}"
        character_key = payload.get("characterKey") or "avatar_player"
        entity_id = f"player_{client_id[:8]}"
        entity = manager.spawn_player(entity_id, name, character_key)

        client.entity_id = entity_id
        client.room_id = entity.room_id
        await server.send_message(client_id, "welcome", self.build_welcome(entity, manager))
        await server.broadcast_to_room(entity.room_id, "entity.spawn", {"entity": entity.to_dict()},
                                       exclude=client_id)
        server.logger.info(f"Player spawned: {entity_id} at ({entity.col},{entity.row}) in {entity.room_id}")

    async def handle_move_request(self, client_id: str, payload: Dict):
        """move.request (§3.2) -> move.path (broadcast) | move.rejected (unicast)."""
        server, manager = self.server, self.server.manager
        client = server.clients[client_id]
        if not client.entity_id:
            await server.send_error(client_id, "invalid_move", "Not spawned yet")
            return
        entity = manager.entities.get(client.entity_id)
        room = manager.rooms.get(entity.room_id) if entity else None
        if room is None:
            await server.send_error(client_id, "invalid_move", "Not in a room")
            return

        try:
            goal_col = int(payload.get("targetCol"))
            goal_row = int(payload.get("targetRow"))
        except (TypeError, ValueError):
            await server.send_error(client_id, "invalid_move", "Missing targetCol/targetRow")
            return

        path, reason = room.request_move(entity.id, goal_col, goal_row)
        if path is None:
            # unicast §5.2: move.rejected com reason
            await server.send_message(client_id, "move.rejected", {
                "entityId": entity.id,
                "targetCol": goal_col, "targetRow": goal_row,
                "reason": reason,
            })
            return

        # BLUEPRINT-P1 §7 (D6): NPC em conversa que recebe move externo —
        # o pedido é ACEITO e EXECUTADO, e isso ENCERRA a conversa
        # (despedida curta + left), nunca bloqueia o movimento.
        conv_mgr = getattr(server, "conversation_mgr", None)
        if conv_mgr is not None and entity.type == "npc":
            conv_mgr.on_npc_moved_externally(entity.id)

        # broadcast §5.2: move.path — path completo [[col,row],...]
        await server.broadcast_to_room(entity.room_id, "move.path", {
            "entityId": entity.id,
            "path": [[c, r] for (c, r) in path],
            "startedAt": now_ms(),
            "moveTimeMs": MOVE_TIME_MS,
        })

    async def handle_chat_message(self, client_id: str, payload: Dict):
        """chat.message — copy-migrate intacto."""
        server = self.server
        client = server.clients[client_id]
        if not client.room_id:
            return
        content = payload.get("content", "")
        if not content or len(content) > 500:
            return
        entity = server.manager.entities.get(client.entity_id)
        sender_name = entity.meta.get("name", "Unknown") if entity else "Unknown"
        chat_payload = {
            "msg_id": str(uuid.uuid4()),
            "room_id": client.room_id,
            "sender_id": client.entity_id,
            "sender_name": sender_name,
            "from": client.entity_id,
            "fromName": sender_name,
            "content": content,
            "timestamp": now_ms(),
            "ts": now_ms(),
        }
        await server.broadcast_to_room(client.room_id, "chat.message", chat_payload)

    async def handle_meeting_invite(self, client_id: str, payload: Dict):
        """meeting.invite — copy-migrate intacto (forward ao supervisor)."""
        try:
            await self.server.supervisor_call("task.create", {
                "title": f"Meeting: {payload.get('topic', 'Meeting')}",
                "description": f"Meeting organized by {client_id}",
                "assignee": "devops",
                "priority": 5,
                "dependencies": [],
                "metadata": {
                    "type": "meeting",
                    "room_id": payload.get("room_id"),
                    "participants": payload.get("participants", []),
                    "organizer": client_id,
                },
            })
        except Exception as e:
            self.server.logger.error(f"Meeting invite failed: {e}")

    async def handle_meeting_join(self, client_id: str, payload: Dict):
        pass  # copy-migrate intacto (TODO legado)

    async def handle_meeting_leave(self, client_id: str, payload: Dict):
        pass  # copy-migrate intacto (TODO legado)

    async def handle_npc_dialogue(self, client_id: str, payload: Dict):
        """npc.dialogue.request — copy-migrate intacto (via Memory Substrate)."""
        server = self.server
        npc_id = payload.get("npc_id") or payload.get("npcId")
        user_text = payload.get("user_text") or payload.get("userText")
        context = payload.get("context", {})

        if not npc_id:
            await server.send_error(client_id, "invalid_request", "Missing npc_id")
            return

        # Protocolo congelado §5.1: payload = {npcId} apenas.
        # user_text é opcional — ausente = saudação padrão.
        if not user_text:
            user_text = "Olá!"

        # Lazy wake: garante o Memory Substrate de pé antes de chamar
        # (start_stack.sh padrão não o sobe mais — economia de ~1GB RAM).
        if not await ensure_memory_substrate(server.logger):
            await server.send_error(
                client_id, "memory_substrate_unavailable",
                "Serviço de memória indisponível — tente novamente em instantes",
            )
            return

        try:
            async with server.memory_session.post(
                f"{MEMORY_SUBSTRATE_URL}/dialogue",
                json={"npc_id": npc_id, "user_text": user_text, "context": context},
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    await self._execute_dialogue_actions(npc_id, result.get("actions", []))
                    dialogue_payload = {
                        "npc_id": npc_id,
                        "npcId": npc_id,
                        "text": result.get("text", ""),
                        "emotion": result.get("emotion", "neutral"),
                        "actions": result.get("actions", []),
                    }
                    await server.broadcast_to_room(
                        server.clients[client_id].room_id,
                        "npc.dialogue.response",
                        dialogue_payload,
                    )
        except Exception as e:
            server.logger.error(f"NPC dialogue error: {e}")
            await server.send_error(client_id, "dialogue_failed", str(e))

    async def _execute_dialogue_actions(self, npc_id: str, actions):
        """Copy-migrate intacto."""
        server, manager = self.server, self.server.manager
        for action in actions:
            action_type = action.get("type")
            if action_type == "move":
                target = action.get("target")
                npc = manager.entities.get(npc_id)
                room = manager.rooms.get(npc.room_id) if npc else None
                if room and target:
                    room.move_entity(npc_id, target["x"], target["y"])
            elif action_type == "spawn_artifact":
                pass
            elif action_type == "schedule_meeting":
                pass
            elif action_type == "change_behavior":
                if npc_id in manager.entities:
                    manager.entities[npc_id].meta["status"] = action.get("behavior", "idle")

    async def handle_npc_dialogue_action(self, client_id: str, payload: Dict):
        """npc.dialogue.action — copy-migrate intacto."""
        server, manager = self.server, self.server.manager
        npc_id = payload.get("npc_id")
        action = payload.get("action")
        params = payload.get("params", {})
        if not npc_id or not action:
            await server.send_error(client_id, "invalid_action", "Missing npc_id or action")
            return
        if npc_id in manager.entities:
            if action == "change_behavior":
                manager.entities[npc_id].meta["status"] = params.get("behavior", "idle")
                await server.broadcast_to_room(
                    server.clients[client_id].room_id,
                    "npc.action",
                    {"npc_id": npc_id, "action": action, "params": params},
                )
            elif action == "move" and "target" in params:
                npc = manager.entities[npc_id]
                room = manager.rooms.get(npc.room_id)
                if room:
                    room.move_entity(npc_id, params["target"]["x"], params["target"]["y"])

    async def handle_world_sync_request(self, client_id: str, payload: Dict):
        """world.sync.request (reconexão) -> world.sync §5.2."""
        server = self.server
        client = server.clients[client_id]
        room_id = client.room_id or "reception"
        await server.send_message(client_id, "world.sync", self.build_world_sync(server.manager, room_id))

    async def handle_ping(self, client_id: str, payload: Dict):
        await self.server.send_message(client_id, "pong", {"serverTime": now_ms()})

    # ---------------- tabela de despacho §5.1 ----------------
    HANDLERS = {
        "client.hello": handle_hello,
        "move.request": handle_move_request,
        "chat.message": handle_chat_message,
        "meeting.invite": handle_meeting_invite,
        "meeting.join": handle_meeting_join,
        "meeting.leave": handle_meeting_leave,
        "npc.dialogue.request": handle_npc_dialogue,
        "npc.dialogue.action": handle_npc_dialogue_action,
        "world.sync.request": handle_world_sync_request,
        "ping": handle_ping,
    }
