"""
Memory Substrate v1.0 — Embedding Engine
Generates embeddings using sentence-transformers with local models.
"""

import os
import numpy as np
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json


@dataclass
class EmbeddingConfig:
    model_name: str = "all-MiniLM-L6-v2"
    dimensions: int = 384
    device: str = "auto"  # auto | cpu | cuda | mps
    batch_size: int = 32
    normalize: bool = True
    cache_dir: str = None
    max_seq_length: int = 512
    show_progress: bool = False
    # BLUEPRINT-P2-MEMORIA §5: cache de embedding persiste em disco junto ao
    # persist do vector_store.py (mesmo diretório 90-Sistema/_embeddings/).
    embedding_cache_path: str = "90-Sistema/_embeddings/embedding_cache.json"

    def __post_init__(self):
        if self.cache_dir is None:
            self.cache_dir = str(Path.home() / ".cache" / "sentence_transformers")


class EmbeddingEngine:
    """
    Generates embeddings using sentence-transformers.
    Supports local models with caching and batch processing.

    BLUEPRINT-P2-MEMORIA §5 — cache por hash:
    O cache (sha256(texto normalizado) -> embedding 384) vive AQUI, no
    EmbeddingEngine (único dono do modelo), checado ANTES de qualquer
    inferência e persistente entre restarts (JSON junto ao vector_store).
    Isso protege TODOS os consumidores (store, /dialogue, recall).
    """
    
    def __init__(self, config: EmbeddingConfig = None):
        self.config = config or EmbeddingConfig()
        self._model = None
        self._device = self._resolve_device()
        self._embedding_cache: Dict[str, np.ndarray] = {}
        self._cache_file = None
        self.inference_count = 0  # nº de inferências reais (p/ M4/testes)
        self.cache_hit_count = 0  # nº de hits servidos do cache (p/ M4)
        self._init_cache()
    
    def _resolve_device(self) -> str:
        """Resolve device from config."""
        if self.config.device != "auto":
            return self.config.device
        
        # Auto-detect
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
        """Initialize embedding cache (in-memory + persistent on disk)."""
        # BLUEPRINT-P2 §5: persist junto ao vector_store.py
        cache_file = Path(self.config.embedding_cache_path)
        try:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            self._cache_file = cache_file
        except Exception:
            self._cache_file = None

        if self._cache_file and self._cache_file.exists():
            try:
                with open(self._cache_file, 'r') as f:
                    data = json.load(f)
                    self._embedding_cache = {
                        k: np.array(v, dtype=np.float32)
                        for k, v in data.items()
                    }
            except Exception:
                self._embedding_cache = {}

        if self.config.cache_dir:
            cache_dir = Path(self.config.cache_dir)
            cache_dir.mkdir(parents=True, exist_ok=True)
            # cache_dir holds the sentence-transformers model itself; the
            # embedding cache lives in embedding_cache_path (vector_store dir).
    
    def _save_cache(self):
        """Save embedding cache to disk."""
        if self._cache_file:
            try:
                data = {
                    k: v.tolist() 
                    for k, v in self._embedding_cache.items()
                }
                with open(self._cache_file, 'w') as f:
                    json.dump(data, f)
            except Exception:
                pass
    
    def _get_model(self):
        """Lazy load the sentence-transformers model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(
                    self.config.model_name,
                    device=self._device,
                    cache_folder=self.config.cache_dir
                )
                # Set max sequence length
                if hasattr(self._model, 'max_seq_length'):
                    self._model.max_seq_length = self.config.max_seq_length
            except ImportError:
                raise ImportError(
                    "sentence-transformers not installed. "
                    "Install with: pip install sentence-transformers"
                )
        return self._model
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text.

        BLUEPRINT-P2 §5: sha256 do TEXTO NORMALIZADO (strip + collapse
        espaços internos) — textos que diferem só em whitespace não geram
        inferências duplicadas.
        """
        normalized = " ".join(text.strip().split())
        return hashlib.sha256(normalized.encode()).hexdigest()

    def get_embedding(self, text: str) -> tuple:
        """BLUEPRINT-P2 §3/§5 — retorna (embedding, cached_flag).

        Consulta o cache por hash ANTES de qualquer inferência. É a porta
        única usada pelo gateway (/memory/store) para saber se o embedding
        veio do cache (`cached=true`) sem vazar detalhes do engine.
        """
        cache_key = self._get_cache_key(text)
        cached = cache_key in self._embedding_cache
        if cached:
            self.cache_hit_count += 1
            return self._embedding_cache[cache_key], True

        # Miss: encode() roda a inferência real (e conta em inference_count)
        emb = self.encode(text)
        if isinstance(emb, np.ndarray):
            emb = np.asarray(emb, dtype=np.float32)
        return emb, False
    
    def encode(
        self, 
        texts: Union[str, List[str]], 
        batch_size: int = None,
        show_progress: bool = None,
        convert_to_numpy: bool = True,
        convert_to_tensor: bool = False,
        normalize_embeddings: bool = None
    ) -> Union[np.ndarray, List[np.ndarray]]:
        """
        Encode texts to embeddings.
        
        Args:
            texts: Single text or list of texts
            batch_size: Batch size for processing
            show_progress: Show progress bar
            convert_to_numpy: Return as numpy array
            convert_to_tensor: Return as torch tensor
            normalize_embeddings: Normalize to unit length
            
        Returns:
            Embeddings as numpy array (n_texts, dimensions) or list of arrays
        """
        # Normalize input
        if isinstance(texts, str):
            texts = [texts]
            single = True
        else:
            single = False
        
        batch_size = batch_size or self.config.batch_size
        show_progress = show_progress if show_progress is not None else self.config.show_progress
        normalize = normalize_embeddings if normalize_embeddings is not None else self.config.normalize
        
        # Check cache for single texts
        results = []
        uncached_texts = []
        uncached_indices = []
        cached_any = False  # tracks if at least one hit happened this call

        for i, text in enumerate(texts):
            cache_key = self._get_cache_key(text)
            if cache_key in self._embedding_cache:
                results.append(self._embedding_cache[cache_key])
                uncached_texts.append(None)  # Placeholder to keep index sync
                uncached_indices.append(None)
                cached_any = True
            else:
                uncached_texts.append(text)
                uncached_indices.append(i)
                results.append(None)  # Placeholder

        # Drop placeholder Nones (texts kept in order via uncached_indices)
        uncached = [(idx, t) for idx, t in zip(uncached_indices, uncached_texts) if t is not None]
        uncached_texts = [t for _, t in uncached]
        uncached_indices = [idx for idx, _ in uncached]
        if cached_any:
            self.cache_hit_count += 1

        # Encode uncached texts
        if uncached_texts:
            self.inference_count += 1
            model = self._get_model()
            new_embeddings = model.encode(
                uncached_texts,
                batch_size=batch_size,
                show_progress_bar=show_progress,
                convert_to_numpy=True,
                normalize_embeddings=normalize
            )
            
            # Fill in results and update cache
            for idx, embedding in zip(uncached_indices, new_embeddings):
                results[idx] = embedding
                cache_key = self._get_cache_key(texts[idx])
                self._embedding_cache[cache_key] = embedding
            
            # Save cache on every write (BLUEPRINT-P2: persistente desde a 1ª inferência)
            self._save_cache()
        elif cached_any:
            # All hits: nothing new to persist (cache file unchanged)
            pass
        
        # Convert to requested format
        if convert_to_tensor:
            try:
                import torch
                return torch.tensor(np.stack(results))
            except ImportError:
                pass
        
        if single:
            return results[0]
        
        if convert_to_numpy:
            return np.stack(results)
        
        return results
    
    def encode_single(self, text: str, **kwargs) -> np.ndarray:
        """Encode a single text to embedding."""
        return self.encode(text, **kwargs)
    
    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two embeddings."""
        # Assumes normalized embeddings
        return float(np.dot(a, b))
    
    def similarities(self, query: np.ndarray, candidates: np.ndarray) -> np.ndarray:
        """Compute similarities between query and multiple candidates."""
        # query: (dim,), candidates: (n, dim)
        # Returns: (n,) similarities
        return np.dot(candidates, query)
    
    def get_dimensions(self) -> int:
        """Get embedding dimensions."""
        return self.config.dimensions
    
    def get_model_info(self) -> Dict:
        """Get model information."""
        return {
            "model_name": self.config.model_name,
            "dimensions": self.config.dimensions,
            "device": self._device,
            "max_seq_length": self.config.max_seq_length,
            "cache_size": len(self._embedding_cache)
        }
    
    def clear_cache(self):
        """Clear embedding cache."""
        self._embedding_cache = {}
        self._save_cache()
    
    def __del__(self):
        """Save cache on destruction."""
        self._save_cache()


# ============================================================
# FACTORY
# ============================================================

def create_embedding_engine(config: EmbeddingConfig = None) -> EmbeddingEngine:
    """Create embedding engine with default or custom config."""
    if config is None:
        config = EmbeddingConfig()
    return EmbeddingEngine(config)