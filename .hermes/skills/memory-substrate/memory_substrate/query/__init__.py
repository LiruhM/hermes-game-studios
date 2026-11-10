"""
Memory Substrate v1.0 — Query Engine Package
Main entry point for the query engine.
"""

from .planner import QueryPlanner, QueryPlan, QueryEntity, QueryFilter, QueryIntent, QuerySource, create_query_planner
from .retriever import Retriever, RetrievalConfig, RetrievalMode, RetrievalResult, create_retriever
from .reranker import Reranker, RerankerConfig, RerankResult, create_reranker
from .synthesizer import Synthesizer, SynthesizerConfig, SynthesizedAnswer, CitationStyle, OutputFormat, create_synthesizer
from .context_builder import ContextBuilder, ContextBuilderConfig, ContextSegment, ContextPriority, create_context_builder

__version__ = "1.0.0"
__all__ = [
    # Planner
    "QueryPlanner",
    "QueryPlan",
    "QueryEntity",
    "QueryFilter",
    "QueryIntent",
    "QuerySource",
    "create_query_planner",
    # Retriever
    "Retriever",
    "RetrievalConfig",
    "RetrievalMode",
    "RetrievalResult",
    "create_retriever",
    # Reranker
    "Reranker",
    "RerankerConfig",
    "RerankResult",
    "create_reranker",
    # Synthesizer
    "Synthesizer",
    "SynthesizerConfig",
    "SynthesizedAnswer",
    "CitationStyle",
    "OutputFormat",
    "create_synthesizer",
    # Context Builder
    "ContextBuilder",
    "ContextBuilderConfig",
    "ContextSegment",
    "ContextPriority",
    "create_context_builder"
]