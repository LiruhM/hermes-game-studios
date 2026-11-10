"""
Memory Substrate v1.0 — API Gateway
FastAPI-based REST API for the Memory Substrate.
"""

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime
import uvicorn
import asyncio
import time
import uuid
import random
from pathlib import Path
from contextlib import asynccontextmanager

from memory_substrate.adapters import (
    VaultAdapter, create_vault_adapter,
    MemPalaceAdapter, create_mempalace_adapter,
    SkillAdapter, create_skill_adapter
)
from memory_substrate.indexing import (
    VectorStore, create_vector_store,
    LexicalIndex, create_lexical_index,
    GraphIndex, create_graph_index,
    EmbeddingEngine, create_embedding_engine,
    IndexScheduler, create_scheduler,
    Chunker, create_chunker
)
from memory_substrate.query import (
    QueryPlanner, create_query_planner,
    Retriever, create_retriever,
    Reranker, create_reranker,
    Synthesizer, create_synthesizer,
    ContextBuilder, create_context_builder,
    QueryPlan, QueryIntent
)
from memory_substrate.models import MemoryChunk, SearchResult


# ============================================================
# PYDANTIC MODELS
# ============================================================

class QueryRequest(BaseModel):
    query: str
    max_results: int = 20
    synthesize: bool = True
    citation_style: str = "wiki"
    sources: List[str] = ["vault", "mempalace", "skill"]
    filters: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, Any]] = None


class QueryResponse(BaseModel):
    answer: str
    citations: List[Dict[str, Any]]
    confidence: float
    gaps: List[str]
    follow_up_questions: List[str]
    sources: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    latency_ms: float


class SearchRequest(BaseModel):
    query: str
    k: int = 10
    source: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None


class SearchResponse(BaseModel):
    results: List[Dict[str, Any]]
    total: int
    latency_ms: float


class IndexRequest(BaseModel):
    source: Optional[str] = None  # None = all
    full: bool = False


class IndexResponse(BaseModel):
    status: str
    chunks_indexed: int
    duration_ms: float


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    adapters: Dict[str, bool]
    index_stats: Dict[str, Any]
    scheduler: Dict[str, Any]


class TraverseRequest(BaseModel):
    entity: str
    max_depth: int = 3
    direction: str = "both"  # outgoing | incoming | both


class DialogueRequest(BaseModel):
    npc_id: str
    user_text: str
    context: Optional[Dict[str, Any]] = None


class DialogueAction(BaseModel):
    type: str  # move, spawn_artifact, schedule_meeting, change_behavior
    target: Optional[Dict[str, int]] = None
    behavior: Optional[str] = None
    artifact: Optional[Dict[str, Any]] = None
    meeting: Optional[Dict[str, Any]] = None


class DialogueResponse(BaseModel):
    text: str
    emotion: str = "neutral"
    actions: List[DialogueAction] = []
    metadata: Optional[Dict[str, Any]] = None


class ConversationLineRequest(BaseModel):
    """BLUEPRINT-P1 §6: geração de fala de conversa NPC<->NPC."""
    speaker_id: str
    listener_id: str
    recent_lines: List[Dict[str, Any]] = []


class ConversationLineResponse(BaseModel):
    text: str
    speaker_id: str
    metadata: Optional[Dict[str, Any]] = None


# ---- BLUEPRINT-P2-MEMORIA §3 — memória de conversas NPC <-> NPC ----

class MemoryStoreRequest(BaseModel):
    """BLUEPRINT-P2 §3.1 — payload de gravação de memória de conversa."""
    text: str = Field(..., min_length=1)  # obrigatório, não vazio (422 se vazio)
    participants: List[str] = []
    room: str = ""
    topic: str = ""
    timestamp: float = Field(default_factory=time.time)


class MemoryStoreResponse(BaseModel):
    id: str
    cached: bool = False  # true se o embedding veio do cache por hash (§5)
    stored: bool = True
    reason: Optional[str] = None  # preenchido quando stored=false


class MemoryRecalledItem(BaseModel):
    text: str
    topic: str = ""
    timestamp: float = 0.0
    participants: List[str] = []
    score: float = 0.0


class MemoryRecallRequest(BaseModel):
    """BLUEPRINT-P2 §3.2 — recall com filtro participants."""
    query: str = Field(..., min_length=1)
    participants: List[str] = []
    top_k: int = 3  # default 3; hard cap 3 aplicado no endpoint


class MemoryRecallResponse(BaseModel):
    memories: List[MemoryRecalledItem] = []


# ============================================================
# GLOBAL STATE
# ============================================================

class AppState:
    def __init__(self):
        self.vault_adapter = None
        self.mempalace_adapter = None
        self.skill_adapter = None
        self.vector_store = None
        self.lexical_index = None
        self.graph_index = None
        self.embedding_engine = None
        self.chunker = None
        self.scheduler = None
        self.query_planner = None
        self.retriever = None
        self.reranker = None
        self.synthesizer = None
        self.context_builder = None
        self.initialized = False


app_state = AppState()


# ============================================================
# LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await initialize_memory_substrate()
    yield
    # Shutdown
    await shutdown_memory_substrate()


async def initialize_memory_substrate():
    """Initialize all Memory Substrate components."""
    print("🚀 Initializing Memory Substrate...")
    
    try:
        # 1. Adapters
        app_state.vault_adapter = create_vault_adapter(
            vault_path="C:/Users/mathe/Hermes_Brain",
            watch_enabled=True
        )
        print("✅ Vault adapter initialized")
        
        app_state.mempalace_adapter = create_mempalace_adapter(
            endpoint="http://localhost:8765"
        )
        print("✅ MemPalace adapter initialized")
        
        app_state.skill_adapter = create_skill_adapter(
            skills_dir="C:/Users/mathe/AppData/Local/hermes/skills"
        )
        print("✅ Skill adapter initialized")
        
        # 2. Indexing components
        app_state.vector_store = create_vector_store()
        print("✅ Vector store initialized")
        
        app_state.lexical_index = create_lexical_index()
        print("✅ Lexical index initialized")
        
        app_state.graph_index = create_graph_index()
        print("✅ Graph index initialized")
        
        app_state.embedding_engine = create_embedding_engine()
        print("✅ Embedding engine initialized")
        
        app_state.chunker = create_chunker()
        print("✅ Chunker initialized")
        
        # 3. Scheduler
        app_state.scheduler = create_scheduler()
        app_state.scheduler.register_callback('file_changed', on_file_changed)
        app_state.scheduler.register_callback('mempalace_changed', on_mempalace_changed)
        app_state.scheduler.register_callback('skill_changed', on_skill_changed)
        app_state.scheduler.register_callback('index_vault_file', on_file_changed)
        app_state.scheduler.start()
        print("✅ Scheduler started")
        
        # 4. Query Engine
        app_state.query_planner = create_query_planner()
        print("✅ Query planner initialized")
        
        app_state.retriever = create_retriever(
            vector_store=app_state.vector_store,
            lexical_index=app_state.lexical_index,
            graph_index=app_state.graph_index,
            embedding_engine=app_state.embedding_engine
        )
        print("✅ Retriever initialized")
        
        app_state.reranker = create_reranker()
        print("✅ Reranker initialized")
        
        app_state.synthesizer = create_synthesizer()
        print("✅ Synthesizer initialized")
        
        app_state.context_builder = create_context_builder()
        print("✅ Context builder initialized")
        
        app_state.initialized = True
        print("🎉 Memory Substrate fully initialized!")
        
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        raise


async def shutdown_memory_substrate():
    """Graceful shutdown."""
    print("🛑 Shutting down Memory Substrate...")
    
    if app_state.scheduler:
        app_state.scheduler.close()
    
    if app_state.vector_store:
        app_state.vector_store.close()
    
    if app_state.lexical_index:
        app_state.lexical_index.close()
    
    print("✅ Shutdown complete")


# ============================================================
# CALLBACK HANDLERS
# ============================================================

def on_file_changed(rel_path: str, event_type: str):
    """Handle vault file changes."""
    try:
        # Get full path
        full_path = str(app_state.vault_adapter.vault_path / rel_path)
        vault_file = app_state.vault_adapter.read_file(rel_path)
        chunks = app_state.chunker.chunk_file(full_path)
        
        for chunk in chunks:
            embedding = app_state.embedding_engine.encode(chunk["content"])
            
            # Extract metadata fields for vector store
            meta = chunk["metadata"]
            app_state.vector_store.add(
                embedding=embedding,
                source="vault",
                source_id=rel_path,
                content=chunk["content"],
                title=Path(rel_path).stem,
                para_layer=meta.get("para_layer", 1),
                para_category=meta.get("para_category", "meta"),
                tags=meta.get("tags", []),
                wing=meta.get("wing"),
                room=meta.get("room"),
                drawer_type=meta.get("drawer_type"),
                skill_name=meta.get("skill_name"),
                skill_version=meta.get("skill_version"),
                links=meta.get("links", []),
                entities=meta.get("entities", []),
                relevance_score=meta.get("relevance_score", 0.0),
                token_count=meta.get("token_count", 0),
                language=meta.get("language", "pt"),
                metadata=meta
            )
            
            app_state.lexical_index.add(
                chunk_id=str(uuid.uuid4()),
                source="vault",
                source_id=rel_path,
                title=Path(rel_path).stem,
                content=chunk["content"],
                tags=meta.get("tags", []),
                entities=meta.get("entities", [])
            )
            
            # Update graph
            entities = meta.get("entities", [])
            for entity in entities:
                app_state.graph_index.add_relation(
                    "vault:" + rel_path, entity, "mentions"
                )
                app_state.graph_index.auto_link_chunk(
                    f"vault:{rel_path}", chunk["content"], entities
                )
        
        print(f"📝 Indexed {rel_path} ({event_type})")
        
    except Exception as e:
        print(f"Error indexing {rel_path}: {e}")


def on_mempalace_changed(drawer_id: str, event_type: str):
    """Handle MemPalace drawer changes."""
    try:
        drawer = app_state.mempalace_adapter.get_drawer(drawer_id)
        if drawer:
            # Process similar to vault file
            pass
    except Exception as e:
        print(f"Error processing MemPalace change: {e}")


def on_skill_changed(skill_name: str, event_type: str):
    """Handle skill manifest changes."""
    try:
        manifest = app_state.skill_adapter.get_skill(skill_name)
        if manifest:
            # Update skill in vector store
            pass
    except Exception as e:
        print(f"Error processing skill change: {e}")


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="Memory Substrate API",
    description="Unified query interface for Vault, MemPalace, and Skills",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# DEPENDENCIES
# ============================================================

def get_initialized():
    if not app_state.initialized:
        raise HTTPException(status_code=503, detail="Memory Substrate not initialized")
    return True


# ============================================================
# ROUTES
# ============================================================

@app.get("/health", response_model=HealthResponse)
async def health_check(_: bool = Depends(get_initialized)):
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        adapters={
            "vault": app_state.vault_adapter is not None,
            "mempalace": app_state.mempalace_adapter is not None,
            "skill": app_state.skill_adapter is not None
        },
        index_stats={
            "vector": app_state.vector_store.get_stats() if app_state.vector_store else {},
            "lexical": app_state.lexical_index.get_stats() if app_state.lexical_index else {},
            "graph": app_state.graph_index.get_stats() if app_state.graph_index else {}
        },
        scheduler={
            "running": app_state.scheduler.running if app_state.scheduler else False,
            "stats": app_state.scheduler.get_status() if app_state.scheduler else {}
        }
    )


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """
    Main query endpoint - natural language query with synthesis.
    """
    start_time = time.time()
    
    try:
        # 1. Plan the query
        plan = app_state.query_planner.plan(request.query, request.context)
        
        # 2. Retrieve sources
        sources = app_state.retriever.retrieve(
            query=request.query,
            plan=plan,
            filters=request.filters,
            top_k=request.max_results
        )
        
        # 3. Rerank
        candidates = [{"chunk_id": s.chunk_id, "content": s.content, **s.metadata} for s in sources]
        reranked = app_state.reranker.rerank_with_original_scores(
            query=request.query,
            candidates=candidates,
            top_k=request.max_results
        )
        
        # Convert back to RetrievalResult format
        # (simplified for now)
        
        # 4. Synthesize answer
        answer = app_state.synthesizer.synthesize(
            query=request.query,
            sources=[{"chunk_id": r.chunk_id, "content": r.content, **r.metadata} for r in sources],
            plan=plan,
            context=request.context
        )
        
        latency_ms = (time.time() - start_time) * 1000
        
        return QueryResponse(
            answer=answer.answer,
            citations=answer.citations,
            confidence=answer.confidence,
            gaps=answer.gaps,
            follow_up_questions=answer.follow_up_questions,
            sources=answer.sources,
            metadata=answer.metadata,
            latency_ms=latency_ms
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """
    Search endpoint - raw retrieval without synthesis.
    """
    start_time = time.time()
    
    try:
        results = app_state.retriever.retrieve(
            query=request.query,
            filters=request.filters,
            top_k=request.k
        )
        
        latency_ms = (time.time() - start_time) * 1000
        
        return SearchResponse(
            results=[{
                "id": r.chunk_id,
                "source": r.source,
                "score": r.score,
                "match_types": r.match_types,
                "metadata": r.metadata,
                "content": r.content,
                "highlights": r.highlights
            } for r in results],
            total=len(results),
            latency_ms=(time.time() - start_time) * 1000
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/index", response_model=IndexResponse)
async def index(request: IndexRequest, background_tasks: BackgroundTasks):
    """
    Trigger indexing (incremental or full).
    """
    start_time = time.time()
    
    try:
        if request.full:
            background_tasks.add_task(run_full_reindex)
            return IndexResponse(
                status="full_reindex_started",
                chunks_indexed=0,
                duration_ms=(time.time() - start_time) * 1000
            )
        else:
            # Trigger incremental
            if app_state.scheduler:
                stats = app_state.scheduler.trigger_incremental()
                return IndexResponse(
                    status="incremental_completed",
                    chunks_indexed=stats.get("chunks_created", 0),
                    duration_ms=(time.time() - start_time) * 1000
                )
            else:
                raise HTTPException(status_code=503, detail="Scheduler not available")
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/traverse")
async def traverse(request: TraverseRequest):
    """
    Graph traversal from an entity.
    """
    try:
        paths = app_state.graph_index.traverse_from(
            entity=request.entity,
            max_depth=request.max_depth,
            direction=request.direction
        )
        
        return {
            "entity": request.entity,
            "paths": paths,
            "total_paths": len(paths)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/conversation", response_model=ConversationLineResponse)
async def conversation_line(request: ConversationLineRequest):
    """
    BLUEPRINT-P1 §6 — gera UMA fala de conversa NPC <-> NPC.
    O servidor do jogo chama com timeout de 5s; falha aqui vira
    fallback de pool local no game server (nunca silencia o turno).
    """
    speaker_id = request.speaker_id
    listener_id = request.listener_id
    recent = request.recent_lines or []

    # Extrai role dos ids (mesma convenção de /dialogue)
    role = "dev"
    sid = speaker_id.lower()
    if "devops" in sid:
        role = "devops"
    elif "watchdog" in sid:
        role = "watchdog"
    elif "researcher" in sid:
        role = "researcher"
    elif "receptionist" in sid:
        role = "dev"

    # Pequenos abridores/continuações por role — o mesmo estilo de
    # resposta em templates usado por /dialogue (sem chamada LLM pesada).
    _conversation_starters = {
        "dev": [
            "Ei, viu o build da noite? Passou verde por pouco.",
            "Tava refactorando o módulo de colisão... quer ver depois?",
            "Esse bug some quando eu chego perto, juro.",
            "Você revisou meu PR? Ficou pequeno, prometo.",
        ],
        "devops": [
            "Servidor respondeu em 3 ms hoje, tá suspeito.",
            "O deploy de ontem rodou liso, aproveita que tá calmo.",
            "Recebi alerta falso às 3 da manhã. De novo.",
            "Vamos revisar o runbook antes do próximo release?",
        ],
        "watchdog": [
            "Sistema nominal. Zero alertas. Aproveitando a calmaria.",
            "Fiz a ronda, tudo no lugar.",
            "Vi o rack 3 piscando estranho, vou vigiar.",
        ],
        "researcher": [
            "Li um paper interessante sobre compressão de contexto.",
            "Achei um benchmark novo, quer dar uma olhada?",
            "Minha hipótese falhou de novo. Mas de um jeito bonito.",
        ],
    }
    pool = _conversation_starters.get(role, _conversation_starters["dev"])

    # Se há falas recentes, dá continuidade ao assunto (simples echo-contexto)
    if recent:
        last_author, last_text = "", ""
        for ln in reversed(recent):
            last_author, last_text = ln.get("author", ""), ln.get("text", "")
            if last_author != speaker_id:
                break
        if last_text:
            text = f"Pois é... sobre \"{last_text[:40]}\", tava pensando nisso também."
        else:
            text = random.choice(pool)
    else:
        text = random.choice(pool)

    return ConversationLineResponse(
        text=text,
        speaker_id=speaker_id,
        metadata={"listener_id": listener_id, "role": role,
                  "recent_count": len(recent)},
    )


# ============================================================
# BLUEPRINT-P2-MEMORIA §3 — /memory/store e /memory/recall
# ============================================================

# Limiar mínimo de similaridade no recall: abaixo disso a "memória" é ruído
# e o NPC não cita conversas irrelevantes (M3: sem match -> lista vazia).
MEMORY_MIN_SCORE = 0.10


@app.post("/memory/store", response_model=MemoryStoreResponse)
async def memory_store(request: MemoryStoreRequest):
    """
    BLUEPRINT-P2 §3.1 — grava uma memória de conversa NPC <-> NPC.

    - Embedding via cache por hash do EmbeddingEngine (§5): `cached=true`
      quando servido do disco, zero inferência.
    - Persist: vector_store (sqlite junto ao persist existente).
    - Falha de gravação -> stored=false + reason (nunca 500 direto).
    """
    mem_id = f"mem_conv_{uuid.uuid4().hex[:4]}_{int(request.timestamp)}"

    try:
        # Formato embeddado (decisão §2.2): o próprio `text` já chega como
        # resumo pronto do game server — embeddamos text.strip() sem concat.
        embedding, cached = app_state.embedding_engine.get_embedding(request.text.strip())

        metadata = {
            "participants": request.participants,
            "timestamp": request.timestamp,
            "room": request.room,
            "topic": request.topic,
            "type": "conversation",
        }

        app_state.vector_store.add(
            embedding=embedding,
            source="conversation",       # memória de conversa NPC<->NPC
            source_id=mem_id,
            content=request.text,
            title=request.topic or mem_id,
            room=request.room or None,
            metadata=metadata,
            embedding_model=app_state.embedding_engine.config.model_name,
        )

        return MemoryStoreResponse(id=mem_id, cached=cached, stored=True)

    except HTTPException:
        raise
    except Exception as e:
        return MemoryStoreResponse(
            id=mem_id, cached=False, stored=False, reason=str(e)
        )


@app.post("/memory/recall", response_model=MemoryRecallResponse)
async def memory_recall(request: MemoryRecallRequest):
    """
    BLUEPRINT-P2 §3.2 — recall de memórias por similaridade.

    - Filtro participants: só retorna memórias em que TODOS os
      participantes consultados participaram (zero vazamento, M3).
    - top_k default 3, HARD CAP 3 (M2).
    - Score abaixo de MEMORY_MIN_SCORE é descartado (sem match -> []).
    - Sem memories/participants -> lista vazia, nunca erro.
    """
    try:
        top_k = max(1, min(request.top_k, 3))  # hard cap 3 (M2)

        # Embedding da query (cache por hash também protege aqui)
        query_emb, _ = app_state.embedding_engine.get_embedding(
            request.query.strip())

        # Busca vetorial ampla, filtra participants e re-ranqueia por
        # similaridade real (cosine em embeddings normalizados).
        raw = app_state.vector_store.search_vector(query_emb, k=50)
        memories = []
        for chunk_id, distance in raw:
            chunk = app_state.vector_store.get(chunk_id)
            if not chunk:
                continue
            meta = chunk.get("metadata") or {}
            if meta.get("type") != "conversation":
                continue  # só memórias de conversa
            mem_parts = set(meta.get("participants") or [])
            # TODOS os participantes consultados devem estar na memória (M3)
            if request.participants and not all(
                    p in mem_parts for p in request.participants):
                continue
            # sqlite-vec distance -> cosine similarity; FAISS: 1.0 - IP
            score = 1.0 - distance if distance <= 2.0 else distance
            if score < MEMORY_MIN_SCORE:
                continue
            memories.append(MemoryRecalledItem(
                text=chunk.get("content") or "",
                topic=meta.get("topic") or "",
                timestamp=meta.get("timestamp") or 0.0,
                participants=meta.get("participants") or [],
                score=round(float(score), 4),
            ))
            if len(memories) >= top_k:
                break

        return MemoryRecallResponse(memories=memories)

    except HTTPException:
        raise
    except Exception as e:
        # Fallback silencioso (§4): qualquer erro vira lista vazia,
        # a conversa do NPC segue sem memória, zero crash.
        return MemoryRecallResponse(memories=[])


@app.post("/dialogue", response_model=DialogueResponse)
async def dialogue(request: DialogueRequest):
    """
    NPC Dialogue endpoint - processes player dialogue with NPCs.
    Uses the Memory Substrate to generate contextual responses and actions.
    """
    try:
        npc_id = request.npc_id
        user_text = request.user_text
        context = request.context or {}
        
        # Query Memory Substrate for relevant context about this NPC
        # Search for NPC's knowledge, personality, past interactions
        search_query = f"NPC {npc_id} personality knowledge dialogue context {user_text}"
        sources = app_state.retriever.retrieve(
            query=search_query,
            filters={"entity": npc_id},
            top_k=5
        )
        
        # Build context from NPC's knowledge
        npc_context = []
        for s in sources:
            content = s.content[:500] if s.content else ""
            if content:
                npc_context.append(content)
        
        # Use synthesizer to generate NPC response
        # Build a dialogue-specific prompt
        dialogue_prompt = f"""Você é {npc_id}, um NPC no escritório Hermes-Corp.
Contexto do jogador: {user_text}
Conhecimento do NPC: {' '.join(npc_context[:3]) if npc_context else 'Nenhum contexto específico'}
Contexto adicional: {context}

Responda como este NPC faria - personalidade baseada no seu role (dev/devops/researcher/watchdog/ceo).
Retorne em formato JSON com: text (resposta), emotion (neutral/happy/excited/concerned/angry), actions (lista de ações como move, spawn_artifact, schedule_meeting, change_behavior)."""
        
        # Generate response via synthesizer (using it as LLM interface)
        # For now, template-based response based on NPC role
        role = "dev"
        if "devops" in npc_id.lower():
            role = "devops"
        elif "researcher" in npc_id.lower():
            role = "researcher"
        elif "watchdog" in npc_id.lower():
            role = "watchdog"
        elif "ceo" in npc_id.lower() or "player" in npc_id.lower():
            role = "ceo"
        
        # Role-based personality responses
        role_responses = {
            "dev": {
                "greeting": "Oi! Tava no meio de um refactor aqui... o que foi?",
                "emotion": "neutral",
                "keywords": ["código", "bug", "feature", "deploy", "test", "refactor"]
            },
            "devops": {
                "greeting": "E aí! Servidores estão estáveis, deploy rodando liso. Precisa de algo?",
                "emotion": "neutral",
                "keywords": ["servidor", "deploy", "CI/CD", "docker", "kubernetes", "monitoring"]
            },
            "researcher": {
                "greeting": "Olá! Acabei de encontrar um paper interessante sobre otimização de tokens... Como posso ajudar?",
                "emotion": "excited",
                "keywords": ["pesquisa", "paper", "otimização", "benchmark", "análise", "dados"]
            },
            "watchdog": {
                "greeting": "Sistema nominal. Alertas: zero. O que você precisa?",
                "emotion": "neutral",
                "keywords": ["alerta", "monitoramento", "health check", "uptime", "incidente", "segurança"]
            },
            "ceo": {
                "greeting": "Bom te ver. A equipe tá produtiva hoje. Em que posso ajudar?",
                "emotion": "happy",
                "keywords": ["prioridade", "roadmap", "equipe", "entrega", "estratégia", "decisão"]
            }
        }
        
        personality = role_responses.get(role, role_responses["dev"])
        
        # Simple keyword matching to determine response type
        user_lower = user_text.lower()
        actions = []
        emotion = personality["emotion"]
        response_text = personality["greeting"]
        
        # Check for specific intents
        if any(k in user_lower for k in ["move", "vai", "anda", "caminha", "vá para"]):
            # Extract target position (simplified)
            actions.append(DialogueAction(type="change_behavior", behavior="moving").model_dump())
            response_text = f"Vou até lá. {personality['greeting']}"
            emotion = "excited"
        elif any(k in user_lower for k in ["reunião", "meeting", "call", "sync"]):
            actions.append(DialogueAction(type="schedule_meeting", meeting={"topic": "Team sync"}).model_dump())
            response_text = f"Marca a reunião então. {personality['greeting']}"
            emotion = "neutral"
        elif any(k in user_lower for k in ["para", "para aí", "espera", "wait", "stop"]):
            actions.append(DialogueAction(type="change_behavior", behavior="idle").model_dump())
            response_text = "Parado. Aguardando ordens."
            emotion = "neutral"
        elif "?" in user_text:
            response_text = f"Boa pergunta. {personality['greeting']} Sobre isso: baseado no que sei, {' '.join(npc_context[:2]) if npc_context else 'preciso pesquisar mais'}."
            emotion = "excited"
        
        return DialogueResponse(
            text=response_text,
            emotion=emotion,
            actions=[DialogueAction(**a) for a in actions],
            metadata={
                "npc_id": npc_id,
                "role": role,
                "sources_used": len(sources),
                "context_keys": list(context.keys())
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/entity/{entity}")
async def get_entity(entity: str):
    """Get entity details from graph."""
    try:
        relations = app_state.graph_index.get_relations(entity)
        chunks = app_state.graph_index.get_entity_chunks(entity)
        
        return {
            "entity": entity,
            "relations": relations,
            "chunks": list(chunks),
            "chunk_count": len(chunks)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_stats():
    """Get system statistics."""
    return {
        "vector_store": app_state.vector_store.get_stats() if app_state.vector_store else {},
        "lexical_index": app_state.lexical_index.get_stats() if app_state.lexical_index else {},
        "graph_index": app_state.graph_index.get_stats() if app_state.graph_index else {},
        "scheduler": app_state.scheduler.get_status() if app_state.scheduler else {}
    }


@app.get("/plan")
async def get_plan(query: str):
    """Get query execution plan without executing."""
    plan = app_state.query_planner.plan(query)
    return {
        "plan": plan.to_dict(),
        "explanation": app_state.query_planner.explain_plan(plan)
    }


# ============================================================
# BACKGROUND TASKS
# ============================================================

async def run_full_reindex():
    """Background task for full reindex."""
    print("🔄 Starting full reindex...")
    if app_state.scheduler:
        stats = app_state.scheduler.trigger_full_reindex()
        print(f"✅ Full reindex completed: {stats}")
    else:
        print("⚠️ Scheduler not available for full reindex")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    uvicorn.run(
        "api_gateway:app",
        host="127.0.0.1",
        port=8766,
        reload=True,
        log_level="info"
    )