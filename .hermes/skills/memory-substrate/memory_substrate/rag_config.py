"""
rag_config.py — RAG Cirúrgico (L4 Atomic Notes) — Fase 2 PCM, Onda 1
====================================================================

Consulta cirúrgica ao Memory Substrate com budget controlado, conforme o
blueprint `PRINCIPIO-CONFIGURACAO-MAXIMA-ARQUITETURA-v3.md` §5.1:

    QUERY PLANNER → HYBRID RETRIEVER (vector + lexical) → CONTEXT BUILDER
    • Budget: 4000 tokens para conhecimento (restante p/ task + response)
    • Citações obrigatórias (wiki-links)
    • Camada de origem registrada (soul / carta / config-deus / skill)

API pública:
    surgical_recall(query, agent_id, top_k=5, max_tokens=4000) -> dict

Uso como script (prova real):
    python rag_config.py "query" [--agent ALICE] [--top-k 5] [--max-tokens 4000]

Detalhes de implementação (sobre a query API real do pacote):
- VectorStore (indexing/vector_store.py): índice FAISS fallback
  (IndexFlatIP, cosine) persistido em 90-Sistema/_embeddings/.
- LexicalIndex (indexing/lexical_index.py): FTS5 BM25 em lexical.db.
- EmbeddingEngine (indexing/embedding_engine.py): all-MiniLM-L6-v2 CPU
  com cache persistente (embedding_cache.json).
- Retriever (query/retriever.py): fusão RRF (1/(rank+61)) de vector +
  lexical + graph. Graph não existe nesta fase (graph.pkl ausente) e o
  Retriever trata graph_index=None como lista vazia — sem erro.
- BUG contornado: o Retriever repassa a query crua ao FTS5, que rejeita
  pontuação ("fts5: syntax error near ?"). Aqui a query é sanitizada
  para o ramo lexical e o embedding é gerado a partir do texto ORIGINAL
  (semântica preservada), passado pré-computado ao Retriever.
"""

import re
import sys
import time
import json
from pathlib import Path
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Imports do pacote real (funcionam como módulo do pacote OU como script)
# ---------------------------------------------------------------------------
try:  # importado como memory_substrate.rag_config
    from .indexing.vector_store import VectorStore, VectorStoreConfig
    from .indexing.lexical_index import LexicalIndex, LexicalIndexConfig
    from .indexing.embedding_engine import EmbeddingEngine, EmbeddingConfig
    from .query.retriever import (
        Retriever, RetrievalConfig, RetrievalMode, RetrievalResult,
    )
    from .query.reranker import Reranker, RerankerConfig
except ImportError:  # executado como script: python rag_config.py
    _PKG_PARENT = str(Path(__file__).resolve().parent.parent)
    if _PKG_PARENT not in sys.path:
        sys.path.insert(0, _PKG_PARENT)
    from memory_substrate.indexing.vector_store import (
        VectorStore, VectorStoreConfig,
    )
    from memory_substrate.indexing.lexical_index import (
        LexicalIndex, LexicalIndexConfig,
    )
    from memory_substrate.indexing.embedding_engine import (
        EmbeddingEngine, EmbeddingConfig,
    )
    from memory_substrate.query.retriever import (
        Retriever, RetrievalConfig, RetrievalMode, RetrievalResult,
    )
    from memory_substrate.query.reranker import Reranker, RerankerConfig

# ---------------------------------------------------------------------------
# Constantes (blueprint §5.1: budget 4000 tokens, ~4 chars/token)
# ---------------------------------------------------------------------------
VAULT_ROOT = Path("C:/Users/mathe/Hermes_Brain")
EMBEDDINGS_DIR = VAULT_ROOT / "90-Sistema" / "_embeddings"

DEFAULT_TOP_K = 5
DEFAULT_MAX_TOKENS = 4000
CHARS_PER_TOKEN = 4  # estimativa: tokens ≈ chars / 4

# Pool de candidatos maior que top_k: o context builder escolhe os
# top_k que couberem no budget (consulta cirúrgica, sem estourar).
# Blueprint §5.1: retriever top-50 por ramo → cross-encoder rerank → top_k.
POOL_FACTOR = 4
VECTOR_TOP_K = 50
LEXICAL_TOP_K = 50
RERANK_POOL = 50  # candidatos enviados ao cross-encoder (blueprint: top-50→top-10)

# Prioridade de camada para desempate (blueprint §5.1: notas atômicas e
# config de identidade primeiro; knowledge base depois). Usada apenas
# como chave secundária de ordenação — score RRF domina.
LAYER_PRIORITY = {"soul": 0, "carta": 1, "config-deus": 2, "skill": 3}

# Stopwords PT/EN mínimas: tokens de 1 letra nunca ajudam o BM25.
_FTS_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)

# Cache de componentes (índice ~3MB + modelo MiniLM: carregar 1x por processo)
_stack: Optional[Dict] = None


# ---------------------------------------------------------------------------
# Stack do Substrate (singleton lazy)
# ---------------------------------------------------------------------------
def get_stack() -> Dict:
    """Carrega o índice existente da Fase 1 (vector + lexical + embeddings).

    Usa APENAS componentes reais do pacote memory_substrate — nenhuma
    re-implementação de busca.
    """
    global _stack
    if _stack is not None:
        return _stack

    vector_store = VectorStore(VectorStoreConfig(
        db_path=str(EMBEDDINGS_DIR / "memory_substrate.db"),
    ))
    lexical_index = LexicalIndex(LexicalIndexConfig(
        db_path=str(EMBEDDINGS_DIR / "lexical.db"),
    ))
    embedding_engine = EmbeddingEngine(EmbeddingConfig(
        model_name="all-MiniLM-L6-v2",
        device="cpu",  # hardware: CPU, 12GB RAM
        embedding_cache_path=str(EMBEDDINGS_DIR / "embedding_cache.json"),
    ))
    retriever = Retriever(
        vector_store=vector_store,
        lexical_index=lexical_index,
        graph_index=None,  # graph.pkl não existe nesta fase → sem ramo graph
        embedding_engine=embedding_engine,
        config=RetrievalConfig(
            vector_top_k=VECTOR_TOP_K,
            lexical_top_k=LEXICAL_TOP_K,
            fusion_method="rrf",
            min_score_threshold=0.0,
            deduplicate=True,
            max_final_results=VECTOR_TOP_K * POOL_FACTOR,
        ),
    )
    reranker = Reranker(RerankerConfig(
        model_name="cross-encoder/ms-marco-MiniLM-L-6-v2",
        device="cpu",  # hardware: CPU, 12GB RAM (modelo já em cache local)
        batch_size=16,
        top_k=RERANK_POOL,
    ))
    _stack = {
        "vector_store": vector_store,
        "lexical_index": lexical_index,
        "embedding_engine": embedding_engine,
        "retriever": retriever,
        "reranker": reranker,
    }
    return _stack


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------
def sanitize_fts_query(query: str) -> str:
    """Converte linguagem natural em query FTS5 segura.

    O Retriever repassa a string direto ao FTS5, que trata '?', '!', '"'
    etc. como operadores/sintaxe e aborta com "syntax error". Solução:
    extrair tokens unicode, dropar 1-char, deduplicar e unir com OR
    (OR amplia o recall; o BM25 naturalmente rebaixa termos comuns).
    """
    seen = set()
    tokens = []
    for tok in _FTS_TOKEN_RE.findall(query):
        if len(tok) < 2:
            continue
        low = tok.lower()
        if low not in seen:
            seen.add(low)
            tokens.append(low)
    return " OR ".join(tokens) if tokens else '""'


def estimate_tokens(text: str) -> int:
    """Estimativa de tokens do blueprint: ~4 chars por token."""
    return (len(text) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN


def _layer_of(chunk: Dict) -> str:
    """Camada de origem do chunk (soul/carta/config-deus/skill)."""
    meta = chunk.get("metadata") or {}
    layer = meta.get("layer")
    if layer:
        return str(layer)
    # fallback heurístico pelo caminho do arquivo
    sid = str(chunk.get("source_id", ""))
    if "/SOUL-" in sid:
        return "soul"
    if "/CARTA-" in sid:
        return "carta"
    if "config-deus" in sid:
        return "config-deus"
    return "skill"


def _wiki_link(chunk: Dict) -> str:
    """Citação em wiki-link (blueprint: citações obrigatórias)."""
    title = chunk.get("title") or Path(str(chunk.get("source_id", "fonte"))).stem
    return f"[[{title}]]"


# ---------------------------------------------------------------------------
# API principal
# ---------------------------------------------------------------------------
def surgical_recall(
    query: str,
    agent_id: str = "default",
    top_k: int = DEFAULT_TOP_K,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> Dict:
    """RAG cirúrgico: query híbrida (vector+lexical) com budget de tokens.

    Pipeline (blueprint §5.1):
      1. Embedding real da query (all-MiniLM-L6-v2, cache-aware).
      2. Retriever híbrido do Substrate (vector FAISS + FTS5 BM25, RRF).
      2b. Cross-encoder rerank (ms-marco-MiniLM-L-6-v2) — precisão
          cirúrgica top-50 → top_k (fallback gracioso p/ ordem RRF).
      3. Context builder: monta bloco limpo com fontes citadas, cap de
         `max_tokens` (~4 chars/token), registrando a camada de origem.

    Args:
        query: pergunta em linguagem natural.
        agent_id: agente que consulta (registrado no bloco/relatório).
        top_k: nº máximo de fontes no bloco final.
        max_tokens: budget do bloco (default 4000).

    Returns:
        dict com keys:
          - query, agent_id, context_block, tokens_est, budget_tokens
          - sources: lista com rank/layer/title/source_id/score/match_types
          - stats: contagens de índice, tempo, modo de fusão
    """
    start = time.time()
    stack = get_stack()
    vs: VectorStore = stack["vector_store"]
    ee: EmbeddingEngine = stack["embedding_engine"]
    retriever: Retriever = stack["retriever"]

    # 1. Embedding REAL da query original (preserva semântica; cache-aware)
    query_embedding = ee.encode(query)

    # 2. Query híbrida no índice da Fase 1.
    #    - ramo lexical recebe a query sanitizada (contorna bug FTS5)
    #    - ramo vector usa o embedding pré-computado da query original
    fts_query = sanitize_fts_query(query)
    pool_size = max(VECTOR_TOP_K, top_k * POOL_FACTOR)
    candidates: List[RetrievalResult] = retriever.retrieve(
        query=fts_query,
        query_embedding=query_embedding,
        mode=RetrievalMode.HYBRID,
        top_k=pool_size,
    )

    # 2b. Cross-encoder rerank (blueprint §5.1: top-50 → top-k com
    #     precisão cirúrgica). Conteúdo completo via vs.get (o Retriever
    #     trunca em 500 chars). Fallback gracioso: se o cross-encoder
    #     falhar (modelo ausente etc.), mantém a ordem RRF.
    rerank_applied = False
    rerank_scores: Dict[str, float] = {}
    rerank_pool = candidates[:RERANK_POOL]
    if len(rerank_pool) > 1:
        rerank_input = []
        for res in rerank_pool:
            chunk = vs.get(res.chunk_id)
            content = (chunk.get("content") if chunk else None) or res.content
            if content:
                rerank_input.append({
                    "chunk_id": res.chunk_id,
                    "content": content,
                    "rrf_score": float(res.score),
                })
        try:
            rerank_out = stack["reranker"].rerank(
                query=query, candidates=rerank_input, top_k=len(rerank_input),
            )
            rerank_scores = {
                c["chunk_id"]: float(c.get("rerank_score", 0.0))
                for c in rerank_out
            }
            # ordem final = ordem do cross-encoder (NÃO re-ordenar por RRF)
            order = {c["chunk_id"]: i for i, c in enumerate(rerank_out)}
            candidates = sorted(
                rerank_pool,
                key=lambda res: order.get(res.chunk_id, len(order)),
            )
            rerank_applied = True
        except Exception as e:
            print(f"[rag_config] rerank indisponível ({e}); usando ordem RRF")

    # 3. Enriquecimento: dados completos do chunk (o Retriever trunca 500ch).
    #    Ordem final = rerank do cross-encoder (se aplicado) ou RRF;
    #    prioridade de camada só como desempate.
    enriched = []
    for res in candidates:
        chunk = vs.get(res.chunk_id)
        if not chunk:
            continue
        enriched.append({
            "chunk_id": res.chunk_id,
            "rrf_score": float(res.score),
            "rerank_score": rerank_scores.get(res.chunk_id),
            "match_types": {k: float(v) for k, v in res.match_types.items()},
            "layer": _layer_of(chunk),
            "title": chunk.get("title") or "",
            "source_id": chunk.get("source_id") or "",
            "content": chunk.get("content") or "",
            "tokens_est": chunk.get("token_count")
                          or estimate_tokens(chunk.get("content") or ""),
        })
    if rerank_applied:
        enriched.sort(key=lambda e: (
            -e["rerank_score"],
            LAYER_PRIORITY.get(e["layer"], 9),
        ))
    else:
        enriched.sort(key=lambda e: (-e["rrf_score"],
                                     LAYER_PRIORITY.get(e["layer"], 9)))

    # 4. Context builder: header + blocos até top_k fontes / budget.
    header = (
        f"=== RAG CIRÚRGICO (Memory Substrate, Fase 2 PCM) ===\n"
        f"query: {query}\n"
        f"agente: {agent_id}\n"
        f"modo: híbrido vector+lexical (RRF) | budget: {max_tokens} tokens "
        f"(~{CHARS_PER_TOKEN} chars/token)\n"
    )
    tokens_used = estimate_tokens(header)

    selected: List[Dict] = []
    blocks: List[str] = []
    for cand in enriched:
        if len(selected) >= top_k:
            break
        score_part = (f"rerank={cand['rerank_score']:.3f}"
                      if cand["rerank_score"] is not None
                      else f"score_rrf={cand['rrf_score']:.4f}")
        block = (
            f"\n[{len(selected) + 1}] camada={cand['layer']} | {score_part} | "
            f"matches={sorted(cand['match_types'])} | "
            f"{_wiki_link(cand)} ({cand['source_id']})\n"
            f"{cand['content'].strip()}\n"
        )
        block_tokens = estimate_tokens(block)
        if tokens_used + block_tokens > max_tokens:
            # consulta cirúrgica: não estoura o budget nem trunca no meio —
            # para nas fontes inteiras que couberem.
            if not selected:
                # garante ao menos 1 fonte: trunca este bloco no que sobra
                room_chars = (max_tokens - tokens_used) * CHARS_PER_TOKEN
                if room_chars > 200:
                    block = block[:room_chars] + "\n[…truncado p/ respeitar budget]\n"
                    block_tokens = estimate_tokens(block)
                    tokens_used += block_tokens
                    selected.append(cand)
                    blocks.append(block)
            break
        tokens_used += block_tokens
        selected.append(cand)
        blocks.append(block)

    sources_line = "\n".join(
        f"  {i + 1}. {s['layer']} — {_wiki_link(s)} — {s['source_id']}"
        for i, s in enumerate(selected)
    )
    footer = (
        f"\n=== FIM RAG: {len(selected)} fonte(s), "
        f"{tokens_used} tokens estimados de {max_tokens} ==="
    )
    context_block = header + "".join(blocks) + footer + "\n"

    elapsed_ms = (time.time() - start) * 1000.0
    try:
        total_chunks = vs.count()
    except Exception:
        total_chunks = None

    return {
        "query": query,
        "agent_id": agent_id,
        "context_block": context_block,
        "tokens_est": tokens_used,
        "budget_tokens": max_tokens,
        "sources": [
            {
                "rank": i + 1,
                "layer": s["layer"],
                "title": s["title"],
                "wiki_link": _wiki_link({"title": s["title"]}),
                "source_id": s["source_id"],
                "rrf_score": s["rrf_score"],
                "rerank_score": s["rerank_score"],
                "match_types": s["match_types"],
                "chunk_tokens_est": s["tokens_est"],
            }
            for i, s in enumerate(selected)
        ],
        "stats": {
            "candidates_pool": len(candidates),
            "total_index_chunks": total_chunks,
            "elapsed_ms": round(elapsed_ms, 1),
            "fts_query": fts_query,
            "vector_top_k": VECTOR_TOP_K,
            "lexical_top_k": LEXICAL_TOP_K,
            "fusion": "rrf",
            "rerank": "cross-encoder/ms-marco-MiniLM-L-6-v2"
                      if rerank_applied else "fallback-rrf",
        },
    }


# ---------------------------------------------------------------------------
# CLI de prova (saída crua colável em relatório)
# ---------------------------------------------------------------------------
def _main(argv: List[str]) -> int:
    args = argv[1:]
    query = None
    agent_id = "default"
    top_k = DEFAULT_TOP_K
    max_tokens = DEFAULT_MAX_TOKENS
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--agent":
            agent_id = args[i + 1]; i += 2
        elif a == "--top-k":
            top_k = int(args[i + 1]); i += 2
        elif a == "--max-tokens":
            max_tokens = int(args[i + 1]); i += 2
        elif query is None:
            query = a; i += 1
        else:
            i += 1
    if not query:
        print(__doc__)
        return 2

    result = surgical_recall(query, agent_id=agent_id, top_k=top_k,
                             max_tokens=max_tokens)
    print(result["context_block"])
    print("--- FONTES (JSON) ---")
    print(json.dumps(result["sources"], ensure_ascii=False, indent=1))
    print("--- STATS (JSON) ---")
    print(json.dumps(result["stats"], ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
