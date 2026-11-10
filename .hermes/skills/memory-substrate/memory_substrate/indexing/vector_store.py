"""
Memory Substrate v1.0 — Vector Store
SQLite-vec based vector storage for embeddings with metadata filtering.
Falls back to FAISS when sqlite-vec is not available.
"""

import sqlite3
import json
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import uuid
import os

# Try to import FAISS as fallback
try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False


@dataclass
class VectorStoreConfig:
    db_path: str
    index_type: str = "hnsw"  # hnsw | flat | faiss
    dimensions: int = 384
    hnsw_M: int = 16
    hnsw_ef_construction: int = 200
    hnsw_ef_search: int = 50
    enable_wal: bool = True
    synchronous: str = "NORMAL"  # OFF | NORMAL | FULL
    # FAISS fallback
    faiss_index_path: str = None  # Auto-generated from db_path if None
    
    def __post_init__(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        if self.faiss_index_path is None:
            self.faiss_index_path = self.db_path.replace('.db', '_faiss.index')


class VectorStore:
    """
    Vector store for embeddings.
    Uses sqlite-vec when available, falls back to FAISS.
    Includes metadata filtering capabilities.
    """
    
    def __init__(self, config: VectorStoreConfig):
        self.config = config
        self.conn = None
        self.vec_available = False
        self.faiss_index = None
        self.faiss_id_to_chunk = {}  # FAISS index -> chunk_id mapping
        self._init_db()
    
    def _init_db(self):
        """Initialize database and create tables."""
        self.conn = sqlite3.connect(self.config.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        
        # Enable WAL mode for better concurrency
        if self.config.enable_wal:
            self.conn.execute("PRAGMA journal_mode=WAL")
        
        self.conn.execute(f"PRAGMA synchronous={self.config.synchronous}")
        
        # Try to load sqlite-vec extension
        self._load_vec_extension()
        
        # Create tables
        self._create_tables()
        
        # Create vector index (sqlite-vec or FAISS)
        self._create_vector_index()
    
    def _load_vec_extension(self):
        """Load sqlite-vec extension."""
        try:
            # Try to load sqlite-vec
            self.conn.enable_load_extension(True)
            self.conn.load_extension("sqlite_vec")
            self.vec_available = True
        except Exception:
            # Try alternative paths
            for path in [
                "/usr/lib/sqlite_vec",
                "/usr/local/lib/sqlite_vec",
                "/opt/homebrew/lib/sqlite_vec",
                os.path.expanduser("~/.local/lib/sqlite_vec"),
            ]:
                try:
                    self.conn.load_extension(path)
                    self.vec_available = True
                    break
                except Exception:
                    continue
        
        if not self.vec_available:
            print("Warning: sqlite-vec not available, using FAISS fallback")
            self._init_faiss()
    
    def _init_faiss(self):
        """Initialize FAISS index as fallback."""
        if not FAISS_AVAILABLE:
            raise RuntimeError("Neither sqlite-vec nor FAISS available for vector search")
        
        # Create or load FAISS index
        if os.path.exists(self.config.faiss_index_path):
            self.faiss_index = faiss.read_index(self.config.faiss_index_path)
            # Load ID mapping
            mapping_path = self.config.faiss_index_path + '.mapping'
            if os.path.exists(mapping_path):
                with open(mapping_path, 'r') as f:
                    self.faiss_id_to_chunk = json.load(f)
        else:
            # Create new FAISS index (IndexFlatIP for cosine similarity)
            self.faiss_index = faiss.IndexFlatIP(self.config.dimensions)
            self.faiss_id_to_chunk = {}
        
        # Also initialize FAISS tables
        self._create_faiss_tables()
    
    def _create_tables(self):
        """Create main tables."""
        self.conn.executescript("""
            -- Main embeddings table
            CREATE TABLE IF NOT EXISTS embeddings (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,           -- 'vault' | 'mempalace' | 'skill'
                source_id TEXT NOT NULL,        -- path | drawer_id | skill_name
                content TEXT NOT NULL,          -- chunk text
                title TEXT,                     -- readable title
                summary TEXT,                   -- short summary
                
                -- PARA metadata
                para_layer INTEGER,             -- 1=inbox, 2=literature, 3=resource, 4=atomic
                para_category TEXT,             -- projeto|area|recurso|arquivo|meta|sistema
                tags TEXT,                      -- JSON array
                
                -- MemPalace metadata
                wing TEXT,
                room TEXT,
                drawer_type TEXT,
                
                -- Skill metadata
                skill_name TEXT,
                skill_version TEXT,
                
                -- Embedding
                embedding BLOB NOT NULL,        -- serialized float32 array
                embedding_model TEXT,
                dimensions INTEGER,
                
                -- Relationships
                links TEXT,                     -- JSON array of related IDs
                entities TEXT,                  -- JSON array of KG entities
                
                -- Temporal
                created_at TEXT,
                updated_at TEXT,
                accessed_at TEXT,
                
                -- Quality
                relevance_score REAL DEFAULT 0,
                token_count INTEGER DEFAULT 0,
                language TEXT DEFAULT 'pt',
                
                -- Raw metadata
                metadata TEXT                   -- JSON object
            );
            
            -- Metadata indexes for filtering
            CREATE INDEX IF NOT EXISTS idx_source ON embeddings(source);
            CREATE INDEX IF NOT EXISTS idx_source_id ON embeddings(source_id);
            CREATE INDEX IF NOT EXISTS idx_para_category ON embeddings(para_category);
            CREATE INDEX IF NOT EXISTS idx_para_layer ON embeddings(para_layer);
            CREATE INDEX IF NOT EXISTS idx_wing ON embeddings(wing);
            CREATE INDEX IF NOT EXISTS idx_skill_name ON embeddings(skill_name);
            CREATE INDEX IF NOT EXISTS idx_created_at ON embeddings(created_at);
            CREATE INDEX IF NOT EXISTS idx_tags ON embeddings(tags);
            
            -- Full-text search (lexical)
            CREATE VIRTUAL TABLE IF NOT EXISTS embeddings_fts USING fts5(
                id UNINDEXED,
                content,
                title,
                summary,
                tags,
                entities,
                tokenize='porter unicode61'
            );
            
            -- Trigger to keep FTS in sync
            CREATE TRIGGER IF NOT EXISTS embeddings_ai AFTER INSERT ON embeddings BEGIN
                INSERT INTO embeddings_fts(id, content, title, summary, tags, entities)
                VALUES (new.id, new.content, new.title, new.summary, new.tags, new.entities);
            END;
            
            CREATE TRIGGER IF NOT EXISTS embeddings_ad AFTER DELETE ON embeddings BEGIN
                DELETE FROM embeddings_fts WHERE id = old.id;
            END;
            
            CREATE TRIGGER IF NOT EXISTS embeddings_au AFTER UPDATE ON embeddings BEGIN
                DELETE FROM embeddings_fts WHERE id = old.id;
                INSERT INTO embeddings_fts(id, content, title, summary, tags, entities)
                VALUES (new.id, new.content, new.title, new.summary, new.tags, new.entities);
            END;
        """)
        self.conn.commit()
    
    def _create_vector_index(self):
        """Create vector index using sqlite-vec or FAISS."""
        if self.vec_available:
            try:
                # Create virtual table for vectors
                self.conn.execute(f"""
                    CREATE VIRTUAL TABLE IF NOT EXISTS vec_embeddings USING vec0(
                        id TEXT PRIMARY KEY,
                        embedding FLOAT[{self.config.dimensions}]
                    );
                """)
                
                # Create HNSW index if supported
                if self.config.index_type == "hnsw":
                    self.conn.execute(f"""
                        CREATE INDEX IF NOT EXISTS hnsw_idx ON vec_embeddings(embedding)
                        USING hnsw(
                            M={self.config.hnsw_M},
                            ef_construction={self.config.hnsw_ef_construction},
                            ef_search={self.config.hnsw_ef_search}
                        );
                    """)
                
                self.conn.commit()
            except Exception as e:
                print(f"Vector index creation failed (may not be supported): {e}")
        else:
            # FAISS fallback - tables already created in _init_faiss
            self._create_faiss_tables()
    
    def _create_faiss_tables(self):
        """Create FAISS-specific tables for storing embeddings."""
        self.conn.executescript("""
            -- FAISS vector table (stores raw embeddings for FAISS index sync)
            CREATE TABLE IF NOT EXISTS faiss_embeddings (
                id TEXT PRIMARY KEY,
                embedding BLOB NOT NULL
            );
            
            -- Index for FAISS internal ID mapping
            CREATE TABLE IF NOT EXISTS faiss_id_map (
                faiss_id INTEGER PRIMARY KEY,
                chunk_id TEXT UNIQUE
            );
        """)
        self.conn.commit()
    
    # ============================================================
    # VECTOR OPERATIONS
    # ============================================================
    
    def _serialize_embedding(self, embedding: np.ndarray) -> bytes:
        """Serialize numpy array to bytes."""
        return embedding.astype(np.float32).tobytes()
    
    def _deserialize_embedding(self, blob: bytes, dimensions: int = None) -> np.ndarray:
        """Deserialize bytes to numpy array."""
        dim = dimensions or self.config.dimensions
        return np.frombuffer(blob, dtype=np.float32, count=dim)
    
    def add(
        self, 
        embedding: np.ndarray,
        source: str,
        source_id: str,
        content: str,
        title: str = "",
        summary: str = "",
        para_layer: int = 1,
        para_category: str = "meta",
        tags: List[str] = None,
        wing: str = None,
        room: str = None,
        drawer_type: str = None,
        skill_name: str = None,
        skill_version: str = None,
        links: List[str] = None,
        entities: List[str] = None,
        created_at: str = None,
        updated_at: str = None,
        metadata: Dict = None,
        relevance_score: float = 0.0,
        token_count: int = 0,
        language: str = "pt",
        embedding_model: str = "all-MiniLM-L6-v2"
    ) -> str:
        """Add a new embedding with metadata."""
        import datetime
        
        chunk_id = str(uuid.uuid4())
        now = datetime.datetime.now().isoformat()
        
        # Serialize embedding
        emb_blob = embedding.astype(np.float32).tobytes()
        
        # JSON serialize arrays
        tags_json = json.dumps(tags or [])
        links_json = json.dumps(links or [])
        entities_json = json.dumps(entities or [])
        metadata_json = json.dumps(metadata or {})
        
        # Insert into main table
        self.conn.execute("""
            INSERT INTO embeddings (
                id, source, source_id, content, title, summary,
                para_layer, para_category, tags,
                wing, room, drawer_type,
                skill_name, skill_version,
                embedding, embedding_model, dimensions,
                links, entities,
                created_at, updated_at, accessed_at,
                relevance_score, token_count, language, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            chunk_id, source, source_id, content, title, summary,
            para_layer, para_category, tags_json,
            wing, room, drawer_type,
            skill_name, skill_version,
            emb_blob, embedding_model, len(embedding),
            links_json, entities_json,
            created_at or now, updated_at or now, now,
            relevance_score, token_count, language, metadata_json
        ))
        
        # Insert into vector table (sqlite-vec or FAISS)
        if self.vec_available:
            self.conn.execute(
                "INSERT INTO vec_embeddings (id, embedding) VALUES (?, ?)",
                (chunk_id, emb_blob)
            )
        else:
            # FAISS fallback
            self._add_to_faiss(chunk_id, embedding)
        
        self.conn.commit()
        return chunk_id
    
    def add_batch(self, chunks: List[Dict]) -> List[str]:
        """Add multiple chunks in a batch."""
        ids = []
        for chunk in chunks:
            chunk_id = self.add(**chunk)
            ids.append(chunk_id)
        return ids
    
    def update(self, chunk_id: str, **kwargs) -> bool:
        """Update an existing chunk."""
        # Build dynamic update query
        allowed_fields = {
            'content', 'title', 'summary', 'para_layer', 'para_category',
            'tags', 'wing', 'room', 'drawer_type', 'skill_name', 'skill_version',
            'links', 'entities', 'updated_at', 'relevance_score',
            'token_count', 'language', 'metadata'
        }
        
        updates = []
        values = []
        for key, value in kwargs.items():
            if key in allowed_fields:
                updates.append(f"{key} = ?")
                if key in ['tags', 'links', 'entities', 'metadata']:
                    values.append(json.dumps(value))
                else:
                    values.append(value)
        
        if not updates:
            return False
        
        values.append(chunk_id)
        query = f"UPDATE embeddings SET {', '.join(updates)} WHERE id = ?"
        cursor = self.conn.execute(query, values)
        self.conn.commit()
        return cursor.rowcount > 0
    
    def delete(self, chunk_id: str) -> bool:
        """Delete a chunk by ID."""
        cursor = self.conn.execute("DELETE FROM embeddings WHERE id = ?", (chunk_id,))
        
        if self.vec_available:
            self.conn.execute("DELETE FROM vec_embeddings WHERE id = ?", (chunk_id,))
        else:
            self.conn.execute("DELETE FROM faiss_embeddings WHERE id = ?", (chunk_id,))
            self.conn.execute("DELETE FROM faiss_id_map WHERE chunk_id = ?", (chunk_id,))
        
        self.conn.commit()
        return cursor.rowcount > 0
    
    def get(self, chunk_id: str) -> Optional[Dict]:
        """Get a chunk by ID."""
        row = self.conn.execute(
            "SELECT * FROM embeddings WHERE id = ?", (chunk_id,)
        ).fetchone()
        
        if row:
            return self._row_to_dict(row)
        return None
    
    def _row_to_dict(self, row: sqlite3.Row) -> Dict:
        """Convert SQLite row to dict with deserialized fields."""
        d = dict(row)
        
        # Deserialize JSON fields
        for field in ['tags', 'links', 'entities', 'metadata']:
            if d[field]:
                try:
                    d[field] = json.loads(d[field])
                except Exception:
                    d[field] = []
            else:
                d[field] = []
        
        # Deserialize embedding if needed
        if d['embedding']:
            d['embedding'] = np.frombuffer(d['embedding'], dtype=np.float32)
        
        return d
    
    # ============================================================
    # SEARCH OPERATIONS
    # ============================================================
    
    def search_vector(
        self, 
        query_embedding: np.ndarray, 
        k: int = 10,
        filter_sql: str = "",
        filter_params: Tuple = ()
    ) -> List[Tuple[str, float]]:
        """Search for nearest neighbors using vector similarity (sqlite-vec or FAISS)."""
        if self.vec_available:
            # Use sqlite-vec
            query_vec = query_embedding.astype(np.float32).tobytes()
            
            # Build query with optional filter
            base_query = """
                SELECT id, vec_distance(embedding, ?) as distance
                FROM vec_embeddings
            """
            
            if filter_sql:
                # Join with main table for filtering
                query = f"""
                    SELECT v.id, vec_distance(v.embedding, ?) as distance
                    FROM vec_embeddings v
                    JOIN embeddings e ON v.id = e.id
                    WHERE {filter_sql}
                    ORDER BY distance ASC
                    LIMIT ?
                """
                params = (query_vec,) + filter_params + (k,)
            else:
                query = """
                    SELECT id, vec_distance(embedding, ?) as distance
                    FROM vec_embeddings
                    ORDER BY distance ASC
                    LIMIT ?
                """
                params = (query_vec, k)
            
            cursor = self.conn.execute(query, params)
            return [(row['id'], row['distance']) for row in cursor.fetchall()]
        else:
            # Use FAISS fallback
            return self._search_vector_faiss(query_embedding, k)
    
    # ============================================================
    # FAISS FALLBACK METHODS
    # ============================================================
    
    def _add_to_faiss(self, chunk_id: str, embedding: np.ndarray):
        """Add embedding to FAISS index."""
        if not self.faiss_index:
            return
        
        # Normalize for cosine similarity (IndexFlatIP)
        faiss.normalize_L2(embedding.reshape(1, -1))
        
        # Get or assign FAISS internal ID
        if chunk_id in self.faiss_id_to_chunk:
            faiss_id = self.faiss_id_to_chunk[chunk_id]
        else:
            faiss_id = len(self.faiss_id_to_chunk)
            self.faiss_id_to_chunk[chunk_id] = faiss_id
            # Store mapping in DB
            self.conn.execute(
                "INSERT OR REPLACE INTO faiss_id_map (faiss_id, chunk_id) VALUES (?, ?)",
                (faiss_id, chunk_id)
            )
        
        # Add to FAISS index
        self.faiss_index.add(embedding.reshape(1, -1).astype(np.float32))
        
        # Store embedding blob for persistence
        emb_blob = embedding.astype(np.float32).tobytes()
        self.conn.execute(
            "INSERT OR REPLACE INTO faiss_embeddings (id, embedding) VALUES (?, ?)",
            (chunk_id, emb_blob)
        )
    
    def _search_vector_faiss(self, query_embedding: np.ndarray, k: int = 10) -> List[Tuple[str, float]]:
        """Search using FAISS index."""
        if not self.faiss_index or self.faiss_index.ntotal == 0:
            return []
        
        # Normalize query for cosine similarity
        faiss.normalize_L2(query_embedding.reshape(1, -1))
        
        # Search
        k = min(k, self.faiss_index.ntotal)
        distances, indices = self.faiss_index.search(query_embedding.reshape(1, -1).astype(np.float32), k)
        
        # Convert FAISS internal IDs back to chunk_ids
        results = []
        id_to_chunk = {v: k for k, v in self.faiss_id_to_chunk.items()}
        for i, idx in enumerate(indices[0]):
            if idx >= 0 and idx in id_to_chunk:
                chunk_id = id_to_chunk[idx]
                # Convert inner product distance to cosine distance
                distance = 1.0 - distances[0][i]  # cosine similarity -> distance
                results.append((chunk_id, distance))
        
        return results
    
    def _save_faiss(self):
        """Save FAISS index and mappings to disk."""
        if self.faiss_index:
            faiss.write_index(self.faiss_index, self.config.faiss_index_path)
            mapping_path = self.config.faiss_index_path + '.mapping'
            with open(mapping_path, 'w') as f:
                json.dump(self.faiss_id_to_chunk, f)
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
        
        # Save FAISS index on close
        try:
            self._save_faiss()
        except Exception:
            pass  # Ignore errors during shutdown
    
    def search_hybrid(
        self,
        query_embedding: np.ndarray,
        query_text: str = "",
        k: int = 10,
        semantic_weight: float = 0.5,
        lexical_weight: float = 0.3,
        graph_weight: float = 0.2,
        filters: Dict = None
    ) -> List[Dict]:
        """Hybrid search combining vector, lexical, and graph scores.
        Uses Reciprocal Rank Fusion (RRF).
        """
        results = {}
        
        # 1. Vector search
        if semantic_weight > 0:
            vec_results = self.search_vector(query_embedding, k=k*3)
            for rank, (chunk_id, distance) in enumerate(vec_results):
                score = semantic_weight / (rank + 1 + 60)  # RRF
                if chunk_id not in results:
                    results[chunk_id] = {"id": chunk_id, "score": 0, "sources": {}}
                results[chunk_id]["score"] += score
                results[chunk_id]["sources"]["vector"] = distance
        
        # 2. Lexical search (FTS5)
        if lexical_weight > 0 and query_text:
            fts_results = self.search_lexical(query_text, k=k*3)
            for rank, (chunk_id, bm25_score) in enumerate(fts_results):
                score = lexical_weight / (rank + 1 + 60)
                if chunk_id not in results:
                    results[chunk_id] = {"id": chunk_id, "score": 0, "sources": {}}
                results[chunk_id]["score"] += score
                results[chunk_id]["sources"]["lexical"] = bm25_score
        
        # Apply filters
        if filters:
            filtered = {}
            for chunk_id, data in results.items():
                chunk = self.get(chunk_id)
                if chunk and self._matches_filters(chunk, filters):
                    filtered[chunk_id] = data
            results = filtered
        
        # Sort by combined score
        sorted_results = sorted(
            results.items(), 
            key=lambda x: x[1]["score"], 
            reverse=True
        )
        
        # Return top k with full chunk data
        final = []
        for chunk_id, data in sorted_results[:k]:
            chunk = self.get(chunk_id)
            if chunk:
                final.append({
                    **chunk,
                    "hybrid_score": data["score"],
                    "sources": data["sources"]
                })
        
        return final
    
    def search_lexical(self, query: str, k: int = 10) -> List[Tuple[str, float]]:
        """Full-text search using FTS5."""
        cursor = self.conn.execute("""
            SELECT id, bm25(embeddings_fts) as score
            FROM embeddings_fts
            WHERE embeddings_fts MATCH ?
            ORDER BY score ASC
            LIMIT ?
        """, (query, k))
        return [(row['id'], row['score']) for row in cursor.fetchall()]
    
    def _matches_filters(self, chunk: Dict, filters: Dict) -> bool:
        """Check if chunk matches metadata filters."""
        for key, value in filters.items():
            if key == "source" and chunk.get("source") != value:
                return False
            elif key == "para_category" and chunk.get("para_category") != value:
                return False
            elif key == "para_layer" and chunk.get("para_layer") != value:
                return False
            elif key == "wing" and chunk.get("wing") != value:
                return False
            elif key == "skill_name" and chunk.get("skill_name") != value:
                return False
            elif key == "tags":
                chunk_tags = set(chunk.get("tags", []))
                if isinstance(value, list):
                    if not any(v in chunk_tags for v in value):
                        return False
                elif value not in chunk_tags:
                    return False
        return True
    
    # ============================================================
    # UTILITY METHODS
    # ============================================================
    
    def count(self, filter_sql: str = "", filter_params: Tuple = ()) -> int:
        """Count total embeddings."""
        query = "SELECT COUNT(*) as cnt FROM embeddings"
        if filter_sql:
            query += f" WHERE {filter_sql}"
        row = self.conn.execute(query, filter_params).fetchone()
        return row['cnt']
    
    def get_stats(self) -> Dict:
        """Get database statistics."""
        stats = {}
        
        # Total count
        stats['total_chunks'] = self.count()
        
        # By source
        cursor = self.conn.execute("""
            SELECT source, COUNT(*) as cnt 
            FROM embeddings 
            GROUP BY source
        """)
        stats['by_source'] = {row['source']: row['cnt'] for row in cursor.fetchall()}
        
        # By PARA category
        cursor = self.conn.execute("""
            SELECT para_category, COUNT(*) as cnt 
            FROM embeddings 
            GROUP BY para_category
        """)
        stats['by_para_category'] = {row['para_category']: row['cnt'] for row in cursor.fetchall()}
        
        # By wing
        cursor = self.conn.execute("""
            SELECT wing, COUNT(*) as cnt 
            FROM embeddings 
            WHERE wing IS NOT NULL
            GROUP BY wing
        """)
        stats['by_wing'] = {row['wing']: row['cnt'] for row in cursor.fetchall()}
        
        # DB size
        db_path = Path(self.config.db_path)
        if db_path.exists():
            stats['db_size_mb'] = db_path.stat().st_size / (1024 * 1024)
        
        return stats
    
    def vacuum(self):
        """Vacuum database to reclaim space."""
        self.conn.execute("VACUUM")
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
        
        # Save FAISS index on close
        try:
            self._save_faiss()
        except Exception:
            pass  # Ignore errors during shutdown
    
    def __del__(self):
        try:
            self.close()
        except Exception:
            pass  # Ignore errors during garbage collection


# ============================================================
# FACTORY
# ============================================================

def create_vector_store(config: VectorStoreConfig = None) -> VectorStore:
    """Create vector store with default or custom config."""
    if config is None:
        config = VectorStoreConfig(
            db_path="90-Sistema/_embeddings/memory_substrate.db"
        )
    return VectorStore(config)