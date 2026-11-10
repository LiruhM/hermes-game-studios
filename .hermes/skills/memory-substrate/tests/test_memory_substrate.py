"""
Memory Substrate v1.0 — Test Suite
Integration tests for the Memory Substrate components.
"""

import pytest
import tempfile
import os
from pathlib import Path

# Test models
def test_memory_chunk_creation():
    """Test MemoryChunk creation and serialization."""
    from memory_substrate.models import MemoryChunk, SourceType, PARALayer, PARACategory
    
    chunk = MemoryChunk(
        source=SourceType.VAULT,
        source_id="10-Projetos/Teste/README.md",
        content="Test content",
        title="Test",
        para_category=PARACategory.PROJECT,
        para_layer=PARALayer.RESOURCE,
        tags=["test", "project"]
    )
    
    assert chunk.source == SourceType.VAULT
    assert chunk.para_category == PARACategory.PROJECT
    assert chunk.para_layer == PARALayer.RESOURCE
    assert "test" in chunk.tags


def test_skill_manifest():
    """Test SkillManifest creation."""
    from memory_substrate.models import SkillManifest
    
    manifest = SkillManifest(
        name="test-skill",
        version="1.0.0",
        description="Test skill",
        category="test"
    )
    
    assert manifest.name == "test-skill"
    assert manifest.version == "1.0.0"


# Test chunker
def test_fixed_chunker():
    """Test fixed-size chunking."""
    from memory_substrate.indexing import Chunker, ChunkerConfig, ChunkingStrategy
    
    config = ChunkerConfig(
        strategy=ChunkingStrategy.FIXED,
        chunk_size=100,
        chunk_overlap=20
    )
    chunker = Chunker(config)
    
    text = "A" * 300  # 300 chars
    chunks = chunker.chunk(text)
    
    # Should create ~3 chunks (300 / (100-20) = 3.75)
    assert len(chunks) >= 3
    for chunk in chunks:
        assert len(chunk["content"]) <= 100


def test_heading_chunker():
    """Test heading-based chunking for markdown."""
    from memory_substrate.indexing import Chunker, ChunkerConfig, ChunkingStrategy
    
    config = ChunkerConfig(strategy=ChunkingStrategy.HEADING)
    chunker = Chunker(config)
    
    markdown = """# Heading 1
Content for heading 1.

## Heading 2
Content for heading 2.

### Heading 3
Content for heading 3."""
    
    chunks = chunker.chunk(markdown)
    
    assert len(chunks) == 3
    assert chunks[0]["metadata"]["heading"] == "Heading 1"
    assert chunks[1]["metadata"]["heading"] == "Heading 2"
    assert chunks[2]["metadata"]["heading"] == "Heading 3"


# Test embedding engine (mock test - requires model)
def test_embedding_engine_config():
    """Test embedding engine configuration."""
    from memory_substrate.indexing import EmbeddingEngine, EmbeddingConfig
    
    config = EmbeddingConfig(
        model_name="all-MiniLM-L6-v2",
        dimensions=384,
        device="cpu"
    )
    
    # Just test config creation - actual model loading requires download
    assert config.model_name == "all-MiniLM-L6-v2"
    assert config.dimensions == 384


# Test query planner
def test_query_planner():
    """Test query planning."""
    from memory_substrate.query import QueryPlanner, QueryIntent, QuerySource
    
    planner = QueryPlanner()
    
    # Test list intent
    plan = planner.plan("liste todas as skills")
    assert plan.intent == "list"
    
    # Test find intent
    plan = planner.plan("onde está o arquivo de configuração?")
    assert plan.intent == "find"
    
    # Test synthesize intent
    plan = planner.plan("explique como funciona o token optimization")
    assert plan.intent == "synthesize"
    
    # Test traverse intent
    plan = planner.plan("o que conecta o vault ao mempalace?")
    assert plan.intent == "traverse"


# Test query planner entities
def test_query_planner_entities():
    """Test entity extraction."""
    from memory_substrate.query import QueryPlanner
    
    planner = QueryPlanner()
    
    plan = planner.plan("como configurar o token-optimization?")
    
    # Should extract skill entity
    skill_entities = [e for e in plan.entities if e.type == "skill"]
    assert len(skill_entities) > 0
    assert "token-optimization" in skill_entities[0].text


# Test query planner sources
def test_query_planner_sources():
    """Test source determination."""
    from memory_substrate.query import QueryPlanner, QuerySource
    
    planner = QueryPlanner()
    
    # Vault query
    plan = planner.plan("busque no vault sobre token optimization")
    assert "vault" in [s.value for s in plan.sources]
    
    # MemPalace query
    plan = planner.plan("o que tem no mempalace sobre RAG?")
    assert "mempalace" in [s.value for s in plan.sources]
    
    # Skill query
    plan = planner.plan("como usar a skill token-optimization?")
    assert "skill" in [s.value for s in plan.sources]


# Test context builder
def test_context_builder():
    """Test context building."""
    from memory_substrate.query import ContextBuilder, ContextBuilderConfig, ContextPriority
    
    config = ContextBuilderConfig(
        max_context_tokens=1000,
        reserved_for_response=500
    )
    builder = ContextBuilder(config)
    
    # Test token counting
    tokens = builder._count_tokens("Hello world")
    assert tokens > 0
    
    # Test truncation
    long_text = "A" * 10000
    truncated = builder._truncate_text(long_text, 100)
    assert builder._count_tokens(truncated) <= 100


# Test query planner explain
def test_query_planner_explain():
    """Test plan explanation."""
    from memory_substrate.query import QueryPlanner
    
    planner = QueryPlanner()
    plan = planner.plan("liste todas as skills de token optimization")
    
    explanation = planner.explain_plan(plan)
    
    assert "Intent: list" in explanation
    assert "Sources:" in explanation
    assert "Capabilities:" in explanation


# Test models search result
def test_search_result():
    """Test SearchResult model."""
    from memory_substrate.models import SearchResult, MemoryChunk, SourceType
    
    chunk = MemoryChunk(
        source=SourceType.VAULT,
        source_id="test.md",
        content="Test content",
        title="Test"
    )
    
    result = SearchResult(
        chunk=chunk,
        score=0.95,
        match_type="semantic",
        highlights=["test"]
    )
    
    assert result.score == 0.95
    assert result.match_type == "semantic"
    assert "test" in result.highlights


# ============================================================
# INTEGRATION TESTS (require actual services)
# ============================================================

# These tests require running services and are marked as integration
# Run with: pytest -m integration

# @pytest.mark.integration
# def test_vault_adapter_integration():
#     """Test vault adapter with real vault."""
#     from memory_substrate.adapters import create_vault_adapter
#     
#     adapter = create_vault_adapter(vault_path="C:/Users/mathe/Hermes_Brain")
#     files = adapter.list_files("*.md")
#     assert len(files) > 0

# @pytest.mark.integration
# def test_embedding_engine_integration():
#     """Test embedding engine with real model."""
#     from memory_substrate.indexing import create_embedding_engine
#     
#     engine = create_embedding_engine()
#     embeddings = engine.encode(["test query", "another query"])
#     assert embeddings.shape == (2, 384)

# @pytest.mark.integration
# def test_full_pipeline():
#     """Test full query pipeline."""
#     from memory_substrate import create_memory_substrate_sync
#     
#     components = create_memory_substrate_sync()
#     planner = components["planner"]
#     
#     plan = planner.plan("test query")
#     assert plan is not None


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])