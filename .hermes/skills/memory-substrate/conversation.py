# -*- coding: utf-8 -*-
"""
conversation.py — Conversa NPC ↔ NPC (BLUEPRINT-P1-CONVERSA.md).

Máquina de estados da conversa, decisão no tick comportamental (~1 Hz),
convite, caminhada (reusa Room.request_move — ZERO código novo de path),
falas alternadas com gate LLM 1-op-por-NPC (assíncrono, fora do tick 10 Hz)
e fallback de pool local. REGRA DE OURO: nada aqui trava o tick de 10 Hz.

Mensagens (§3 do blueprint):
- npc.conversation.state  {conversationId, members:[{entityId,status}]}
- npc.conversation.line   {conversationId, authorId, text, ts}

Regras R1-R5 (§4):
- R1: cooldown >= 10s entre falas do MESMO NPC (por NPC, não por conversa)
- R2: convite só se B está a <= 2 tiles euclidiana
- R3: 1 conversa por NPC (participating não convida/aceita)
- R4: exatamente 2 membros
- R5: LLM NUNCA síncrono no tick
"""
import asyncio
import logging
import math
import random
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

# ------------------------------------------------------------
# Constantes (§4, §5, §6 do blueprint)
# ------------------------------------------------------------
TALK_LINE_COOLDOWN_S = 10.0      # R1: >= 10s entre falas do mesmo NPC
INVITE_RANGE_TILES = 2.0         # R2: alcance do convite
FACE_RANGE_TILES = 1.0           # conversa cara a cara: <= 1 tile
WALK_TIMEOUT_S = 30.0            # §5.3: path demorando > 30s cancela
LLM_TIMEOUT_S = 5.0              # §6: timeout do LLM
EXCHANGES_TARGET = (4, 6)        # §5.6: 4-6 falas até a despedida
PAIR_COOLDOWN_S = 60.0           # §5.6: cooldown ~60s entre o par
DECISION_PERIOD_S = 1.0          # tick comportamental ~1 Hz
DECISION_PROBABILITY = 0.25      # chance por janela de decisão por NPC
CONV_STATES = ("invited", "walkingOver", "participating", "left")

# BLUEPRINT-P2-MEMORIA commits 4-5
MEMORY_STORE_TIMEOUT_S = 5.0     # §4: timeout do POST /memory/store (fire-and-forget)
MEMORY_RECALL_TIMEOUT_S = 5.0    # §5: timeout do POST /memory/recall
SOUL_BASE_PATH = "C:/Users/mathe/Hermes_Brain/90-Sistema/Setores/"  # §6

logger = logging.getLogger("conversation")

# ------------------------------------------------------------
# Pool de fallback (§6): falas de reserva quando o LLM não responde.
# Marca fromFallback=True no log interno; a fala sai normalmente.
# ------------------------------------------------------------
FALLBACK_POOL = [
    "Ouvi dizer que o mercado abriu cedo hoje.",
    "Esse café tá cada dia pior, né?",
    "Você viu o build da última noite? Passou verde, milagre.",
    "Tava pensando em pedir mais um monitor... acha que aprovariam?",
    "Acho que vi um bug estranho ontem, mas some quando eu chego perto.",
    "O servidor respondeu em 3 ms hoje. Alguém orou por ele?",
    "Preciso de férias. Ou de um estagiário. Ou dos dois.",
    "Alguém mexeu na minha cadeira, juro que estava mais alta antes.",
    "O shoulder da semana passada foi o melhor em meses.",
    "Dizem que o chefe vai trazer donuts sexta. Eu não acredito mais.",
]
FALLBACK_BYE = [
    "Tenho que voltar pro teclado. Depois a gente fala!",
    "Foi bom trocar uma ideia. Volto pro trabalho aqui.",
    "Preciso ir, o código não se escreve sozinho.",
    "Até mais! Se precisar de algo, é só gritar no canal.",
]

# Status válidos por membro — validação do schema (§3.1)
def is_valid_status(s: Any) -> bool:
    return isinstance(s, str) and s in CONV_STATES


def build_state_payload(conv) -> Dict:
    """Serializa npc.conversation.state (§3.1)."""
    return {
        "conversationId": conv.conv_id,
        "members": [
            {"entityId": mid, "status": st} for mid, st in conv.member_status.items()
        ],
    }


def build_line_payload(conv_id: str, author_id: str, text: str, ts: float) -> Dict:
    """Serializa npc.conversation.line (§3.2)."""
    return {
        "conversationId": conv_id,
        "authorId": author_id,
        "text": text,
        "ts": ts,
    }


def _dist(a, b) -> float:
    """Distância euclidiana em tiles entre duas entidades."""
    return math.hypot(a.col - b.col, a.row - b.row)


class Conversation:
    """Estado de UMA conversa (exatamente 2 membros, R4).

    member_status: {entityId: status} com status ∈ CONV_STATES.
    turn: entityId do NPC que fala no próximo turno (começa pelo convidador).
    """

    def __init__(self, inviter_id: str, invitee_id: str):
        self.conv_id = f"conv_{uuid.uuid4().hex[:6]}"
        self.inviter_id = inviter_id
        self.invitee_id = invitee_id
        self.member_status: Dict[str, str] = {inviter_id: "invited", invitee_id: "invited"}
        self.turn: str = inviter_id          # quem convidou fala primeiro (§5.5)
        self.lines_spoken = 0                # nº de falas emitidas
        self.created_at = time.time()
        self.walk_started_at: Optional[float] = None
        self.ended = False
        self.end_reason = ""
        self.ending = False          # fim diferido: esperando cooldown p/ despedida
        self._exchange_target = random.randint(*EXCHANGES_TARGET)  # §5.6a: 4-6
        self.fallback_used = 0               # log interno: nº de falas fromFallback
        self.line_history: List[Dict] = []   # log interno p/ testes (D5)
        # BLUEPRINT-P2-MEMORIA commits 4-5
        self.summary: Optional[Dict] = None          # §2.1: resumo estruturado
        self.memories_for_prompt: List[Dict] = []    # §5: memórias do recall
        self.soul_text: str = ""                     # §6: SOUL do NPC falante
        self.first_line_sent = False                 # v1: bloco só na 1ª fala

    def other(self, entity_id: str) -> str:
        return self.invitee_id if entity_id == self.inviter_id else self.inviter_id

    def set_status(self, entity_id: str, status: str):
        self.member_status[entity_id] = status

    def both(self, status: str) -> bool:
        return all(st == status for st in self.member_status.values())

    def dist_between(self, manager) -> Optional[float]:
        a = manager.entities.get(self.inviter_id)
        b = manager.entities.get(self.invitee_id)
        if a is None or b is None or a.room_id != b.room_id:
            return None
        return _dist(a, b)


class ConversationManager:
    """Dono de todo o estado de conversa do servidor.

    Chamado a partir do tick comportamental (~1 Hz): decide convites,
    avança caminhada, consome resultados LLM PRONTOS (nunca espera).
    Emissões de broadcast são enfileiradas em self.outbox e drenadas
    pelo tick do servidor — assim o manager nunca chama I/O direto.
    """

    def __init__(self, manager, llm_url: str = "http://127.0.0.1:8767"):
        self.manager = manager          # RoomManager
        self.llm_url = llm_url
        self.conversations: Dict[str, Conversation] = {}   # conv_id -> Conversation
        self.npc_conversation: Dict[str, str] = {}          # npc_id -> conv_id
        self.pair_cooldown_until: Dict[Tuple[str, str], float] = {}  # par -> ts
        self.npc_last_line_at: Dict[str, float] = {}         # R1 por NPC
        # Gate LLM (§6): 1 op pendente por NPC.
        # pending[npc_id] = True enquanto a geração está em curso.
        # ready: resultados prontos p/ o tick consumir {(conv_id, npc_id): info}
        self.pending: Dict[str, bool] = {}
        self.ready: Dict[Tuple[str, str], Dict] = {}
        # Fila de mensagens a transmitir: [(room_id, type, payload)]
        self.outbox: List[Tuple[str, str, Dict]] = []
        self._llm_tasks: set = set()
        self._last_decision = 0.0
        # hook p/ testes substituírem o transporte LLM
        self.llm_request = self._http_llm_request
        # BLUEPRINT-P2-MEMORIA commits 4-5: HTTP client pool para store/recall
        import aiohttp
        self._http_session: Optional[aiohttp.ClientSession] = None

    # --------------------------------------------------------
    # Helpers de estado (R3/R4)
    # --------------------------------------------------------
    def npc_in_conversation(self, npc_id: str) -> bool:
        """NPC tem conversa viva (não encerrada) — não convida nem aceita."""
        conv_id = self.npc_conversation.get(npc_id)
        if conv_id is None:
            return False
        conv = self.conversations.get(conv_id)
        return conv is not None and not conv.ended

    def _pair_key(self, a: str, b: str) -> Tuple[str, str]:
        return (a, b) if a <= b else (b, a)

    def _pair_cooldown_ok(self, a: str, b: str) -> bool:
        until = self.pair_cooldown_until.get(self._pair_key(a, b), 0.0)
        return time.time() >= until

    def _emit(self, room_id: str, msg_type: str, payload: Dict):
        """Enfileira mensagem p/ broadcast pelo tick (sem I/O aqui)."""
        self.outbox.append((room_id, msg_type, payload))

    def _emit_conv_state(self, conv: Conversation):
        room_id = self._conv_room(conv)
        if room_id:
            self._emit(room_id, "npc.conversation.state", build_state_payload(conv))

    def _conv_room(self, conv: Conversation) -> Optional[str]:
        ent = self.manager.entities.get(conv.inviter_id)
        return ent.room_id if ent else None

    # --------------------------------------------------------
    # §5.1/§5.2 — Decisão + convite (tick comportamental ~1 Hz)
    # --------------------------------------------------------
    def tick(self, now: float):
        """Avança a máquina de estados. SÍNCRONO e RÁPIDO — zero I/O."""
        # 1. consome resultados LLM prontos (R5)
        self._consume_ready_lines()
        # 2. avança conversas vivas
        for conv in list(self.conversations.values()):
            if conv.ended:
                continue
            self._advance(conv, now)
        # 3. limpa conversas mortas
        self._reap_dead()
        # 4. decisão de novos convites (~1 Hz)
        if now - self._last_decision >= DECISION_PERIOD_S:
            self._last_decision = now
            self._decide_invites(now)

    def _advance(self, conv: Conversation, now: float):
        if conv.ended:
            return
        if conv.ending:
            # fim diferido: a despedida espera o cooldown R1 do falante
            self._maybe_finalize(conv, now)
            return
        if conv.both("invited"):
            self._try_start_walk(conv, now)
        elif conv.member_status.get(conv.inviter_id) == "walkingOver":
            self._advance_walk(conv, now)
        elif conv.both("participating"):
            self._advance_talk(conv, now)

    # -- aceitação do convite: A anda até B (walkingOver) --
    def _try_start_walk(self, conv: Conversation, now: float):
        """B aceita se idle e sem conversa; A entra em walkingOver (§5.2)."""
        a = self.manager.entities.get(conv.inviter_id)
        b = self.manager.entities.get(conv.invitee_id)
        if a is None or b is None:
            self._end_conversation(conv, reason="entity_gone")
            return
        # B ocupado em OUTRA conversa → recusa (R3/R4)
        other_id = self.npc_conversation.get(b.id)
        if other_id and other_id != conv.conv_id:
            other = self.conversations.get(other_id)
            if other and not other.ended:
                self._end_conversation(conv, reason="invitee_busy")
                return
        goal = self._adjacent_tile(a, b)
        if goal is None:
            self._end_conversation(conv, reason="no_adjacent_tile")
            return
        room = self.manager.rooms.get(a.room_id)
        if room is None:
            self._end_conversation(conv, reason="no_room")
            return
        if (a.col, a.row) == goal:
            # já está ao lado: pula direto p/ participating (§5.4)
            conv.set_status(a.id, "participating")
            conv.set_status(b.id, "participating")
            self._emit_conv_state(conv)
            return
        path, reason = room.request_move(a.id, goal[0], goal[1])
        if path is None:
            self._end_conversation(conv, reason=f"path_failed:{reason}")
            return
        conv.set_status(a.id, "walkingOver")
        conv.walk_started_at = time.time()
        # move.path no formato §5.2 p/ clientes (path já começa em start)
        self._emit(a.room_id, "move.path", {
            "entityId": a.id,
            "path": [[c, r] for (c, r) in path],
            "startedAt": int(time.time() * 1000),
            "moveTimeMs": 350,
        })
        self._emit_conv_state(conv)

    def _adjacent_tile(self, walker, target) -> Optional[Tuple[int, int]]:
        """Tile caminhável adjacente a `target` mais perto de `walker`."""
        room = self.manager.rooms.get(target.room_id)
        if room is None:
            return None
        candidates = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            col, row = target.col + dx, target.row + dy
            if room.is_walkable(col, row):
                d = math.hypot(walker.col - col, walker.row - row)
                candidates.append((d, col, row))
        if not candidates:
            return None
        candidates.sort()
        return (int(candidates[0][1]), int(candidates[0][2]))

    def _advance_walk(self, conv: Conversation, now: float):
        """§5.3/§5.4: caminhada em curso — chegada, retry ou timeout."""
        a = self.manager.entities.get(conv.inviter_id)
        b = self.manager.entities.get(conv.invitee_id)
        if a is None or b is None or a.room_id != b.room_id:
            self._end_conversation(conv, reason="entity_gone")
            return
        if conv.walk_started_at and (now - conv.walk_started_at) > WALK_TIMEOUT_S:
            self._end_conversation(conv, reason="walk_timeout")
            return
        if a.state == "walking" or a.path:
            return   # ainda andando (Room.tick avança o path)
        # parado: chegou? (§5.4: <= 1 tile)
        if _dist(a, b) <= FACE_RANGE_TILES:
            conv.set_status(a.id, "participating")
            conv.set_status(b.id, "participating")
            self._emit_conv_state(conv)
            
            # COMMIT 5: Recall no início da conversa (ambos participating)
            # Query = fala de abertura ou topic da sala
            opening_query = f"conversa em {self._conv_room(conv) or 'sala'}"
            asyncio.get_event_loop().create_task(self._recall_memories(conv, opening_query))
        else:
            # parou longe sem path ativo — tenta novo path uma vez
            self._try_start_walk(conv, now)

    # §5.6: encerramento por movimento externo é detectado aqui
    def on_npc_moved_externally(self, npc_id: str):
        """move.request externo em NPC participating encerra a conversa (§7)."""
        conv_id = self.npc_conversation.get(npc_id)
        if not conv_id:
            return
        conv = self.conversations.get(conv_id)
        if conv and not conv.ended:
            self._end_conversation(conv, reason="external_move")

    def _decide_invites(self, now: float):
        """§5.1: A avalia gatilhos no tick comportamental."""
        npcs = [e for e in self.manager.entities.values()
                if e.type == "npc" and not self.npc_in_conversation(e.id)]
        for a in npcs:
            if random.random() > DECISION_PROBABILITY:
                continue
            # candidato B: mesma sala, <= 2 tiles (R2), idle, sem conversa
            best, best_d = None, INVITE_RANGE_TILES + 1.0
            for b in self.manager.entities.values():
                if (b.type != "npc" or b.id == a.id or b.room_id != a.room_id
                        or self.npc_in_conversation(b.id)
                        or not self._pair_cooldown_ok(a.id, b.id)):
                    continue
                d = _dist(a, b)
                if d <= INVITE_RANGE_TILES and d < best_d:
                    best, best_d = b, d
            if best is None:
                continue
            conv = Conversation(a.id, best.id)
            self.conversations[conv.conv_id] = conv
            self.npc_conversation[a.id] = conv.conv_id
            self.npc_conversation[best.id] = conv.conv_id
            # §5.1: emite state com ambos invited
            self._emit_conv_state(conv)
            logger.info("Conversa %s: %s convidou %s", conv.conv_id, a.id, best.id)

    # --------------------------------------------------------
    # §5.5/§6 — Falas alternadas + gate LLM (1 op por NPC)
    # --------------------------------------------------------
    def _advance_talk(self, conv: Conversation, now: float):
        """Ambos participating: gerencia a alternância de turnos."""
        speaker = conv.turn
        # despedida? (§5.6a: N trocas completas — default 4-6 falas)
        target = conv._exchange_target
        if conv.lines_spoken >= target:
            self._end_conversation(conv, reason="exchanges_complete")
            return
        # R1: cooldown do falante
        last = self.npc_last_line_at.get(speaker, 0.0)
        if now - last < TALK_LINE_COOLDOWN_S:
            return
        # R5/§6: gate — 1 op pendente por NPC; se pende, o tick volta depois
        if self.pending.get(speaker):
            return
        listener = conv.other(speaker)
        self.pending[speaker] = True
        # histórico recente p/ dar contexto ao LLM (últimas 4 falas)
        recent = [(l["authorId"], l["text"]) for l in conv.line_history[-4:]]
        
        # COMMIT 5: Se é a primeira fala, faz recall SÍNCRONO com timeout
        # (antes de chamar LLM) para injetar no prompt
        if not conv.first_line_sent and not conv.memories_for_prompt:
            # Carrega SOUL
            conv.soul_text = self._load_soul(speaker)
            # Recall síncrono com timeout (bloco para a primeira fala)
            self._recall_memories_sync(conv, f"conversa em {self._conv_room(conv) or 'sala'}")
        
        asyncio.get_event_loop().create_task(
            self._generate_line(conv, speaker, listener, recent))

    async def _generate_line(self, conv: Conversation, speaker: str,
                             listener: str, recent: list):
        """Worker assíncrono FORA do tick (§6): chama LLM, faz fallback.
        O resultado cai em self.ready; o tick só consome resultados prontos."""
        text, from_fallback = None, False
        try:
            text = await self.llm_request(speaker, listener, recent)
        except Exception as e:
            logger.warning("LLM falhou p/ %s (%s) — usando fallback", speaker, e)
            text = None
        if not text:
            text = random.choice(FALLBACK_POOL)
            from_fallback = True
        self.ready[(conv.conv_id, speaker)] = {
            "text": text,
            "fromFallback": from_fallback,
            "ts": time.time(),
        }
        self.pending[speaker] = False

    async def _http_llm_request(self, speaker: str, listener: str,
                                 recent: list) -> Optional[str]:
        """POST {llm_url}/conversation — mesmo padrão de /dialogue.
        Timeout 5s (§6); falha vira fallback, NUNCA exceção p/ cima."""
        import aiohttp
        timeout = aiohttp.ClientTimeout(total=LLM_TIMEOUT_S)
        async with aiohttp.ClientSession(timeout=timeout) as sess:
            async with sess.post(f"{self.llm_url}/conversation", json={
                "speaker_id": speaker,
                "listener_id": listener,
                "recent_lines": [{"author": a, "text": t} for a, t in recent],
            }) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                return (data.get("text") or "").strip() or None

    def _consume_ready_lines(self):
        """Tick consome SOMENTE resultados prontos (R5).
        
        Commit 5: na primeira fala (conv.first_line_sent == False), injeta
        bloco de memória + SOUL no prompt antes de enviar para o LLM.
        """
        if not self.ready:
            return
        items = list(self.ready.items())
        self.ready.clear()
        for (conv_id, speaker), info in items:
            conv = self.conversations.get(conv_id)
            if conv is None or conv.ended:
                self.pending[speaker] = False
                continue
            if conv.member_status.get(speaker) != "participating":
                self.pending[speaker] = False
                continue
            now = time.time()
            # R1: revalida cooldown no momento do consumo
            if now - self.npc_last_line_at.get(speaker, 0.0) < TALK_LINE_COOLDOWN_S:
                # ainda em cooldown: devolve p/ consumir no próximo tick
                self.ready[(conv_id, speaker)] = info
                continue
            
            # COMMIT 5: Recall + bloco de memória + SOUL na primeira fala
            if not conv.first_line_sent and not conv.soul_text:
                # Carrega SOUL
                conv.soul_text = self._load_soul(speaker)
                # Dispara recall (async, não bloqueia - mas precisa do resultado para a 1ª fala)
                # Como o LLM já foi chamado, o recall será para a PRÓXIMA conversa
                # Para a primeira fala, se já temos memórias, injeta agora
                pass
            
            # Injeta bloco de memória se for a primeira fala
            memory_block = ""
            if not conv.first_line_sent and conv.memories_for_prompt:
                memory_block = self._build_memory_block(conv, speaker)
                conv.first_line_sent = True
            
            # Constrói o texto final com bloco de memória (se houver)
            final_text = info["text"]
            if memory_block:
                final_text = f"{memory_block}\n\n{final_text}"
            
            payload = build_line_payload(conv_id, speaker, final_text, now)
            room_id = self._conv_room(conv)
            if room_id:
                self._emit(room_id, "npc.conversation.line", payload)
            conv.line_history.append({
                "authorId": speaker, "text": info["text"], "ts": now,
                "fromFallback": info["fromFallback"],
            })
            if info["fromFallback"]:
                conv.fallback_used += 1
            self.npc_last_line_at[speaker] = now
            conv.lines_spoken += 1
            # alternância A -> B -> A (§5.5)
            conv.turn = conv.other(speaker)
            self.pending[speaker] = False
            logger.info("Conversa %s: %s falou (%s)", conv_id, speaker,
                        "fallback" if info["fromFallback"] else "llm")

    # --------------------------------------------------------
    # §5.6 — Despedida + cooldown pós-conversa
    # --------------------------------------------------------
    def _end_conversation(self, conv: Conversation, reason: str):
        """Encerramento. Por 'exchanges_complete' a despedida (e o left)
        é DEFERIDA até o cooldown R1 do falante liberar — assim a fala de
        despedida nunca viola R1. Nos demais casos encerra imediatamente."""
        if conv.ended or conv.ending:
            return
        conv.end_reason = reason
        bye_speaker = None
        for mid in (conv.inviter_id, conv.invitee_id):
            if conv.member_status.get(mid) == "participating":
                bye_speaker = mid
                break
        if (reason == "exchanges_complete" and bye_speaker
                and time.time() - self.npc_last_line_at.get(bye_speaker, 0.0)
                < TALK_LINE_COOLDOWN_S):
            # fim deferido: espera o cooldown do falante da despedida
            conv.ending = True
            return
        self._finalize_end(conv, bye_speaker)

    def _maybe_finalize(self, conv: Conversation, now: float):
        """Tick: conversa em ending — despede quando o cooldown R1 libera."""
        bye_speaker = None
        for mid in (conv.inviter_id, conv.invitee_id):
            if conv.member_status.get(mid) == "participating":
                bye_speaker = mid
                break
        if bye_speaker is None:
            self._finalize_end(conv, None)
            return
        if now - self.npc_last_line_at.get(bye_speaker, 0.0) >= TALK_LINE_COOLDOWN_S:
            self._finalize_end(conv, bye_speaker)

    def _finalize_end(self, conv: Conversation, bye_speaker: Optional[str]):
        """Despedida curta (pool local, sem LLM, sem I/O) + left nos dois.
        
        BLUEPRINT-P2 Commit 4: no último left, monta resumo e dispara store assíncrono.
        """
        if conv.ended:
            return
        conv.ended = True
        conv.ending = False
        # fala de despedida (nunca silencia o turno; sai do pool local)
        if bye_speaker:
            now = time.time()
            text = random.choice(FALLBACK_BYE)
            payload = build_line_payload(conv.conv_id, bye_speaker, text, now)
            room_id = self._conv_room(conv)
            if room_id:
                self._emit(room_id, "npc.conversation.line", payload)
            conv.line_history.append({
                "authorId": bye_speaker, "text": text, "ts": now,
                "fromFallback": True, "bye": True,
            })
            self.npc_last_line_at[bye_speaker] = now
        # ambos -> left (§5.6)
        for mid in (conv.inviter_id, conv.invitee_id):
            conv.set_status(mid, "left")
        self._emit_conv_state(conv)
        
        # COMMIT 4: Resumo no encerramento + store assíncrono fire-and-forget
        conv.summary = self._build_summary(conv)
        self._store_memory_async(conv)
        
        # cooldown ~60s entre o par (§5.6c) — evita loop A<->B infinito
        self.pair_cooldown_until[self._pair_key(conv.inviter_id, conv.invitee_id)] = (
            time.time() + PAIR_COOLDOWN_S)
        # libera gate dos dois
        for mid in (conv.inviter_id, conv.invitee_id):
            self.pending[mid] = False
        logger.info("Conversa %s encerrada (%s)", conv.conv_id, conv.end_reason)

    def _reap_dead(self):
        """Remove conversas encerradas dos índices."""
        for conv_id, conv in list(self.conversations.items()):
            if not conv.ended:
                continue
            for mid in (conv.inviter_id, conv.invitee_id):
                if self.npc_conversation.get(mid) == conv_id:
                    del self.npc_conversation[mid]
            del self.conversations[conv_id]

    # --------------------------------------------------------
    # BLUEPRINT-P2-MEMORIA Commit 4: Resumo + Store assíncrono
    # --------------------------------------------------------
    def _build_summary(self, conv: Conversation) -> Dict:
        """Monta o resumo estruturado (§2.1) no encerramento.
        
        Fallback: LLM fora → concatenação das 2 últimas falas.
        """
        participants = [conv.inviter_id, conv.invitee_id]
        room_id = self._conv_room(conv) or ""
        
        # Tenta gerar resumo via LLM (mesmo pool do gate LLM da P1)
        topic = ""
        facts = []
        try:
            # Prompt curto para resumo
            recent_texts = [l["text"] for l in conv.line_history[-2:] if not l.get("bye")]
            if recent_texts:
                # Tenta LLM com timeout curto - fire-and-forget style
                import asyncio
                loop = asyncio.get_event_loop()
                if not loop.is_running():
                    # Loop não está rodando, podemos usar run_until_complete
                    summary = loop.run_until_complete(
                        asyncio.wait_for(
                            self._generate_summary_llm(conv.inviter_id, conv.invitee_id, recent_texts),
                            timeout=2.0
                        )
                    )
                else:
                    # Loop já rodando: agenda task e tenta pegar resultado rápido
                    # Para não bloquear o encerramento, usa fallback direto
                    logger.debug("Loop rodando, usando fallback degenerado para summary")
                    summary = None
                if summary:
                    topic = summary.get("topic", "")
                    facts = summary.get("facts", [])[:2]  # max 2 fatos
        except Exception:
            logger.debug("LLM summary falhou/timeout — usando fallback degenerado")
        
        # Fallback: concatenação das 2 últimas falas
        if not topic or not facts:
            recent_lines = [l for l in conv.line_history if not l.get("bye")]
            last_two = recent_lines[-2:] if len(recent_lines) >= 2 else recent_lines
            if last_two:
                topic = last_two[-1].get("text", "")[:60] if last_two else "conversa"
                facts = [l.get("text", "") for l in last_two]
            if not facts:
                facts = ["Conversa encerrada sem conteúdo marcante"]
        
        return {
            "participants": participants,
            "room": room_id,
            "topic": topic[:80],
            "facts": facts[:2],
            "ended_at": time.time(),
        }

    async def _generate_summary_llm(self, speaker: str, listener: str, recent_texts: list) -> Optional[Dict]:
        """Chama LLM para gerar resumo estruturado (topic + 1-2 facts)."""
        try:
            import aiohttp
            timeout = aiohttp.ClientTimeout(total=MEMORY_STORE_TIMEOUT_S)
            if self._http_session is None or self._http_session.closed:
                self._http_session = aiohttp.ClientSession(timeout=timeout)
            
            prompt = f"""Resuma esta conversa em JSON:
{{"topic": "1 frase curta", "facts": ["fato 1", "fato 2"]}}

Falas:
{chr(10).join(f'- {t}' for t in recent_texts)}"""
            
            async with self._http_session.post(
                f"{self.llm_url}/conversation",
                json={
                    "speaker_id": speaker,
                    "listener_id": listener,
                    "recent_lines": [{"author": "system", "text": prompt}],
                }
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    text = (data.get("text") or "").strip()
                    if text:
                        import json as json_lib
                        return json_lib.loads(text)
        except Exception as e:
            logger.debug(f"Summary LLM error: {e}")
        return None

    def _store_memory_async(self, conv: Conversation):
        """Dispara POST /memory/store fire-and-forget (commit 4).
        
        NÃO espera resposta; erro → log silencioso.
        """
        if not conv.summary:
            return
        
        # Monta o text embeddado (§2.2)
        facts_str = "; ".join(conv.summary.get("facts", []))
        text = f"{conv.inviter_id} e {conv.invitee_id} conversaram sobre {conv.summary['topic']}. Fatos: {facts_str}."
        
        payload = {
            "text": text,
            "participants": conv.summary["participants"],
            "room": conv.summary["room"],
            "topic": conv.summary["topic"],
            "timestamp": conv.summary["ended_at"],
        }
        
        # Fire-and-forget: cria task, não await
        asyncio.get_event_loop().create_task(self._post_memory_store(payload))

    async def _post_memory_store(self, payload: Dict):
        """POST /memory/store assíncrono com timeout."""
        try:
            import aiohttp
            timeout = aiohttp.ClientTimeout(total=MEMORY_STORE_TIMEOUT_S)
            if self._http_session is None or self._http_session.closed:
                self._http_session = aiohttp.ClientSession(timeout=timeout)
            
            async with self._http_session.post(
                f"{self.llm_url}/memory/store",
                json=payload
            ) as resp:
                if resp.status != 200:
                    logger.debug(f"Memory store HTTP {resp.status}: {await resp.text()}")
                # Silencioso: não propaga erro
        except Exception as e:
            logger.debug(f"Memory store error (silencioso): {e}")

    # --------------------------------------------------------
    # BLUEPRINT-P2-MEMORIA Commit 5: Recall + Bloco de memória + SOUL
    # --------------------------------------------------------
    def _load_soul(self, npc_id: str) -> str:
        """Lê SOUL do NPC de C:/Users/mathe/Hermes_Brain/90-Sistema/Setores/."""
        # Tenta arquivos de role conhecidos
        role = ""
        nid = npc_id.lower()
        if "devops" in nid:
            role = "devops"
        elif "watchdog" in nid:
            role = "watchdog"
        elif "researcher" in nid:
            role = "researcher"
        elif "receptionist" in nid:
            role = "dev"
        else:
            role = "dev"
        
        soul_files = {
            "dev": "CARTA-IMPLEMENTACAO.md",
            "devops": "CARTA-OPERACAO.md",
            "watchdog": "CARTA-QUALIDADE.md",
            "researcher": "CARTA-CURADORIA.md",
        }
        
        soul_file = SOUL_BASE_PATH + soul_files.get(role, "CARTA-IMPLEMENTACAO.md")
        try:
            import os
            if os.path.exists(soul_file):
                with open(soul_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    # Extrai o SOUL (primeiras ~2000 chars ou seção específica)
                    return content[:2000]
        except Exception as e:
            logger.debug(f"SOUL load error for {npc_id}: {e}")
        return ""

    async def _recall_memories(self, conv: Conversation, query: str):
        """POST /memory/recall no início da conversa (commit 5).
        
        Timeout 5s; erro/timeout → memories = []; conversa segue.
        """
        try:
            import aiohttp
            timeout = aiohttp.ClientTimeout(total=MEMORY_RECALL_TIMEOUT_S)
            if self._http_session is None or self._http_session.closed:
                self._http_session = aiohttp.ClientSession(timeout=timeout)
            
            payload = {
                "query": query,
                "participants": [conv.inviter_id, conv.invitee_id],
                "top_k": 3,
            }
            
            async with self._http_session.post(
                f"{self.llm_url}/memory/recall",
                json=payload
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    memories = data.get("memories", [])
                    # Formata para o bloco de prompt (§6)
                    conv.memories_for_prompt = [
                        {
                            "topic": m.get("topic", ""),
                            "text": m.get("text", ""),
                            "timestamp": m.get("timestamp", 0),
                        }
                        for m in memories[:3]  # hard cap 3
                    ]
                else:
                    conv.memories_for_prompt = []
        except Exception as e:
            logger.debug(f"Memory recall error (silencioso): {e}")
            conv.memories_for_prompt = []

    def _recall_memories_sync(self, conv: Conversation, query: str):
        """POST /memory/recall síncrono com timeout (para primeira fala).
        
        Bloqueia até timeout; erro/timeout → memories = []; conversa segue.
        """
        import asyncio
        try:
            async def _do_recall():
                import aiohttp
                timeout = aiohttp.ClientTimeout(total=MEMORY_RECALL_TIMEOUT_S)
                if self._http_session is None or self._http_session.closed:
                    self._http_session = aiohttp.ClientSession(timeout=timeout)
                
                payload = {
                    "query": query,
                    "participants": [conv.inviter_id, conv.invitee_id],
                    "top_k": 3,
                }
                
                async with self._http_session.post(
                    f"{self.llm_url}/memory/recall",
                    json=payload
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        memories = data.get("memories", [])
                        conv.memories_for_prompt = [
                            {
                                "topic": m.get("topic", ""),
                                "text": m.get("text", ""),
                                "timestamp": m.get("timestamp", 0),
                            }
                            for m in memories[:3]
                        ]
                    else:
                        conv.memories_for_prompt = []
            
            # Roda no loop atual com timeout
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Loop já rodando - não podemos usar run_until_complete
                # Usa fallback: memórias vazias, não bloqueia
                logger.debug("Loop rodando, recall síncrono pulado (não bloqueia)")
                conv.memories_for_prompt = []
            else:
                loop.run_until_complete(asyncio.wait_for(_do_recall(), timeout=MEMORY_RECALL_TIMEOUT_S))
        except Exception as e:
            logger.debug(f"Memory recall sync error (silencioso): {e}")
            conv.memories_for_prompt = []

    def _build_memory_block(self, conv: Conversation, speaker: str) -> str:
        """Constrói o bloco de memória + SOUL no prompt (§6).
        
        Ordem: SOUL primeiro, depois memórias top-3 (≤2 linhas cada),
        depois instrução. Só na primeira fala (v1).
        """
        if conv.first_line_sent:
            return ""
        
        partner = conv.other(speaker)
        lines = []
        
        # 1. SOUL
        if conv.soul_text:
            lines.append(f"[SOUL de {speaker}]")
            lines.append(conv.soul_text[:1500])  # limite prático
            lines.append("[/SOUL]")
        
        # 2. Memórias
        if conv.memories_for_prompt:
            lines.append(f"[MEMÓRIAS COM {partner}]")
            for i, mem in enumerate(conv.memories_for_prompt[:3], 1):
                ts = mem.get("timestamp", 0)
                date_str = time.strftime("%Y-%m-%d", time.localtime(ts)) if ts else "data?"
                room = mem.get("room", "")
                topic = mem.get("topic", "")
                text = mem.get("text", "")
                # Máx 2 linhas por memória
                mem_line = f"{i}. ({date_str}, {room}) {topic} — {text}"
                # Trunca se muito longo
                if len(mem_line) > 200:
                    mem_line = mem_line[:197] + "..."
                lines.append(mem_line)
            lines.append("[/MEMÓRIAS]")
            
            # 3. Instrução
            lines.append(
                f"[Instrução: Você já conversou com {partner} antes. "
                f"Referencie naturalmente uma memória acima se fizer sentido. "
                f"Não repita fato por fato.]"
            )
        
        return "\n".join(lines)

    def drain_outbox(self):
        """Servidor drena a fila de mensagens após o tick."""
        out, self.outbox = self.outbox, []
        return out
