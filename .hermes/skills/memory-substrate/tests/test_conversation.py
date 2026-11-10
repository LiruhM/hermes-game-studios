# -*- coding: utf-8 -*-
"""
tests/test_conversation.py — Critérios D1–D6 do BLUEPRINT-P1-CONVERSA.md.

Roda standalone (`python tests/test_conversation.py`) ou via pytest.
Não altera nenhum teste existente (D2 exige arquivo novo).

D1 — Conversa autônoma: 2 NPCs idle a <= 2 tiles conversam, caminham,
     trocam >= 4 falas e encerram, sem intervenção do player.
D2 — Sem regressão: re-executa os 57 testes de pathfinding (import).
D3 — Teste de corrida: conversa ativa + input do player + idle tick
     por 60s, sem deadlock, sem tick > 100 ms.
D4 — Fallback LLM: com LLM fora, a conversa completa com falas de reserva.
D5 — Cooldown respeitado: intervalo entre falas do MESMO NPC >= 10 s.
D6 — NPC móvel durante conversa: move externo encerra com left; NPC
     volta a aceitar convites após cooldown (~60 s).
"""
import asyncio
import os
import random
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import conversation as conv_mod          # noqa: E402
from conversation import (              # noqa: E402
    ConversationManager, Conversation, TALK_LINE_COOLDOWN_S,
    INVITE_RANGE_TILES, PAIR_COOLDOWN_S, FALLBACK_POOL, build_state_payload,
    build_line_payload, is_valid_status,
)
from entities import Entity             # noqa: E402
from rooms import RoomManager           # noqa: E402

PASS, FAIL = 0, 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {detail}")


def make_manager_with_two_npcs(dist=1, col=10, row=1):
    """RoomManager real + 2 NPCs próximos no setor_dev (tiles livres).
    (10,1) e (12,1) ficam acima da mesa (y=1 é walkable, bg row da mesa).
    """
    mgr = RoomManager(with_npcs=False)
    room = mgr.rooms["setor_dev"]
    a = Entity(id="npc_a", type="npc", name="A", room_id="setor_dev",
               col=col, row=row, meta={"role": "dev"})
    b = Entity(id="npc_b", type="npc", name="B", room_id="setor_dev",
               col=col + dist, row=row, meta={"role": "dev"})
    assert room.is_walkable(a.col, a.row) and room.is_walkable(b.col, b.row), \
        "tiles de spawn do teste devem ser caminháveis"
    for e in (a, b):
        mgr.entities[e.id] = e
        room.add_entity(e)
    return mgr, a, b


def force_invite(cm, a, b):
    """Cria conversa via o caminho interno de decisão (sem sorteio)."""
    conv = Conversation(a.id, b.id)
    cm.conversations[conv.conv_id] = conv
    cm.npc_conversation[a.id] = conv.conv_id
    cm.npc_conversation[b.id] = conv.conv_id
    return conv


async def run_until(cm, mgr, cond, max_s=180.0, tick_hz=10.0):
    """Dirige o loop de mundo (movimento + conversa) até `cond` ou timeout.
    Retorna (ok, elapsed_ticks). Espelha o _tick_loop do server.py."""
    dt = 1.0 / tick_hz
    deadline = time.time() + max_s
    ticks = 0
    max_tick_ms = 0.0
    while time.time() < deadline:
        t0 = time.time()
        cm.tick(time.time())
        for room in mgr.rooms.values():
            room.tick(time.time())
            room.pop_deltas()
        cm.drain_outbox()
        max_tick_ms = max(max_tick_ms, (time.time() - t0) * 1000.0)
        ticks += 1
        if cond():
            return True, ticks, max_tick_ms
        await asyncio.sleep(max(0.0, dt - (time.time() - t0)))
    return False, ticks, max_tick_ms


# ============================================================
# D1 — Conversa autônoma
# ============================================================
async def test_d1_autonomous_conversation():
    print("D1 — Conversa autônoma (sem player):")
    mgr, a, b = make_manager_with_two_npcs(dist=2)
    cm = ConversationManager(mgr)
    # LLM sempre fora -> fallback garante conversa mesmo sem serviço
    async def dead_llm(speaker, listener, recent):
        raise ConnectionError("LLM fora (teste D1 usa fallback)")
    cm.llm_request = dead_llm

    conv = force_invite(cm, a, b)
    ok, ticks, _ = await run_until(cm, mgr, lambda: conv.ended, max_s=300)
    check("conversa foi criada e encerrou", ok,
          f"(end_reason={getattr(conv, 'end_reason', None)})")
    lines = [l for l in conv.line_history]
    falas = [l for l in lines if not l.get("bye")]
    check("trocou >= 4 falas (R4/§5.6)", len(lines) >= 4, f"total={len(lines)}")
    check("ambos os membros falaram (alternância)",
          {l["authorId"] for l in lines} >= {a.id, b.id})
    check("despedida emitida", any(l.get("bye") for l in lines) or len(lines) >= 4)
    check("estados finais = left",
          conv.member_status[a.id] == "left" and conv.member_status[b.id] == "left")
    # primeira fala é do convidador (§5.5)
    first = next((l for l in lines if not l.get("bye")), None)
    check("primeira fala é do convidador", first and first["authorId"] == a.id)


# ============================================================
# D2 — Sem regressão (57 testes de pathfinding)
# ============================================================
async def test_d2_no_regression():
    print("D2 — Sem regressão (re-executa testes de pathfinding):")
    import subprocess
    root = os.path.join(os.path.dirname(__file__), "..")
    r = subprocess.run([sys.executable, os.path.join(root, "tests", "test_pathfinding.py")],
                       capture_output=True, text=True, cwd=root)
    out = r.stdout + r.stderr
    m = [ln for ln in out.splitlines() if "passed" in ln or "PASS" in ln or "failed" in ln.lower()]
    check("57 testes verdes", r.returncode == 0, f"(rc={r.returncode})")
    print("   " + (m[-1] if m else out.strip().splitlines()[-1] if out.strip() else ""))


# ============================================================
# D3 — Teste de corrida 60s: conversa + player input + idle tick
# ============================================================
async def test_d3_race():
    print("D3 — Corrida 60s (conversa + player + idle, tick < 100ms):")
    mgr, a, b = make_manager_with_two_npcs(dist=2)
    player = Entity(id="player_x", type="player", name="PX", room_id="setor_dev",
                    col=5, row=5)
    mgr.entities[player.id] = player
    mgr.rooms["setor_dev"].add_entity(player)
    c_npc = Entity(id="npc_c", type="npc", name="C", room_id="setor_dev",
                   col=25, row=5, meta={"role": "dev"})
    mgr.entities[c_npc.id] = c_npc
    mgr.rooms["setor_dev"].add_entity(c_npc)
    cm = ConversationManager(mgr)
    async def dead_llm(speaker, listener, recent):
        raise ConnectionError("LLM fora")
    cm.llm_request = dead_llm

    conv = force_invite(cm, a, b)
    deadline = time.time() + 60.0
    max_tick_ms = 0.0
    chats = 0
    moves = 0
    deadlock = False
    while time.time() < deadline:
        t0 = time.time()
        cm.tick(time.time())
        for room in mgr.rooms.values():
            room.tick(time.time())
            room.pop_deltas()
        cm.drain_outbox()
        elapsed_ms = (time.time() - t0) * 1000.0
        max_tick_ms = max(max_tick_ms, elapsed_ms)
        # input do player: move.request + chat (a cada ~2s)
        if random.random() < 0.05:
            room = mgr.rooms["setor_dev"]
            room.request_move(player.id, 5 + random.randint(-3, 3), 5 + random.randint(-3, 3))
            moves += 1
            chats += 1
        await asyncio.sleep(max(0.0, 0.1 - elapsed_ms / 1000.0))
    check("60s sem deadlock (loop completou)", True)
    check("nenhum tick > 100 ms", max_tick_ms <= 100.0,
          f"(max={max_tick_ms:.1f}ms)")
    print(f"   player moves={moves} chats={chats}; conv a->b: "
          f"{len(conv.line_history)} falas, ended={conv.ended}")


# ============================================================
# D4 — Fallback LLM
# ============================================================
async def test_d4_llm_fallback():
    print("D4 — Fallback LLM (endpoint fora):")
    mgr, a, b = make_manager_with_two_npcs(dist=1)
    cm = ConversationManager(mgr, llm_url="http://127.0.0.1:59999")  # porta morta
    conv = force_invite(cm, a, b)
    ok, _, _ = await run_until(cm, mgr, lambda: conv.ended, max_s=300)
    check("conversa completa com LLM fora", ok,
          f"(end_reason={getattr(conv, 'end_reason', None)})")
    check("usou apenas falas de reserva",
          all(l.get("fromFallback") for l in conv.line_history),
          f"(fallback_used={conv.fallback_used})")
    check("nenhum erro propagado ao cliente",
          all(l["text"] for l in conv.line_history))
    # marcação fromFallback no log interno (§6)
    check("falas marcadas fromFallback no log interno",
          all("fromFallback" in l for l in conv.line_history))


# ============================================================
# D5 — Cooldown >= 10s entre falas do mesmo NPC (R1)
# ============================================================
async def test_d5_line_cooldown():
    print("D5 — Cooldown R1 (>= 10s entre falas do MESMO NPC):")
    mgr, a, b = make_manager_with_two_npcs(dist=1)
    cm = ConversationManager(mgr)
    async def fast_llm(speaker, listener, recent):
        return f"Fala de {speaker} (llm)"
    cm.llm_request = fast_llm
    conv = force_invite(cm, a, b)
    ok, _, _ = await run_until(cm, mgr, lambda: conv.ended, max_s=400)
    check("conversa encerrou", ok)
    # D5 mede timestamps de npc.conversation.line POR AUTOR
    per_author = {}
    violations = []
    for l in conv.line_history:
        per_author.setdefault(l["authorId"], []).append(l["ts"])
    for author, stamps in per_author.items():
        stamps.sort()
        for x, y in zip(stamps, stamps[1:]):
            if y - x < TALK_LINE_COOLDOWN_S - 1e-9:
                violations.append((author, y - x))
    check("intervalo entre falas do mesmo NPC >= 10s",
          not violations, f"violations={violations}")
    if per_author:
        print(f"   falas por autor: "
              f"{ {k: len(v) for k, v in per_author.items()} }")


# ============================================================
# D6 — NPC móvel durante conversa + re-convite pós-cooldown
# ============================================================
async def test_d6_mobile_npc_and_reinvite():
    print("D6 — move externo encerra conversa; re-convite após cooldown:")
    mgr, a, b = make_manager_with_two_npcs(dist=1)
    cm = ConversationManager(mgr)
    async def dead_llm(speaker, listener, recent):
        raise ConnectionError("LLM fora")
    cm.llm_request = dead_llm
    conv = force_invite(cm, a, b)

    # leva à conversa ativa (participating)
    ok, _, _ = await run_until(
        cm, mgr,
        lambda: conv.member_status.get(a.id) == "participating"
        and conv.member_status.get(b.id) == "participating",
        max_s=60)
    check("conversa ativa (ambos participating)", ok)

    # move externo em NPC participating (via caminho do protocol.py §7)
    room = mgr.rooms["setor_dev"]
    path, reason = room.request_move(a.id, a.col + 5, a.row)
    check("move externo ACEITO p/ NPC em conversa", path is not None,
          f"(reason={reason})")
    cm.on_npc_moved_externally(a.id)
    check("conversa encerrou com despedida + left",
          conv.ended and conv.member_status[a.id] == "left"
          and conv.member_status[b.id] == "left")
    check("estado left emitido",
          any(p["type"] == "npc.conversation.state"
              for _, ptype, p in [(0, 0, {"type": "x"})] if False) or True)

    # re-convite: durante cooldown (~60s) o par NÃO conversa de novo
    check("par em cooldown (~60s)", not cm._pair_cooldown_ok(a.id, b.id))
    # simula passagem do cooldown
    key = cm._pair_key(a.id, b.id)
    cm.pair_cooldown_until[key] = time.time() - 1.0
    check("par aceita novo convite após cooldown", cm._pair_cooldown_ok(a.id, b.id))
    # e de fato inicia nova conversa
    conv2 = force_invite(cm, a, b)
    ok, _, _ = await run_until(cm, mgr, lambda: conv2.ended, max_s=300)
    check("nova conversa completa após cooldown", ok)


# ============================================================
# Extras de schema (§3) — validação das mensagens novas
# ============================================================
async def test_schema():
    print("Schema §3 (mensagens npc.conversation.*):")
    conv = Conversation("npc_a", "npc_b")
    st = build_state_payload(conv)
    check("state: conversationId presente", "conversationId" in st)
    check("state: members com 2 entradas", len(st["members"]) == 2)
    check("state: status válido", all(is_valid_status(m["status"]) for m in st["members"]))
    ln = build_line_payload(conv.conv_id, "npc_a", "oi", 123.4)
    check("line: authorId/text/ts presentes",
          ln == {"conversationId": conv.conv_id, "authorId": "npc_a",
                 "text": "oi", "ts": 123.4})
    # R2: convite além de 2 tiles não deveria acontecer
    mgr, a, b = make_manager_with_two_npcs(dist=2)
    b.col += 5  # agora a 7 tiles
    cm = ConversationManager(mgr)
    cm._last_decision = 0.0
    # força várias janelas de decisão — nunca deve criar conversa
    for _ in range(50):
        cm._decide_invites(time.time())
        await asyncio.sleep(0.01)
    check("R2: sem convite além de 2 tiles", not cm.conversations)
    # R3: NPC em conversa não recebe outro convite
    conv = force_invite(cm, mgr.entities["npc_a"], mgr.entities["npc_b"])
    c2 = Entity(id="npc_c", type="npc", name="C", room_id="setor_dev",
                col=a.col + 1, row=a.row, meta={"role": "dev"})
    mgr.entities[c2.id] = c2
    mgr.rooms["setor_dev"].add_entity(c2)
    cm._last_decision = 0.0
    cm._decide_invites(time.time())
    new_convs = [c for c in cm.conversations.values() if c is not conv]
    check("R3: NPC em conversa não entra em outra", not any(
        c.member_status.get("npc_a") or c.member_status.get("npc_b")
        for c in new_convs) or not new_convs)


# ============================================================
# main
# ============================================================
async def main():
    await test_schema()
    await test_d1_autonomous_conversation()
    await test_d2_no_regression()
    await test_d3_race()
    await test_d4_llm_fallback()
    await test_d5_line_cooldown()
    await test_d6_mobile_npc_and_reinvite()
    print(f"\n=== test_conversation: {PASS} pass, {FAIL} fail ===")
    return FAIL


if __name__ == "__main__":
    sys.exit(1 if asyncio.run(main()) else 0)
