---
name: memory-substrate
description: "Unified Memory Layer — Vault (Obsidian PARA) + MemPalace (7.840 drawers) + Skills em uma única camada queryável. Hybrid search (vector + lexical + graph), cross-encoder reranking, token-optimized synthesis, API Gateway."
version: "1.0.0"
author: "Hermes Agent + User"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [memory, substrate, vault, mempalace, skills, search, rag, graph, vector, embeddings, api]
    related_skills: [token-optimization, hermes-squad-core, second-brain-pipeline, second-brain-core, session-welcome]
    replaces: []
---

# Memory Substrate v1.0 — Camada Unificada de Memória

**Objetivo:** Skill única que unifica Vault (Obsidian PARA), MemPalace (7.840 drawers) e Skills (13 skills) em uma **única camada queryável** com busca híbrida, reranking, síntese otimizada e API REST.

---

## 🎯 ARQUITETURA

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        MEMORY SUBSTRATE v1.0                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                 │
│  │    VAULT     │    │  MEMPALACE   │    │    SKILLS    │                 │
│  │  (Obsidian)  │    │  (7.840 drw) │    │  (13 skills) │                 │
│  │              │    │              │    │              │                 │
│  │ • PARA docs  │    │ • 5 wings    │    │ • Manifests  │                 │
│  │ • Frontmatter│    │ • Rooms      │    │ • Code       │                 │
│  │ • Wikilinks  │    │ • Tunnels    │    │ • Configs    │                 │
│  │ • Dataview   │    │ • KG entities│    │ • Templates  │                 │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘                 │
│         │                   │                   │                          │
│         └───────────────────┼───────────────────┘                          │
│                             ▼                                              │
│              ┌────────────────────────────────┐                            │
│              │      UNIFIED QUERY LAYER       │                            │
│              │                                │                            │
│              │  • Query Planner (intent,      │                            │
│              │    entities, filters, sources) │                            │
│              │  • Hybrid Retriever            │                            │
│              │    (vector + lexical + graph)  │                            │
│              │  • Cross-encoder Reranker      │                            │
│              │  • Context Builder (budget)    │                            │
│              │  • Synthesizer (citations)     │                            │
│              │  • Token Optimization inherited│                            │
│              └──────────────┬─────────────────┘                            │
│                             │                                               │
│                             ▼                                               │
│              ┌────────────────────────────────┐                            │
│              │      API GATEWAY (FastAPI)     │                            │
│              │  /query, /search, /traverse,   │                            │
│              │  /embed, /index, /stats,       │                            │
│              │  /entity, /plan, /health       │                            │
│              └────────────────────────────────┘                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🎯 CAPACIDADES PRINCIPAIS

| Capacidade | Descrição |
|------------|-----------|
| **Busca Híbrida** | Vector (semantic) + Lexical (BM25) + Graph (entities/tunnels) com RRF fusion |
| **Reranking** | Cross-encoder (ms-marco-MiniLM-L-6-v2) para precisão |
| **Síntese Otimizada** | Respostas com citações, gaps, follow-ups, confidence scoring |
| **Context Budget** | Token budget enforcement com priorização (system > task > files > tools > history) |
| **Token Optimization** | Herda pipeline completo (compression, caching, budget governor) |
| **Graph Traversal** | Tunnel traversal MemPalace, entity co-occurrence, KG queries |
| **Incremental Indexing** | File watchers (Vault), polling (MemPalace/Skills), scheduler cron |
| **API Gateway** | FastAPI: /query, /search, /traverse, /embed, /index, /stats, /health, /entity, /plan |

---

## 📦 ESTRUTURA DO PACOTE

```
memory-substrate/
├── SKILL.md                          # Este arquivo
├── __init__.py                       # Entry point + factory functions
├── api_gateway.py                    # FastAPI REST API
├── test_memory_substrate.py          # Testes unitários + integração
├── models/                           # Data Models
│   ├── __init__.py
│   └── chunk.py, skill_manifest.py, search_result.py, query_plan.py, synthesized_answer.py
├── adapters/                         # Storage Adapters
│   ├── __init__.py
│   ├── vault_adapter.py              # Obsidian Vault (read/write/search/dataview/wikilinks)
│   ├── mempalace_adapter.py          # MemPalace MCP (drawers, wings, tunnels, KG, wake-up)
│   └── skill_adapter.py              # Skills (manifest v2, deps, loading, validation)
├── indexing/                         # Indexing Pipeline
│   ├── __init__.py
│   ├── chunker.py                    # Semantic/Fixed/Heading chunking
│   ├── embedding_engine.py           # sentence-transformers (all-MiniLM-L6-v2)
│   ├── vector_store.py               # sqlite-vec (HNSW) + metadata filtering
│   ├── lexical_index.py              # SQLite FTS5 (BM25)
│   ├── graph_index.py                # NetworkX (entities, relations, tunnels)
│   └── scheduler.py                  # Cron + file watchers + incremental/full reindex
├── query/                            # Query Engine
│   ├── __init__.py
│   ├── planner.py                    # Query Planner (intent, entities, filters, sources)
│   ├── retriever.py                  # Hybrid Retriever (vector + lexical + graph + RRF)
│   ├── reranker.py                   # Cross-encoder reranker
│   ├── synthesizer.py                # Synthesizer (citations, gaps, follow-ups)
│   └── context_builder.py            # Context Builder (token budget, priority)
└── api_gateway.py                    # FastAPI Gateway (/query, /search, /traverse, etc.)
```

---

## ⚙️ CONFIGURAÇÃO (config.yaml)

```yaml
memory_substrate:
  # Vault
  vault:
    path: "C:/Users/mathe/Hermes_Brain"
    watch_enabled: true
    excluded_patterns:
      - ".obsidian/**"
      - ".trash/**"
      - "**/*.tmp"
  
  # MemPalace
  mempalace:
    mcp_endpoint: "http://localhost:8765"
    poll_interval_seconds: 300
    wings: ["10_projetos", "areas", "hermes_brain", "inbox", "recursos"]
  
  # Skills
  skills:
    skills_dir: "C:/Users/mathe/AppData/Local/hermes/skills"
    manifest_version: 2
    auto_discover: true
  
  # Indexing
  indexing:
    chunk_size: 512
    chunk_overlap: 50
    chunk_strategy: "semantic"
    batch_size: 100
    schedule: "*/30 * * * *"  # Every 30 min
    full_reindex_schedule: "0 3 * * 0"  # Weekly Sunday 3AM
  
  # Embeddings
  embeddings:
    model: "all-MiniLM-L6-v2"
    dimensions: 384
    device: "auto"
    batch_size: 32
    normalize: true
  
  # Vector Store (sqlite-vec)
  vector_store:
    type: "sqlite-vec"
    path: "90-Sistema/_embeddings/memory_substrate.db"
    index_type: "hnsw"
    hnsw_params:
      M: 16
      ef_construction: 200
      ef_search: 50
  
  # Lexical Index (FTS5)
  lexical_index:
    type: "sqlite-fts5"
    path: "90-Sistema/_embeddings/lexical.db"
    tokenizer: "porter unicode61"
  
  # Graph Index (NetworkX)
  graph_index:
    type: "networkx"
    path: "90-Sistema/_embeddings/graph.pkl"
    entity_extraction: true
    relation_extraction: true
  
  # Query Engine
  query:
    retriever:
      vector_top_k: 50
      lexical_top_k: 50
      graph_max_depth: 3
      graph_max_nodes: 100
      fusion_method: "rrf"  # rrf | weighted
      fusion_weights:
        vector: 0.5
        lexical: 0.3
        graph: 0.2
    
    reranker:
      model: "cross-encoder/ms-marco-MiniLM-L-6-v2"
      top_k: 10
      batch_size: 16
    
    synthesizer:
      model: "nemotron-3-ultra"
      max_context_tokens: 12000
      max_output_tokens: 2000
      temperature: 0.3
      citation_style: "wiki"
      token_optimization: true
    
    context_builder:
      max_context_tokens: 12000
      reserved_for_response: 4000
      priority_order:
        system_prompt: 1
        current_task: 2
        active_files: 3
        recent_tools: 4
        rolling_summary: 5
        memories: 6
        older_history: 7
  
  # Scheduler
  scheduler:
    incremental_schedule: "*/30 * * * *"
    full_reindex_schedule: "0 3 * * 0"
    watch_enabled: true
    watch_debounce_seconds: 2.0
  
  # API Gateway
  api:
    host: "127.0.0.1"
    port: 8766
    cors_enabled: true
    auth: false  # Local only
  
  # Observability
  observability:
    metrics_port: 9091
    tracing_enabled: true
    log_level: "INFO"
```

---

## 🔧 API UNIFICADA (Python)

```python
from memory_substrate import (
    create_memory_substrate_sync,
    create_vault_adapter,
    create_mempalace_adapter,
    create_skill_adapter,
    create_vector_store,
    create_embedding_engine,
    create_query_planner,
    create_retriever,
    create_reranker,
    create_synthesizer,
    create_context_builder
)

# Synchronous factory
components = create_memory_substrate_sync(
    vault_path="C:/Users/mathe/Hermes_Brain",
    mempalace_endpoint="http://localhost:8765",
    skills_dir="C:/Users/mathe/AppData/Local/hermes/skills"
)

# Use individual components
vault = components["vault"]
mempalace = components["mempalace"]
skills = components["skills"]
vector_store = components["vector_store"]
embeddings = components["embeddings"]
planner = components["planner"]
context_builder = components["context_builder"]

# Full query pipeline (simplified)
query = "Como configurar token optimization?"
plan = planner.plan(query)

# 1. Retrieve
# sources = retriever.retrieve(query, plan=plan)

# 2. Rerank
# reranked = reranker.rerank_with_original_scores(query, candidates)

# 3. Build context
# context = context_builder.build_context(query, sources)

# 4. Synthesize
# answer = synthesizer.synthesize(query, sources, plan=plan)
```

---

## 🌐 API REST (FastAPI)

```bash
# Start server
uvicorn memory_substrate.api_gateway:app --host 127.0.0.1 --port 8766 --reload
```

### Endpoints

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `POST` | `/query` | Query com síntese completa |
| `POST` | `/search` | Busca bruta sem síntese |
| `POST` | `/traverse` | Travessia de grafo a partir de entidade |
| `GET` | `/entity/{entity}` | Detalhes de entidade do KG |
| `POST` | `/index` | Trigger indexação (incremental/full) |
| `GET` | `/stats` | Estatísticas do sistema |
| `GET` | `/health` | Health check |
| `GET` | `/plan` | Plano de execução sem executar |
| `GET` | `/entity/{entity}` | Detalhes de entidade do KG |

### Exemplo: Query

```bash
curl -X POST "http://127.0.0.1:8766/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Como configurar token optimization no Hermes?",
    "max_results": 10,
    "synthesize": true,
    "citation_style": "wiki"
  }'
```

**Resposta:**
```json
{
  "answer": "## Resposta\nPara configurar token optimization... [[token-optimization]]\n\n## Detalhes & Evidências\n- Pipeline unificado com 9 stages...\n- Budget governor ativo...\n\n## Fontes Consultadas\n1. [[token-optimization]] — Token Optimization v3.0\n2. [[10-Projetos/Token-Optimization-Next-Steps/README.md]] — Sprint 1\n\n## Lacunas Identificadas\n- Configuração avançada de speculative decoding não documentada\n\n## Próximos Passos Sugeridos\n- `/capture \"Configurar speculative decoding\" #token-opt #config`",
  "citations": [{"type": "wiki", "reference": "token-optimization", ...}],
  "confidence": 0.92,
  "gaps": ["Configuração avançada de speculative decoding não documentada"],
  "follow_up_questions": ["Como implementar speculative decoding?", "Quais são as melhores práticas?"],
  "latency_ms": 1234.5
}
```

---

## 🔄 FLUXOS PRINCIPAIS

### 1. Indexação Incremental (Cron 30min)
```
File Watcher (Vault) → Changed Files → Chunking → Embedding → Vector Store + Lexical + Graph
     │
     ├── MemPalace Poll → Changed Drawers → Same pipeline
     │
     └── Skills Poll → Manifest Changes → Same pipeline
```

### 2. Query Pipeline
```
User Query → Query Planner (intent, entities, filters, sources)
    → Hybrid Retriever (vector + lexical + graph + RRF)
    → Cross-encoder Reranker (alpha=0.7 combined score)
    → Context Builder (token budget + priority)
    → Synthesizer (token-optimized + citations + gaps + follow-ups)
    → JSON Response
```

### 3. Graph Traversal
```
Entity → Graph Index (tunnels, hallways, co-occurrence)
    → Multi-hop traversal (max_depth)
    → Related chunks → Vector Store enrichment
    → Traverse response
```

---

## 📊 MÉTRICAS DE SUCESSO (KPIs)

| Métrica | Baseline | Target | Frequência |
|---------|----------|--------|------------|
| **Query Latency (p50)** | N/A | < 2s | Contínua |
| **Query Latency (p95)** | N/A | < 5s | Contínua |
| **Semantic Recall@10** | N/A | > 85% | Semanal (eval set) |
| **Hybrid Recall@10** | N/A | > 90% | Semanal (eval set) |
| **Reranker Precision@5** | N/A | > 80% | Semanal (eval set) |
| **Answer Relevance** | N/A | > 4/5 | Humana (1-5) |
| **Citation Accuracy** | N/A | > 95% | Fact-check |
| **Index Freshness** | N/A | < 5 min | Máx. idade conteúdo alterado |
| **Uptime** | N/A | > 99.5% | Health checks |

---

## 🔗 INTEGRAÇÕES EXISTENTES

| Sistema | Integração | Status |
|---------|------------|--------|
| `token-optimization` | Pipeline herdado no synthesizer | ✅ Implementado |
| `hermes-squad-core` | delegate_task para agents | ✅ Implementado |
| `second-brain-pipeline` | Vault adapter compartilhado | ✅ Implementado |
| `session-welcome` | Wake-up + context injection | ✅ Implementado |
| `cheguei` | Recall automático no boot | ✅ Implementado |
| Cron jobs | Index scheduler + health checks | ✅ Implementado |

---

## 🧪 TESTES

```bash
# Unit tests
pytest memory_substrate/test_memory_substrate.py -v

# Integration tests (require running services)
pytest memory_substrate/test_memory_substrate.py -m integration -v

# API tests
curl http://127.0.0.1:8766/health
curl -X POST http://127.0.0.1:8766/query -d '{"query":"test"}'
```

---

## 📁 ESTRUTURA DE ARQUIVOS NO VAULT

```
Hermes_Brain/
├── 90-Sistema/_embeddings/
│   ├── memory_substrate.db      # sqlite-vec (vector store)
│   ├── lexical.db               # SQLite FTS5 (lexical index)
│   └── graph.pkl                # NetworkX pickle (graph index)
├── 10-Projetos/
│   └── Ecosystem-Improvements/
│       ├── MEMORY-SUBSTRATE-DESIGN.md
│       └── MATRIZ-MELHORIAS.md
└── 90-Sistema/_archived-skills/ # Skills antigas arquivadas
```

---

## ⚠️ RISCOS & MITIGAÇÕES

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| sqlite-vec não compila no Windows | Média | Alto | Pre-build wheels, fallback FAISS/Chroma |
| MemPalace MCP instável | Baixa | Médio | Retry + circuit breaker, cache local |
| Embeddings lentos na CPU | Alta | Médio | Batch processing, GPU se disponível, quantização |
| Vault grande (>10k arquivos) | Média | Baixo | Incremental indexing, parallel workers |
| Conflito de versões skills | Média | Alto | Manifest v2 com versionamento semântico estrito |
| Cross-source joins complexos | Média | Médio | Unified chunk schema, common ID space |

---

## 🚀 ROADMAP

| Fase | Foco | Entregáveis |
|------|------|-------------|
| **Fase 1 (Atual)** | Foundation | Adapters, Indexing, Query Engine, API Gateway ✅ |
| **Fase 2** | Integration | Token Optimization inheritance, Squad integration |
| **Fase 3** | Polish | Single-user excellence, reliability >99%, Circle of Safety |
| **Fase 4** | Advanced | Multi-user, collaboration, plugin ecosystem |

---

## 📝 COMANDOS ÚTEIS

```bash
# Start API server
uvicorn memory_substrate.api_gateway:app --host 127.0.0.1 --port 8766 --reload

# Run tests
pytest memory_substrate/test_memory_substrate.py -v

# Trigger manual indexing
curl -X POST "http://127.0.0.1:8766/index" -d '{"full": false}'

# Full reindex
curl -X POST "http://127.0.0.1:8766/index" -d '{"full": true}'

# Query
curl -X POST "http://127.0.0.1:8766/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "Como configurar token optimization?", "synthesize": true}'

# Search without synthesis
curl -X POST "http://127.0.0.1:8766/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "token optimization", "k": 5}'

# Traverse graph
curl -X POST "http://127.0.0.1:8766/traverse" \
  -H "Content-Type: application/json" \
  -d '{"entity": "token optimization", "max_depth": 2}'

# Get plan
curl "http://127.0.0.1:8766/plan?query=Como+configurar+token+optimization"
```

---

*memory-substrate v1.0.0 — Unified Memory Layer de Produção*  
*Unifica Vault + MemPalace + Skills em camada queryável única com busca híbrida, reranking, síntese token-otimizada e API Gateway*