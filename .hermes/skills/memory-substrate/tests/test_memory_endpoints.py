# -*- coding: utf-8 -*-
"""
tests/test_memory_endpoints.py — Commits 1-3 do BLUEPRINT-P2-MEMORIA.md.

Arquivo NOVO: não toca em nenhum dos 57 testes existentes
(test_pathfinding, test_conversation, test_memory_substrate, test_client).

C1/M4 — Cache de embedding por hash: texto idêntico 2x -> 2ª vem do cache
        (cached=true, zero inferência nova) e persiste entre instâncias.
C2     — POST /memory/store: grava memória de conversa (§3.1).
C3/M2  — POST /memory/recall: recall por similaridade com filtro
        participants, top_k default 3, hard cap 3.
C3/M3  — Zero vazamento: par A (anna<->boris) NUNCA recebe memória do
        par B (carlos<->dora); recall sem match -> lista vazia.

Embedding: stub determinístico (hash -> vetor 384 normalizado) para rodar
offline e leve no Ryzen 5700U/12GB — o código real usa o EmbeddingEngine
(all-MiniLM-L6-v2); o stub só substitui o modelo interno dele.
"""
import os
import sys
import json
import time
import tempfile
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.chdir(os.path.join(os.path.dirname(__file__), ".."))

from memory_substrate.indexing.embedding_engine import (  # noqa: E402
    EmbeddingEngine, EmbeddingConfig,
)

PASS, FAIL = 0, 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {detail}")


class StubModel:
    """Modelo determinístico: vetor unitário derivado do sha256 do texto.

    Textos que compartilham palavras compartilham similaridade (vetores
    somados por palavra-chave) para o recall ter ranking sensato.
    """
    DIM = 384

    def __init__(self):
        self.encode_calls = 0

    def _vec_for(self, text):
        v = np.zeros(self.DIM, dtype=np.float32)
        for word in set(text.lower().split()):
            h = int.from_bytes(
                __import__("hashlib").sha256(word.encode()).digest()[:8],
                "big")
            v[h % self.DIM] += 1.0
            v[(h >> 32) % self.DIM] += 0.5
        n = np.linalg.norm(v)
        return v / n if n > 0 else v

    def encode(self, texts, **kwargs):
        self.encode_calls += 1
        return np.stack([self._vec_for(t) for t in texts])


def make_engine(tmpdir):
    """EmbeddingEngine REAL com modelo interno trocado por stub determinístico."""
    cfg = EmbeddingConfig(
        embedding_cache_path=os.path.join(tmpdir, "embedding_cache.json"),
        cache_dir=os.path.join(tmpdir, "model_cache"),
    )
    eng = EmbeddingEngine(cfg)
    eng._model = StubModel()  # pré-carregado: nunca toca sentence-transformers
    return eng


# ============================================================
# C1/M4 — Cache de embedding por hash
# ============================================================

def test_cache_hit():
    print("C1/M4 — cache de embedding por hash (texto identico 2x)")
    with tempfile.TemporaryDirectory() as tmp:
        eng = make_engine(tmp)
        text = "Anna e Boris conversaram sobre o mercado abriu cedo."

        emb1, cached1 = eng.get_embedding(text)
        infer_after_1 = eng._model.encode_calls
        emb2, cached2 = eng.get_embedding(text)
        infer_after_2 = eng._model.encode_calls

        check("1o get_embedding: cached=false", cached1 is False)
        check("2o get_embedding: cached=true", cached2 is True,
              f"got cached2={cached2}")
        check("nenhuma inferencia nova na 2a chamada",
              infer_after_2 == infer_after_1 == 1,
              f"infer={infer_after_1}->{infer_after_2}")
        check("embeddings identicos",
              np.allclose(emb1, emb2, atol=1e-6))
        check("dimensao 384", emb1.shape[0] == 384)

        # whitespace diferente -> mesmo hash (texto normalizado)
        _, cached_ws = eng.get_embedding("  " + text + "  ")
        check("whitespace extra tambem e cache hit (texto normalizado)",
              cached_ws is True)


def test_cache_persist():
    print("C1/M4 — cache persistente entre instancias (restart)")
    with tempfile.TemporaryDirectory() as tmp:
        cache_path = os.path.join(tmp, "embedding_cache.json")
        text = "memoria que sobrevive ao restart"

        eng1 = make_engine(tmp)
        _, cached1 = eng1.get_embedding(text)
        check("1a instancia: miss (inferencia)", cached1 is False)
        check("arquivo de cache em disco existe", os.path.exists(cache_path))

        eng2 = make_engine(tmp)  # "restart": nova instancia, mesmo disco
        _, cached2 = eng2.get_embedding(text)
        check("2a instancia (restart): hit sem inferencia", cached2 is True)
        check("contador de hit da 2a instancia = 1", eng2.cache_hit_count == 1)


def _run():
    test_cache_hit()
    test_cache_persist()
    print(f"\n{'='*50}")
    print(f"RESULTADO: {PASS} pass, {FAIL} fail")
    if FAIL:
        sys.exit(1)


def _run():
    test_cache_hit()
    test_cache_persist()
    test_store_and_recall()
    test_no_leakage()
    test_topk_cap()
    print(f"\n{'='*50}")
    print(f"RESULTADO: {PASS} pass, {FAIL} fail")
    if FAIL:
        sys.exit(1)


def make_client(tmpdir):
    """FastAPI TestClient do gateway REAL com embedding stubbed.

    Não sobe servidor: TestClient roda o app in-process (offline, leve).
    VectorStore real (sqlite em tmpdir) prova o persist (M1 parcial).
    """
    from fastapi.testclient import TestClient
    from memory_substrate import api_gateway as gw
    from memory_substrate.indexing.vector_store import (
        VectorStore, VectorStoreConfig,
    )

    gw.app_state.embedding_engine = make_engine(tmpdir)
    gw.app_state.vector_store = VectorStore(
        VectorStoreConfig(db_path=os.path.join(tmpdir, "mem.db"))
    )
    gw.app_state.initialized = True
    client = TestClient(gw.app)

    def _close():
        # Windows: fecha sqlite + salva FAISS antes do tempdir ser apagado
        try:
            gw.app_state.vector_store.close()
        except Exception:
            pass
        gw.app_state.initialized = False

    client._mem_cleanup = _close
    return client


def store(client, text, participants, topic="t", room="room_market", ts=1758200123.0):
    return client.post("/memory/store", json={
        "text": text, "participants": participants,
        "room": room, "topic": topic, "timestamp": ts,
    })


def recall(client, query, participants, top_k=None):
    body = {"query": query, "participants": participants}
    if top_k is not None:
        body["top_k"] = top_k
    return client.post("/memory/recall", json=body)


# ============================================================
# C2 — POST /memory/store  |  C3/M2 — POST /memory/recall
# ============================================================

def test_store_and_recall():
    print("C2+C3/M2 — store + recall por participants retorna a memoria")
    tmp = tempfile.mkdtemp()
    client = make_client(tmp)
    try:
        # Store de memória do par anna<->boris
        r1 = store(client,
                   "Anna e Boris conversaram sobre o mercado abriu cedo.",
                   ["npc_anna", "npc_boris"], topic="mercado abriu cedo")
        check("store responde 200", r1.status_code == 200, r1.text)
        d1 = r1.json()
        check("stored=true", d1.get("stored") is True, str(d1))
        check("id tem prefixo mem_conv_", d1.get("id", "").startswith("mem_conv_"))
        check("1o store: cached=false", d1.get("cached") is False, str(d1))

        # Texto idêntico 2x via endpoint -> 2ª vem do cache (M4 via API)
        r2 = store(client,
                   "Anna e Boris conversaram sobre o mercado abriu cedo.",
                   ["npc_anna", "npc_boris"], topic="mercado abriu cedo")
        check("2o store com texto identico: cached=true",
              r2.json().get("cached") is True, r2.text)

        # Recall pelo mesmo par retorna a memória
        rr = recall(client, "mercado abriu cedo",
                    ["npc_anna", "npc_boris"])
        check("recall responde 200", rr.status_code == 200, rr.text)
        mems = rr.json().get("memories", [])
        check("recall retorna >= 1 memoria", len(mems) >= 1, str(mems))
        if mems:
            m = mems[0]
            check("texto da memoria correto", "mercado" in m.get("text", ""), str(m))
            check("participants corretos",
                  set(m.get("participants", [])) == {"npc_anna", "npc_boris"})
            check("score presente e > 0", m.get("score", 0) > 0)
            check("topic correto", m.get("topic") == "mercado abriu cedo")
            check("scores em ordem desc",
                  all(mems[i]["score"] >= mems[i+1]["score"]
                      for i in range(len(mems)-1)))

        # Texto vazio -> 422 (Pydantic)
        r422 = client.post("/memory/store", json={"text": ""})
        check("texto vazio -> 422", r422.status_code == 422, str(r422.status_code))
    finally:
        client._mem_cleanup()
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def test_no_leakage():
    print("C3/M3 — zero vazamento: par A nao recebe memoria do par B")
    tmp = tempfile.mkdtemp()
    client = make_client(tmp)
    try:
        store(client, "Anna e Boris conversaram sobre o mercado abriu cedo.",
              ["npc_anna", "npc_boris"], topic="mercado")
        store(client, "Carlos e Dora conversaram sobre o servidor caiu ontem.",
              ["npc_carlos", "npc_dora"], topic="servidor caiu")

        # Recall do par A: nunca pode vir memória do par B
        rr = recall(client, "servidor caiu ontem",
                    ["npc_anna", "npc_boris"])
        mems = rr.json().get("memories", [])
        leaked = [m for m in mems
                  if "Carlos" in m.get("text", "") or "Dora" in m.get("text", "")]
        check("par A NAO recebe memoria do par B", len(leaked) == 0, str(mems))

        # Recall sem match de participants -> lista vazia
        rr2 = recall(client, "qualquer coisa", ["npc_anna", "npc_zeca"])
        check("recall sem match de participants -> lista vazia",
              rr2.json().get("memories") == [], rr2.text)

        # Recall do par B retorna a própria memória do par B
        rr3 = recall(client, "servidor caiu ontem",
                     ["npc_carlos", "npc_dora"])
        mems3 = rr3.json().get("memories", [])
        check("par B recebe a propria memoria",
              any("Carlos" in m.get("text", "") for m in mems3), str(mems3))
    finally:
        client._mem_cleanup()
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def test_topk_cap():
    print("C3/M2 — top_k default 3 e hard cap 3")
    tmp = tempfile.mkdtemp()
    client = make_client(tmp)
    try:
        # 5 memórias do mesmo par, textos diferentes (sem cache hit)
        topics = ["mercado", "trigo", "preco", "colheita", "feira"]
        for i, t in enumerate(topics):
            store(client, f"Anna e Boris conversaram sobre {t} na cidade.",
                  ["npc_anna", "npc_boris"], topic=t, ts=1758200123.0 + i)

        rr = recall(client, "mercado trigo preco colheita feira",
                    ["npc_anna", "npc_boris"])
        check("default top_k=3", len(rr.json()["memories"]) <= 3,
              str(len(rr.json()["memories"])))

        rr2 = recall(client, "mercado trigo preco colheita feira",
                     ["npc_anna", "npc_boris"], top_k=10)
        check("top_k=10 capped para 3", len(rr2.json()["memories"]) <= 3,
              str(len(rr2.json()["memories"])))
    finally:
        client._mem_cleanup()
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    _run()
