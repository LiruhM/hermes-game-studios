"""
Memory Substrate v1.0 — Unified Memory Layer
Main entry point for the Memory Substrate skill.
"""

from typing import Dict

from .adapters import (
    VaultAdapter, create_vault_adapter,
    MemPalaceAdapter, create_mempalace_adapter,
    SkillAdapter, create_skill_adapter
)
from .indexing import (
    VectorStore, create_vector_store,
    LexicalIndex, create_lexical_index,
    GraphIndex, create_graph_index,
    EmbeddingEngine, create_embedding_engine,
    IndexScheduler, create_scheduler,
    Chunker, create_chunker,
    ChunkerConfig, ChunkingStrategy
)
from .query import (
    QueryPlanner, create_query_planner,
    Retriever, create_retriever,
    Reranker, create_reranker,
    Synthesizer, create_synthesizer,
    ContextBuilder, create_context_builder
)
from .models import (
    MemoryChunk, SkillManifest, SearchResult, QueryPlan, SynthesizedAnswer
)
from .api_gateway import app

__version__ = "1.0.0"
__all__ = [
    # Adapters
    "VaultAdapter", "create_vault_adapter",
    "MemPalaceAdapter", "create_mempalace_adapter",
    "SkillAdapter", "create_skill_adapter",
    # Indexing
    "VectorStore", "create_vector_store",
    "LexicalIndex", "create_lexical_index",
    "GraphIndex", "create_graph_index",
    "EmbeddingEngine", "create_embedding_engine",
    "IndexScheduler", "create_scheduler",
    "Chunker", "create_chunker", "ChunkerConfig", "ChunkingStrategy",
    # Query
    "QueryPlanner", "create_query_planner",
    "Retriever", "create_retriever",
    "Reranker", "create_reranker",
    "Synthesizer", "create_synthesizer",
    "ContextBuilder", "create_context_builder",
    # Models
    "MemoryChunk", "SkillManifest", "SearchResult", "QueryPlan", "SynthesizedAnswer",
    # API
    "app"
]

# Convenience function to create full Memory Substrate stack
async def create_memory_substrate(
    vault_path: str = "C:/Users/mathe/Hermes_Brain",
    mempalace_endpoint: str = "http://localhost:8765",
    skills_dir: str = "C:/Users/mathe/AppData/Local/hermes/skills",
    config: Dict = None
) -> Dict:
    """
    Create a complete Memory Substrate stack.
    
    Returns dict with all initialized components.
    """
    # This would be an async factory that initializes everything
    # For now, return component creators
    return {
        "vault_adapter": lambda: create_vault_adapter(vault_path=vault_path),
        "mempalace_adapter": lambda: create_mempalace_adapter(endpoint=mempalace_endpoint),
        "skill_adapter": lambda: create_skill_adapter(skills_dir=skills_dir),
        "vector_store": lambda: create_vector_store(),
        "lexical_index": lambda: create_lexical_index(),
        "graph_index": lambda: create_graph_index(),
        "embedding_engine": lambda: create_embedding_engine(),
        "chunker": lambda: create_chunker(),
        "scheduler": lambda: create_scheduler(),
        "query_planner": lambda: create_query_planner(),
        "retriever": None,  # Needs components
        "reranker": None,   # Needs components
        "synthesizer": None, # Needs components
        "context_builder": lambda: create_context_builder()
    }


def create_memory_substrate_sync(
    vault_path: str = "C:/Users/mathe/Hermes_Brain",
    mempalace_endpoint: str = "http://localhost:8765",
    skills_dir: str = "C:/Users/mathe/AppData/Local/hermes/skills"
) -> Dict:
    """Synchronous factory for Memory Substrate components."""
    return {
        "vault": create_vault_adapter(vault_path=vault_path),
        "mempalace": create_mempalace_adapter(endpoint=mempalace_endpoint),
        "skills": create_skill_adapter(skills_dir=skills_dir),
        "vector_store": create_vector_store(),
        "lexical_index": create_lexical_index(),
        "graph_index": create_graph_index(),
        "embeddings": create_embedding_engine(),
        "chunker": create_chunker(),
        "scheduler": create_scheduler(),
        "planner": create_query_planner(),
        "retriever": None,  # Needs components
        "reranker": None,
        "synthesizer": None,
        "context_builder": create_context_builder()
    }