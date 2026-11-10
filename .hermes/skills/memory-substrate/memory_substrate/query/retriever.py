"""
Memory Substrate v1.0 — Query Engine: Retriever
Hybrid retrieval combining vector, lexical, and graph search.
"""

import json
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
import time


class RetrievalMode(str, Enum):
    VECTOR = "vector"
    LEXICAL = "lexical"
    GRAPH = "graph"
    HYBRID = "hybrid"
    AUTO = "auto"


@dataclass
class RetrievalConfig:
    vector_top_k: int = 50
    lexical_top_k: int = 50
    graph_max_depth: int = 3
    graph_max_nodes: int = 100
    fusion_method: str = "rrf"  # rrf | weighted | reciprocal
    fusion_weights: Dict[str, float] = field(default_factory=lambda: {
        "vector": 0.5,
        "lexical": 0.3,
        "graph": 0.2
    })
    min_score_threshold: float = 0.0
    enable_reranking: bool = True
    deduplicate: bool = True
    max_final_results: int = 20


@dataclass
class RetrievalResult:
    chunk_id: str
    source: str
    score: float
    match_types: Dict[str, float]  # vector: 0.8, lexical: 0.6, etc.
    metadata: Dict = field(default_factory=dict)
    content: str = ""
    highlights: List[str] = field(default_factory=list)


class Retriever:
    """
    Hybrid retriever combining vector, lexical, and graph search.
    Supports RRF fusion, weighted fusion, and configurable strategies.
    """
    
    def __init__(
        self, 
        vector_store,
        lexical_index,
        graph_index,
        embedding_engine,
        config: RetrievalConfig = None
    ):
        self.vector_store = vector_store
        self.lexical_index = lexical_index
        self.graph_index = graph_index
        self.embedding_engine = embedding_engine
        self.config = config or RetrievalConfig()
    
    # ============================================================
    # MAIN RETRIEVAL METHOD
    # ============================================================
    
    def retrieve(
        self,
        query: str,
        query_embedding: np.ndarray = None,
        plan = None,  # QueryPlan
        mode: RetrievalMode = RetrievalMode.AUTO,
        filters: Dict = None,
        top_k: int = None
    ) -> List[RetrievalResult]:
        """
        Main retrieval entry point.
        
        Args:
            query: Natural language query
            query_embedding: Pre-computed embedding (optional)
            plan: QueryPlan with intent, entities, filters
            mode: Retrieval mode
            filters: Additional metadata filters
            top_k: Override max results
            
        Returns:
            List of RetrievalResult sorted by combined score
        """
        start_time = time.time()
        top_k = top_k or self.config.max_final_results
        
        # Generate embedding if not provided
        if query_embedding is None and self.embedding_engine:
            query_embedding = self.embedding_engine.encode(query)
        
        # Determine retrieval mode
        if mode == RetrievalMode.AUTO:
            mode = self._determine_mode(query)
        
        # Retrieve from each source
        vector_results = []
        lexical_results = []
        graph_results = []
        
        # Vector search
        if mode in (RetrievalMode.VECTOR, RetrievalMode.HYBRID, RetrievalMode.AUTO):
            if query_embedding is not None:
                vector_results = self._search_vector(query_embedding, plan, filters)
        
        # Lexical search
        if mode in (RetrievalMode.LEXICAL, RetrievalMode.HYBRID, RetrievalMode.AUTO):
            lexical_results = self._search_lexical(query, plan, filters)
        
        # Graph search
        if mode in (RetrievalMode.GRAPH, RetrievalMode.HYBRID, RetrievalMode.AUTO):
            graph_results = self._search_graph(query, plan, filters)
        
        # Fuse results
        fused = self._fuse_results(
            vector_results, lexical_results, graph_results, top_k
        )
        
        # Apply deduplication
        if self.config.deduplicate:
            fused = self._deduplicate(fused)
        
        # Apply minimum score threshold
        fused = [r for r in fused if r.score >= self.config.min_score_threshold]
        
        # Limit results
        fused = fused[:top_k]
        
        # Log timing
        elapsed = time.time() - start_time
        # print(f"Retrieval completed in {time.time() - start_time:.3f}s: {len(fused)} results")
        
        return fused
    
    # ============================================================
    # INDIVIDUAL SEARCH METHODS
    # ============================================================
    
    def _search_vector(
        self, 
        query_embedding: np.ndarray, 
        plan = None,
        filters: Dict = None
    ) -> List[RetrievalResult]:
        """Search vector store using embedding."""
        if not self.vector_store:
            return []
        
        try:
            # Build filter SQL from plan
            filter_sql, filter_params = self._build_filter_sql(plan, filters)
            
            # Search
            results = self.vector_store.search_vector(
                query_embedding=query_embedding,
                k=self.config.vector_top_k,
                filter_sql=filter_sql,
                filter_params=filter_params
            )
            
            # Convert to RetrievalResult
            results_list = []
            for chunk_id, distance in results:
                # Convert distance to similarity score (0-1)
                score = 1.0 / (1.0 + distance)  # Simple conversion
                
                # Get chunk metadata
                chunk = self.vector_store.get(chunk_id)
                if chunk:
                    results_list.append(RetrievalResult(
                        chunk_id=chunk_id,
                        source=chunk.get("source", "unknown"),
                        score=score,
                        match_types={"vector": score},
                        metadata=chunk,
                        content=chunk.get("content", "")[:500]
                    ))
            
            return results_list
            
        except Exception as e:
            print(f"Vector search error: {e}")
            return []
    
    def _search_lexical(
        self, 
        query: str, 
        plan = None,
        filters: Dict = None
    ) -> List[RetrievalResult]:
        """Search lexical index using FTS5."""
        if not self.lexical_index:
            return []
        
        try:
            # Build FTS5 query
            fts_query = self._build_fts_query(query, plan)
            
            # Build filter
            source_filter = None
            if filters and "source" in filters:
                source_filter = filters["source"]
            
            # Search
            results = self.lexical_index.search(
                query=fts_query,
                k=self.config.lexical_top_k,
                source=source_filter,
                highlight=True
            )
            
            # Convert to RetrievalResult
            results_list = []
            for r in results:
                # BM25 score normalization (lower is better in BM25)
                bm25_score = r.get("score", 0)
                score = 1.0 / (1.0 + bm25_score)
                
                results_list.append(RetrievalResult(
                    chunk_id=r["id"],
                    source=r.get("source", "unknown"),
                    score=score,
                    match_types={"lexical": score},
                    metadata={
                        "source_id": r.get("source_id"),
                        "title": r.get("title"),
                        "tags": r.get("tags", []),
                        "entities": r.get("entities", [])
                    },
                    content=r.get("content", "")[:500],
                    highlights=r.get("highlights", [])
                ))
            
            return results_list
            
        except Exception as e:
            print(f"Lexical search error: {e}")
            return []
    
    def _search_graph(
        self, 
        query: str, 
        plan = None,
        filters: Dict = None
    ) -> List[RetrievalResult]:
        """Search graph index for entity relationships."""
        if not self.graph_index:
            return []
        
        try:
            # Extract entities from query
            entities = self.graph_index.extract_entities_from_text(query)
            
            # Also use entities from plan
            if plan and hasattr(plan, 'entities'):
                for e in plan.entities:
                    entities.append(e.text.lower())
            
            results_list = []
            
            # Search for each entity
            for entity in entities[:10]:  # Limit entities
                # Search graph for entity
                entity_results = self.graph_index.search_entities(entity, limit=10)
                
                for er in entity_results:
                    entity_name = er["entity"]
                    count = er["count"]
                    
                    # Score based on entity popularity
                    score = min(1.0, count / 100.0)
                    
                    # Get chunks containing this entity
                    chunk_ids = self.graph_index.get_entity_chunks(entity_name)
                    
                    for chunk_id in list(chunk_ids)[:5]:  # Limit per entity
                        # Get chunk from vector store
                        chunk = None
                        if self.vector_store:
                            chunk = self.vector_store.get(chunk_id)
                        
                        if chunk:
                            results_list.append(RetrievalResult(
                                chunk_id=chunk_id,
                                source=chunk.get("source", "unknown"),
                                score=score * 0.8,  # Graph results slightly lower weight
                                match_types={"graph": score},
                                metadata={
                                    **chunk,
                                    "matched_entity": entity_name,
                                    "entity_count": count
                                },
                                content=chunk.get("content", "")[:500]
                            ))
            
            return results_list
            
        except Exception as e:
            print(f"Graph search error: {e}")
            return []
    
    # ============================================================
    # FUSION METHODS
    # ============================================================
    
    def _fuse_results(
        self,
        vector_results: List[RetrievalResult],
        lexical_results: List[RetrievalResult],
        graph_results: List[RetrievalResult],
        top_k: int
    ) -> List[RetrievalResult]:
        """Fuse results from multiple sources using RRF or weighted fusion."""
        
        if self.config.fusion_method == "rrf":
            return self._rrf_fusion(vector_results, lexical_results, graph_results, top_k)
        elif self.config.fusion_method == "weighted":
            return self._weighted_fusion(vector_results, lexical_results, graph_results, top_k)
        else:
            return self._reciprocal_fusion(vector_results, lexical_results, graph_results, top_k)
    
    def _rrf_fusion(
        self,
        vector_results: List[RetrievalResult],
        lexical_results: List[RetrievalResult],
        graph_results: List[RetrievalResult],
        top_k: int
    ) -> List[RetrievalResult]:
        """
        Reciprocal Rank Fusion (RRF) for combining ranked lists.
        Score = sum(1 / (rank + k)) for each source
        """
        k = 60  # RRF parameter
        scores = {}
        sources_data = {}
        
        # Process vector results
        for rank, result in enumerate(vector_results):
            key = result.chunk_id
            if key not in scores:
                scores[key] = 0
                sources_data[key] = {**result.metadata, "content": result.content}
                sources_data[key]["match_types"] = {}
            
            scores[key] += 1.0 / (rank + 1 + k)
            sources_data[key]["match_types"]["vector"] = result.score
        
        # Process lexical results
        for rank, result in enumerate(lexical_results):
            key = result.chunk_id
            if key not in scores:
                scores[key] = 0
                sources_data[key] = {**result.metadata, "content": result.content}
                sources_data[key]["match_types"] = {}
            
            scores[key] += 1.0 / (rank + 1 + k)
            sources_data[key]["match_types"]["lexical"] = result.score
        
        # Process graph results
        for rank, result in enumerate(graph_results):
            key = result.chunk_id
            if key not in scores:
                scores[key] = 0
                sources_data[key] = {**result.metadata, "content": result.content}
                sources_data[key]["match_types"] = {}
            
            scores[key] += 1.0 / (rank + 1 + k)
            sources_data[key]["match_types"]["graph"] = result.score
        
        # Sort by RRF score
        sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # Build final results
        results = []
        for chunk_id, score in sorted_items[:top_k]:
            data = sources_data[chunk_id]
            results.append(RetrievalResult(
                chunk_id=chunk_id,
                source=data.get("source", "unknown"),
                score=score,
                match_types=data.get("match_types", {}),
                metadata={k: v for k, v in data.items() if k not in ["content", "match_types"]},
                content=data.get("content", "")
            ))
        
        return results
    
    def _weighted_fusion(
        self,
        vector_results: List[RetrievalResult],
        lexical_results: List[RetrievalResult],
        graph_results: List[RetrievalResult],
        top_k: int
    ) -> List[RetrievalResult]:
        """Weighted score fusion."""
        weights = self.config.fusion_weights
        scores = {}
        sources_data = {}
        
        # Vector results
        for result in vector_results:
            key = result.chunk_id
            if key not in scores:
                scores[key] = 0
                sources_data[key] = {**result.metadata, "content": result.content}
                sources_data[key]["match_types"] = {}
            
            scores[key] += result.score * weights.get("vector", 0.5)
            sources_data[key]["match_types"]["vector"] = result.score
        
        # Lexical results
        for result in lexical_results:
            key = result.chunk_id
            if key not in scores:
                scores[key] = 0
                sources_data[key] = {**result.metadata, "content": result.content}
                sources_data[key]["match_types"] = {}
            
            scores[key] += result.score * weights.get("lexical", 0.3)
            sources_data[key]["match_types"]["lexical"] = result.score
        
        # Graph results
        for result in graph_results:
            key = result.chunk_id
            if key not in scores:
                scores[key] = 0
                sources_data[key] = {**result.metadata, "content": result.content}
                sources_data[key]["match_types"] = {}
            
            scores[key] += result.score * weights.get("graph", 0.2)
            sources_data[key]["match_types"]["graph"] = result.score
        
        # Sort and return
        sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        results = []
        for chunk_id, score in sorted_items[:top_k]:
            data = sources_data[chunk_id]
            results.append(RetrievalResult(
                chunk_id=chunk_id,
                source=data.get("source", "unknown"),
                score=score,
                match_types=data.get("match_types", {}),
                metadata={k: v for k, v in data.items() if k not in ["content", "match_types"]},
                content=data.get("content", "")
            ))
        
        return results
    
    def _reciprocal_fusion(
        self,
        vector_results: List[RetrievalResult],
        lexical_results: List[RetrievalResult],
        graph_results: List[RetrievalResult],
        top_k: int
    ) -> List[RetrievalResult]:
        """Simple reciprocal fusion (1/rank)."""
        return self._rrf_fusion(vector_results, lexical_results, graph_results, top_k)
    
    # ============================================================
    # HELPER METHODS
    # ============================================================
    
    def _determine_mode(self, query: str) -> RetrievalMode:
        """Auto-determine retrieval mode from query."""
        query_lower = query.lower()
        
        # Graph indicators
        graph_keywords = ["conecta", "relaciona", "tunnel", "túnel", "grafo", "entidade", "ligação"]
        if any(kw in query_lower for kw in graph_keywords):
            return RetrievalMode.HYBRID
        
        # Lexical indicators (exact phrases, quotes)
        if '"' in query or "'" in query or any(op in query_lower for op in ["and", "or", "not", "near"]):
            return RetrievalMode.HYBRID
        
        # Vector indicators (semantic, conceptual)
        vector_keywords = ["semelhante", "similar", "parecido", "conceito", "ideia", "significado"]
        if any(kw in query_lower for kw in vector_keywords):
            return RetrievalMode.VECTOR
        
        return RetrievalMode.HYBRID
    
    def _build_filter_sql(self, plan, filters: Dict) -> Tuple[str, Tuple]:
        """Build SQL filter from plan and filters."""
        conditions = []
        params = []
        
        if plan and hasattr(plan, 'filters'):
            for f in plan.filters:
                if f.operator == "eq":
                    conditions.append(f"{f.field} = ?")
                    params.append(f.value)
                elif f.operator == "in":
                    placeholders = ",".join(["?"] * len(f.value))
                    conditions.append(f"{f.field} IN ({placeholders})")
                    params.extend(f.value)
                elif f.operator == "contains":
                    conditions.append(f"{f.field} LIKE ?")
                    params.append(f"%{f.value}%")
        
        if filters:
            for key, value in filters.items():
                if key == "source":
                    conditions.append("source = ?")
                    params.append(value)
                elif key == "para_category":
                    conditions.append("para_category = ?")
                    params.append(value)
                elif key == "wing":
                    conditions.append("wing = ?")
                    params.append(value)
                elif key == "tags":
                    if isinstance(value, list):
                        for tag in value:
                            conditions.append("tags LIKE ?")
                            params.append(f"%{tag}%")
                    else:
                        conditions.append("tags LIKE ?")
                        params.append(f"%{value}%")
        
        sql = " AND ".join(conditions) if conditions else ""
        return sql, tuple(params)
    
    def _build_fts_query(self, query: str, plan) -> str:
        """Build FTS5 query from natural language."""
        # Use query as-is for FTS5 (it handles phrases, NOT, AND, OR, NEAR)
        # Could enhance with entity boosting
        return query
    
    def _deduplicate(self, results: List[RetrievalResult]) -> List[RetrievalResult]:
        """Remove duplicate chunk_ids, keeping highest scoring."""
        seen = {}
        for result in results:
            key = result.chunk_id
            if key not in seen or result.score > seen[key].score:
                seen[key] = result
        return list(seen.values())


# ============================================================
# FACTORY
# ============================================================

def create_retriever(
    vector_store,
    lexical_index,
    graph_index,
    embedding_engine,
    config: RetrievalConfig = None
) -> Retriever:
    """Create retriever with default or custom config."""
    if config is None:
        config = RetrievalConfig()
    return Retriever(vector_store, lexical_index, graph_index, embedding_engine, config)