"""
Memory Substrate v1.0 — Chunker
Semantic, fixed, and heading-based chunking strategies.
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from pathlib import Path
from enum import Enum


class ChunkingStrategy(str, Enum):
    SEMANTIC = "semantic"
    FIXED = "fixed"
    HEADING = "heading"


@dataclass
class ChunkerConfig:
    strategy: ChunkingStrategy = ChunkingStrategy.SEMANTIC
    chunk_size: int = 512
    chunk_overlap: int = 50
    # CORREÇÃO (bug chunker, FASE 2 PCM): seções curtas (< min_chunk_size) eram
    # DESCARTADAS silenciosamente pelo HeadingChunker (ex: "## Lema" dos SOULs,
    # <100 chars, sumiu do índice). Baixado 100→40 para preservar seções densas
    # curtas; seções ainda menores são mescladas (merge) — ver HeadingChunker.
    min_chunk_size: int = 40
    max_chunk_size: int = 2000
    heading_levels: List[str] = None  # e.g., ["#", "##", "###"]
    separators: List[str] = None  # For semantic chunking
    
    def __post_init__(self):
        if self.heading_levels is None:
            self.heading_levels = ["#", "##", "###", "####"]
        if self.separators is None:
            self.separators = [
                "\n\n",  # Paragraphs
                "\n",    # Lines
                ". ",    # Sentences
                "? ",    # Questions
                "! ",    # Exclamations
                "; ",    # Semicolons
                ", ",    # Commas
                " "      # Words
            ]


class BaseChunker(ABC):
    """Abstract base class for chunkers."""
    
    def __init__(self, config: ChunkerConfig):
        self.config = config
    
    @abstractmethod
    def chunk(self, text: str, metadata: Dict = None) -> List[Dict]:
        """Chunk text into pieces with metadata."""
        pass
    
    def _create_chunk(
        self, 
        content: str, 
        index: int, 
        metadata: Dict = None,
        start_char: int = 0,
        end_char: int = 0
    ) -> Dict:
        """Create a standardized chunk dict."""
        chunk_meta = metadata.copy() if metadata else {}
        chunk_meta.update({
            "chunk_index": index,
            "chunk_start": start_char,
            "chunk_end": end_char,
            "chunk_size": len(content)
        })
        
        return {
            "content": content,
            "metadata": chunk_meta,
            "start_char": start_char,
            "end_char": end_char
        }


class FixedChunker(BaseChunker):
    """Fixed-size chunking with overlap."""
    
    def chunk(self, text: str, metadata: Dict = None) -> List[Dict]:
        chunks = []
        chunk_size = self.config.chunk_size
        overlap = self.config.chunk_overlap
        step = chunk_size - overlap
        
        if step <= 0:
            step = chunk_size
        
        for i in range(0, len(text), step):
            end = min(i + chunk_size, len(text))
            chunk_text = text[i:end]
            
            if len(chunk_text.strip()) < self.config.min_chunk_size:
                continue
            
            chunk = self._create_chunk(
                content=chunk_text,
                index=len(chunks),
                metadata=metadata,
                start_char=i,
                end_char=end
            )
            chunks.append(chunk)
        
        return chunks


class HeadingChunker(BaseChunker):
    """Heading-based chunking for markdown documents."""

    # CORREÇÃO (bug chunker, FASE 2 PCM): antes, seções < min_chunk_size eram
    # descartadas silenciosamente ("## Lema" dos SOULs sumiu do índice).
    # Escolha: MERGE da seção curta com o chunk seguinte (mais simples e seguro
    # que só baixar o min, pois preserva todo o conteúdo sem criar chunks
    # minúsculos demais). Default min_chunk_size também baixado 100→40.
    def chunk(self, text: str, metadata: Dict = None) -> List[Dict]:
        chunks = []
        lines = text.split("\n")

        current_chunk = []   # linhas da seção corrente (começa com a linha do heading)
        current_heading = ""
        heading_level = 0
        chunk_index = 0
        char_offset = 0

        # CORREÇÃO: linhas de seções curtas (< min_chunk_size) acumulam aqui e
        # são MESCLADAS como prefixo da PRÓXIMA seção longa (ou num chunk
        # final, se o doc acabar). Antes eram descartadas silenciosamente.
        pending_lines: List[str] = []
        pending_heading = ""
        pending_level = 0

        def _emit(section_lines: List[str], heading: str, level: int):
            nonlocal chunk_index, char_offset
            content = "\n".join(section_lines).strip()
            if not content:
                return
            chunk = self._create_chunk(
                content=content,
                index=chunk_index,
                metadata={
                    **(metadata or {}),
                    "heading": heading,
                    "heading_level": level
                },
                start_char=char_offset,
                end_char=char_offset + len(content)
            )
            chunks.append(chunk)
            chunk_index += 1
            char_offset += len(content) + 1

        for line in lines:
            # Check if line is a heading
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)

            if heading_match:
                # Close previous section
                if current_chunk:
                    content = "\n".join(current_chunk).strip()
                    if len(content) >= self.config.min_chunk_size:
                        # Seção longa: emite (com pendentes curtas no prefixo)
                        _emit(pending_lines + current_chunk, current_heading, heading_level)
                        pending_lines = []
                    else:
                        # Seção curta: NÃO descarta — acumula para merge
                        pending_lines.extend(current_chunk)
                        pending_heading = current_heading
                        pending_level = heading_level

                # Start new chunk
                heading_level = len(heading_match.group(1))
                current_heading = heading_match.group(2).strip()
                current_chunk = [line]

            else:
                current_chunk.append(line)

        # Don't forget the last chunk
        if current_chunk:
            content = "\n".join(current_chunk).strip()
            if len(content) >= self.config.min_chunk_size:
                _emit(pending_lines + current_chunk, current_heading, heading_level)
                pending_lines = []
            else:
                pending_lines.extend(current_chunk)
                pending_heading = current_heading
                pending_level = heading_level

        # Seções curtas no fim do doc (sem próxima seção): emitem juntas
        # num chunk final — antes esse conteúdo era perdido.
        if pending_lines:
            _emit(pending_lines, pending_heading, pending_level)

        return chunks


class SemanticChunker(BaseChunker):
    """Semantic chunking using recursive splitting with separators."""
    
    def __init__(self, config: ChunkerConfig):
        super().__init__(config)
        self.separators = config.separators or [
            "\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " "
        ]
    
    def chunk(self, text: str, metadata: Dict = None) -> List[Dict]:
        """Recursively split text using separators."""
        chunks = self._recursive_split(text, self.separators)
        
        result = []
        for i, chunk_text in enumerate(chunks):
            if len(chunk_text.strip()) < self.config.min_chunk_size:
                continue
            
            # Further split if too large
            if len(chunk_text) > self.config.max_chunk_size:
                sub_chunks = self._split_large_chunk(chunk_text)
                for j, sub in enumerate(sub_chunks):
                    chunk = self._create_chunk(
                        content=sub,
                        index=len(result) + j,
                        metadata=metadata
                    )
                    result.append(chunk)
            else:
                chunk = self._create_chunk(
                    content=chunk_text.strip(),
                    index=len(result),
                    metadata=metadata
                )
                result.append(chunk)
        
        return result
    
    def _recursive_split(self, text: str, separators: List[str]) -> List[str]:
        """Recursively split text using separators in order."""
        if not separators:
            return [text]
        
        separator = separators[0]
        remaining = separators[1:]
        
        # Split by current separator
        parts = text.split(separator)
        
        # If split worked and parts are reasonably sized, continue recursively
        if len(parts) > 1 and remaining:
            result = []
            for part in parts:
                if part.strip():
                    sub_parts = self._recursive_split(part, remaining)
                    # Rejoin with separator
                    result.extend([p + separator for p in sub_parts[:-1]])
                    result.append(sub_parts[-1])
            return result
        
        return [text]
    
    def _split_large_chunk(self, text: str) -> List[str]:
        """Split a chunk that's too large using fixed-size with overlap."""
        chunker = FixedChunker(self.config)
        chunks = chunker.chunk(text)
        return [c["content"] for c in chunks]


# ============================================================
# FACTORY
# ============================================================

class Chunker:
    """Main chunker that delegates to strategy-specific implementations."""
    
    def __init__(self, config: ChunkerConfig):
        self.config = config
        self._chunkers = {
            ChunkingStrategy.FIXED: FixedChunker(config),
            ChunkingStrategy.HEADING: HeadingChunker(config),
            ChunkingStrategy.SEMANTIC: SemanticChunker(config)
        }
    
    def chunk(self, text: str, metadata: Dict = None, strategy: ChunkingStrategy = None) -> List[Dict]:
        """Chunk text using specified or configured strategy."""
        strategy = strategy or self.config.strategy
        chunker = self._chunkers.get(strategy)
        
        if not chunker:
            raise ValueError(f"Unknown chunking strategy: {strategy}")
        
        return chunker.chunk(text, metadata)
    
    def chunk_file(self, file_path: str, metadata: Dict = None) -> List[Dict]:
        """Chunk a file based on its extension."""
        path = Path(file_path)
        
        # Determine strategy by file type
        if path.suffix == ".md":
            strategy = ChunkingStrategy.HEADING
        elif path.suffix in [".py", ".js", ".ts", ".rs", ".go"]:
            strategy = ChunkingStrategy.SEMANTIC  # Could be enhanced for code
        else:
            strategy = self.config.strategy
        
        text = path.read_text(encoding="utf-8", errors="replace")
        file_metadata = {
            **(metadata or {}),
            "file_path": str(file_path),
            "file_name": path.name,
            "file_extension": path.suffix
        }
        
        return self.chunk(text, file_metadata, strategy)


def create_chunker(config: ChunkerConfig = None) -> Chunker:
    """Create chunker with default or custom config."""
    if config is None:
        config = ChunkerConfig()
    return Chunker(config)