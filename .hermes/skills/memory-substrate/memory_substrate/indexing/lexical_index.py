"""
Memory Substrate v1.0 — Lexical Index
SQLite FTS5 based full-text search for keyword/phrase matching.
"""

import sqlite3
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path


@dataclass
class LexicalIndexConfig:
    db_path: str
    tokenizer: str = "porter unicode61"  # porter | unicode61 | ascii
    enable_triggers: bool = True
    
    def __post_init__(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)


class LexicalIndex:
    """
    SQLite FTS5 based lexical index for full-text search.
    Provides BM25-ranked keyword/phrase search with filtering.
    """
    
    def __init__(self, config: LexicalIndexConfig):
        self.config = config
        self.conn = None
        self._init_db()
    
    def _init_db(self):
        """Initialize database and create FTS5 table."""
        self.conn = sqlite3.connect(self.config.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        
        # Enable WAL mode
        self.conn.execute("PRAGMA journal_mode=WAL")
        
        # Create FTS5 virtual table
        self._create_fts_table()
        
        if self.config.enable_triggers:
            self._create_sync_triggers()
    
    def _create_fts_table(self):
        """Create FTS5 virtual table for full-text search."""
        self.conn.execute(f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS lexical_index USING fts5(
                id UNINDEXED,
                source UNINDEXED,
                source_id UNINDEXED,
                title,
                content,
                summary,
                tags,
                entities,
                -- Column weights for BM25
                tokenize='{self.config.tokenizer}'
            );
        """)
        self.conn.commit()
    
    def _create_sync_triggers(self):
        """Create triggers to sync with main embeddings table."""
        # Note: These assume the main table is in the same database
        # If separate DB, would need application-level sync
        pass
    
    # ============================================================
    # INDEX OPERATIONS
    # ============================================================
    
    def add(
        self,
        chunk_id: str,
        source: str,
        source_id: str,
        title: str,
        content: str,
        summary: str = "",
        tags: List[str] = None,
        entities: List[str] = None
    ) -> bool:
        """Add a document to the lexical index."""
        tags_json = " ".join(tags or [])
        entities_json = " ".join(entities or [])
        
        try:
            self.conn.execute("""
                INSERT INTO lexical_index (id, source, source_id, title, content, summary, tags, entities)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                chunk_id, source, source_id, title, content, summary,
                tags_json, entities_json
            ))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Already exists, update instead
            return self.update(chunk_id, content, summary, tags, entities)
    
    def update(
        self,
        chunk_id: str,
        content: str = None,
        summary: str = None,
        tags: List[str] = None,
        entities: List[str] = None
    ) -> bool:
        """Update an existing document."""
        updates = []
        params = []
        
        if content is not None:
            updates.append("content = ?")
            params.append(content)
        if summary is not None:
            updates.append("summary = ?")
            params.append(summary)
        if tags is not None:
            updates.append("tags = ?")
            params.append(" ".join(tags))
        if entities is not None:
            updates.append("entities = ?")
            params.append(" ".join(entities))
        
        if not updates:
            return False
        
        params.append(chunk_id)
        query = f"UPDATE lexical_index SET {', '.join(updates)} WHERE id = ?"
        
        cursor = self.conn.execute(query, params)
        self.conn.commit()
        return cursor.rowcount > 0
    
    def delete(self, chunk_id: str) -> bool:
        """Delete a document from the index."""
        cursor = self.conn.execute("DELETE FROM lexical_index WHERE id = ?", (chunk_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def delete_by_source(self, source: str) -> int:
        """Delete all documents from a source."""
        cursor = self.conn.execute("DELETE FROM lexical_index WHERE source = ?", (source,))
        self.conn.commit()
        return cursor.rowcount
    
    # ============================================================
    # SEARCH OPERATIONS
    # ============================================================
    
    def search(
        self,
        query: str,
        k: int = 10,
        source: str = None,
        highlight: bool = True
    ) -> List[Dict]:
        """
        Search the lexical index.
        
        Args:
            query: FTS5 query string (supports phrases, NOT, AND, OR, NEAR)
            k: Maximum results
            source: Filter by source
            highlight: Include highlighted snippets
            
        Returns:
            List of search results with BM25 scores
        """
        # Build query
        base_query = """
            SELECT id, source, source_id, title, content, summary, tags, entities,
                   bm25(lexical_index) as score
            FROM lexical_index
        """
        
        where_conditions = ["lexical_index MATCH ?"]
        params = [query]
        
        if source:
            where_conditions.append("source = ?")
            params.append(source)
        
        where_clause = " WHERE " + " AND ".join(where_conditions)
        order_clause = " ORDER BY score ASC"  # BM25: lower is better
        limit_clause = f" LIMIT {k}"
        
        full_query = base_query + where_clause + order_clause + limit_clause
        
        cursor = self.conn.execute(full_query, params)
        
        results = []
        for row in cursor.fetchall():
            result = {
                "id": row["id"],
                "source": row["source"],
                "source_id": row["source_id"],
                "title": row["title"],
                "content": row["content"],
                "summary": row["summary"],
                "tags": row["tags"].split() if row["tags"] else [],
                "entities": row["entities"].split() if row["entities"] else [],
                "score": row["score"]
            }
            
            if highlight:
                result["highlights"] = self._generate_highlights(
                    row["content"], query
                )
            
            results.append(result)
        
        return results
    
    def search_bm25(
        self,
        query: str,
        k: int = 10,
        source: str = None
    ) -> List[Tuple[str, float]]:
        """Search returning only (id, bm25_score) tuples."""
        results = self.search(query, k=k, source=source, highlight=False)
        return [(r["id"], r["score"]) for r in results]
    
    def _generate_highlights(self, content: str, query: str, max_snippets: int = 3) -> List[str]:
        """Generate highlighted snippets from content."""
        # Simple highlighting - find query terms in content
        import re
        
        # Extract terms from query (remove FTS5 operators)
        terms = re.findall(r'"([^"]+)"|(\S+)', query)
        terms = [t[0] or t[1] for t in terms if t[0] or t[1]]
        terms = [t for t in terms if t not in ('AND', 'OR', 'NOT', 'NEAR')]
        
        if not terms:
            return [content[:200] + "..."]
        
        highlights = []
        sentences = re.split(r'[.!?]+', content)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Check if sentence contains any query terms
            sentence_lower = sentence.lower()
            matches = sum(1 for term in terms if term.lower() in sentence_lower)
            
            if matches > 0:
                # Highlight terms
                highlighted = sentence
                for term in terms:
                    pattern = re.compile(re.escape(term), re.IGNORECASE)
                    highlighted = pattern.sub(f"**{term}**", highlighted)
                
                highlights.append(highlighted)
                
                if len(highlights) >= max_snippets:
                    break
        
        if not highlights:
            return [content[:200] + "..."]
        
        return highlights
    
    def count(self, source: str = None) -> int:
        """Count documents in index."""
        if source:
            row = self.conn.execute(
                "SELECT COUNT(*) as cnt FROM lexical_index WHERE source = ?", 
                (source,)
            ).fetchone()
        else:
            row = self.conn.execute("SELECT COUNT(*) as cnt FROM lexical_index").fetchone()
        return row["cnt"]
    
    def get_stats(self) -> Dict:
        """Get index statistics."""
        stats = {}
        stats["total_documents"] = self.count()
        
        # By source
        cursor = self.conn.execute("""
            SELECT source, COUNT(*) as cnt 
            FROM lexical_index 
            GROUP BY source
        """)
        stats["by_source"] = {row["source"]: row["cnt"] for row in cursor.fetchall()}
        
        # DB size
        db_path = Path(self.config.db_path)
        if db_path.exists():
            stats["db_size_mb"] = db_path.stat().st_size / (1024 * 1024)
        
        return stats
    
    def rebuild(self, documents: List[Dict]) -> int:
        """Rebuild entire index from documents."""
        # Clear existing
        self.conn.execute("DELETE FROM lexical_index")
        
        # Bulk insert
        count = 0
        for doc in documents:
            if self.add(**doc):
                count += 1
        
        self.conn.commit()
        return count
    
    def optimize(self):
        """Optimize FTS5 index (merge segments)."""
        self.conn.execute("INSERT INTO lexical_index(lexical_index) VALUES('optimize')")
        self.conn.commit()
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def __del__(self):
        self.close()


# ============================================================
# FACTORY
# ============================================================

def create_lexical_index(config: LexicalIndexConfig = None) -> LexicalIndex:
    """Create lexical index with default or custom config."""
    if config is None:
        config = LexicalIndexConfig(
            db_path="90-Sistema/_embeddings/lexical.db"
        )
    return LexicalIndex(config)