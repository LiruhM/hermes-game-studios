"""
Memory Substrate v1.0 — Query Engine: Reranker
Cross-encoder reranking for precision improvement.
"""

import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
import numpy as np


@dataclass
class RerankerConfig:
    model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    device: str = "auto"  # auto | cpu | cuda
    batch_size: int = 16
    max_length: int = 512
    top_k: int = 10
    threshold: float = 0.0  # Minimum score to keep
    normalize: bool = True
    cache_enabled: bool = True


@dataclass
class RerankResult:
    chunk_id: str
    score: float
    original_score: float
    metadata: Dict = None
    content: str = ""


class Reranker:
    """
    Cross-encoder reranker for improving retrieval precision.
    Uses a cross-encoder model to re-score query-document pairs.
    """
    
    def __init__(self, config: RerankerConfig = None):
        self.config = config or RerankerConfig()
        self._model = None
        self._device = self._resolve_device()
        self._cache: Dict[str, float] = {}
        self._init_cache()
    
    def _resolve_device(self) -> str:
        if self.config.device != "auto":
            return self.config.device
        
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            pass
        return "cpu"
    
    def _init_cache(self):
        """Initialize score cache."""
        if self.config.cache_enabled:
            pass  # Could add persistent cache
    
    def _get_model(self):
        """Lazy load the cross-encoder model."""
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
                self._model = CrossEncoder(
                    self.config.model_name,
                    device=self._device,
                    max_length=self.config.max_length
                )
            except ImportError:
                raise ImportError(
                    "sentence-transformers not installed. "
                    "Install with: pip install sentence-transformers"
                )
        return self._model
    
    def _get_cache_key(self, query: str, text: str) -> str:
        """Generate cache key for query-document pair."""
        import hashlib
        combined = f"{query}|||{text}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    def rerank(
        self,
        query: str,
        candidates: List[Dict],
        top_k: int = None,
        return_scores: bool = True
    ) -> List[Dict]:
        """
        Rerank candidates using cross-encoder.
        
        Args:
            query: Query string
            candidates: List of candidate dicts with 'content' and 'chunk_id'
            top_k: Number of top results to return
            return_scores: Whether to include rerank scores
            
        Returns:
            Reranked candidates with updated scores
        """
        if not candidates:
            return []
        
        top_k = top_k or self.config.top_k
        
        # Prepare pairs for cross-encoder
        pairs = []
        valid_candidates = []
        
        for cand in candidates:
            content = cand.get("content", "") or cand.get("text", "")
            if not content:
                continue
            
            # Truncate content if too long
            if len(content) > self.config.max_length * 4:  # rough char estimate
                content = content[:self.config.max_length * 4]
            
            # Check cache
            cache_key = self._get_cache_key(query, content)
            if cache_key in self._cache:
                cached_score = self._cache[cache_key]
                cand["rerank_score"] = cached_score
                valid_candidates.append(cand)
            else:
                pairs.append((query, content))
                valid_candidates.append(cand)
        
        if not pairs:
            return valid_candidates[:top_k]
        
        # Get cross-encoder scores
        model = self._get_model()
        scores = model.predict(pairs, batch_size=self.config.batch_size, show_progress_bar=False)
        
        # Update candidates with scores
        for cand, score in zip(valid_candidates, scores):
            score = float(score)
            
            # Apply sigmoid if needed (some models output logits)
            if score < -10 or score > 10:
                score = 1 / (1 + np.exp(-score))
            
            # Normalize to 0-1 if needed
            if self.config.normalize and (score < 0 or score > 1):
                score = 1 / (1 + np.exp(-score))
            
            cand["rerank_score"] = float(score)
            
            # Update cache
            content = cand.get("content", "") or cand.get("text", "")
            cache_key = self._get_cache_key(query, content)
            self._cache[cache_key] = float(score)
        
        # Sort by rerank score
        valid_candidates.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
        
        # Apply threshold
        if self.config.threshold > 0:
            valid_candidates = [c for c in valid_candidates if c.get("rerank_score", 0) >= self.config.threshold]
        
        # Return top_k
        results = valid_candidates[:top_k]
        
        return results
    
    def rerank_with_original_scores(
        self,
        query: str,
        candidates: List[Dict],
        alpha: float = 0.7,
        top_k: int = None
    ) -> List[Dict]:
        """
        Rerank combining original retrieval score with cross-encoder score.
        
        Combined score = alpha * rerank_score + (1 - alpha) * original_score
        """
        top_k = top_k or self.config.top_k
        
        # First rerank
        reranked = self.rerank(query, candidates, top_k=len(candidates), return_scores=True)
        
        # Combine scores
        for cand in reranked:
            original_score = cand.get("score", cand.get("original_score", 0))
            rerank_score = cand.get("rerank_score", 0)
            
            # Normalize original score if needed
            if original_score > 1:
                original_score = 1 / (1 + original_score)
            
            combined = alpha * rerank_score + (1 - alpha) * original_score
            cand["combined_score"] = combined
            cand["original_score"] = original_score
        
        # Sort by combined score
        reranked.sort(key=lambda x: x.get("combined_score", 0), reverse=True)
        
        return reranked[:top_k]
    
    def score_pairs(self, pairs: List[Tuple[str, str]]) -> np.ndarray:
        """Score query-document pairs directly."""
        model = self._get_model()
        scores = model.predict(pairs, batch_size=self.config.batch_size)
        return np.array([float(s) for s in scores])
    
    def clear_cache(self):
        """Clear score cache."""
        self._cache.clear()
    
    def get_stats(self) -> Dict:
        """Get reranker statistics."""
        return {
            "model": self.config.model_name,
            "device": self._device,
            "batch_size": self.config.batch_size,
            "cache_size": len(self._cache),
            "max_length": self.config.max_length
        }


# ============================================================
# FACTORY
# ============================================================

def create_reranker(config: RerankerConfig = None) -> Reranker:
    """Create reranker with default or custom config."""
    if config is None:
        config = RerankerConfig()
    return Reranker(config)