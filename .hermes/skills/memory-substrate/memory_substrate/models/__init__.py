"""
Memory Substrate v1.0 — Data Models
Unified data structures for vault, mempalace, and skills.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pathlib import Path
import uuid


class SourceType(str, Enum):
    VAULT = "vault"
    MEMPALACE = "mempalace"
    SKILL = "skill"


class PARALayer(int, Enum):
    INBOX = 1
    LITERATURE = 2
    RESOURCE = 3
    ATOMIC = 4


class PARACategory(str, Enum):
    PROJECT = "projeto"
    AREA = "area"
    RESOURCE = "recurso"
    ARCHIVE = "arquivo"
    META = "meta"
    SYSTEM = "sistema"


class DrawerType(str, Enum):
    NOTE = "note"
    ENTITY = "entity"
    TUNNEL = "tunnel"
    HALLWAY = "hallway"


class ChunkStrategy(str, Enum):
    SEMANTIC = "semantic"
    FIXED = "fixed"
    HEADING = "heading"


@dataclass
class MemoryChunk:
    """Unified chunk across all memory sources"""
    
    # Identity
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: SourceType = SourceType.VAULT
    source_id: str = ""  # Vault path | Drawer ID | Skill name
    
    # Content
    content: str = ""
    title: str = ""
    summary: str = ""
    
    # PARA Metadata
    para_layer: PARALayer = PARALayer.INBOX
    para_category: PARACategory = PARACategory.META
    tags: List[str] = field(default_factory=list)
    
    # MemPalace Metadata
    wing: Optional[str] = None
    room: Optional[str] = None
    drawer_type: Optional[DrawerType] = None
    
    # Skill Metadata
    skill_name: Optional[str] = None
    skill_version: Optional[str] = None
    
    # Embeddings
    embedding: List[float] = field(default_factory=list)
    embedding_model: str = "all-MiniLM-L6-v2"
    
    # Relationships
    links: List[str] = field(default_factory=list)  # Wikilinks / related chunk IDs
    entities: List[str] = field(default_factory=list)  # KG entities
    
    # Temporal
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    accessed_at: datetime = field(default_factory=datetime.now)
    
    # Quality
    relevance_score: float = 0.0
    token_count: int = 0
    language: str = "pt"
    
    # Raw metadata (source-specific)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.embedding:
            self.embedding = []
        if not self.links:
            self.links = []
        if not self.entities:
            self.entities = []
        if not self.tags:
            self.tags = []
        if not self.metadata:
            self.metadata = {}


@dataclass
class VaultFile:
    """Represents a file in Obsidian Vault"""
    path: str
    relative_path: str
    content: str
    frontmatter: Dict[str, Any]
    stat: Any  # os.stat_result
    wikilinks: List[str] = field(default_factory=list)
    backlinks: List[str] = field(default_factory=list)
    
    def to_chunk(self) -> MemoryChunk:
        """Convert to MemoryChunk"""
        chunk = MemoryChunk(
            source=SourceType.VAULT,
            source_id=self.relative_path,
            content=self.content,
            title=Path(self.relative_path).stem,
            metadata={
                "full_path": self.path,
                "frontmatter": self.frontmatter,
                "wikilinks": self.wikilinks,
                "backlinks": self.backlinks,
                "size": self.stat.st_size,
                "modified": datetime.fromtimestamp(self.stat.st_mtime).isoformat()
            }
        )
        
        # Extract PARA info from path
        parts = Path(self.relative_path).parts
        if parts:
            first = parts[0]
            if first.startswith("00-"):
                chunk.para_category = PARACategory.META
                chunk.para_layer = PARALayer.INBOX
            elif first.startswith("10-"):
                chunk.para_category = PARACategory.PROJECT
                chunk.para_layer = PARALayer.RESOURCE
            elif first.startswith("20-"):
                chunk.para_category = PARACategory.AREA
                chunk.para_layer = PARALayer.RESOURCE
            elif first.startswith("30-"):
                chunk.para_category = PARACategory.RESOURCE
                chunk.para_layer = PARALayer.RESOURCE
            elif first.startswith("40-"):
                chunk.para_category = PARACategory.ARCHIVE
            elif first.startswith("50-"):
                chunk.para_category = PARACategory.META
            elif first.startswith("90-"):
                chunk.para_category = PARACategory.SYSTEM
        
        # Tags from frontmatter
        if "tags" in self.frontmatter:
            tags = self.frontmatter["tags"]
            if isinstance(tags, list):
                chunk.tags = [str(t).lstrip("#") for t in tags]
            elif isinstance(tags, str):
                chunk.tags = [t.strip().lstrip("#") for t in tags.split(",")]
        
        return chunk


@dataclass
class Drawer:
    """Represents a MemPalace drawer"""
    id: str
    wing: str
    room: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    drawer_type: DrawerType = DrawerType.NOTE
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    links: List[str] = field(default_factory=list)  # Tunnel connections
    
    def to_chunk(self) -> MemoryChunk:
        """Convert to MemoryChunk"""
        chunk = MemoryChunk(
            id=self.id,
            source=SourceType.MEMPALACE,
            source_id=self.id,
            content=self.content,
            title=self.metadata.get("title", f"Drawer {self.id[:8]}"),
            wing=self.wing,
            room=self.room,
            drawer_type=self.drawer_type,
            metadata=self.metadata,
            links=self.links
        )
        
        # Extract tags from metadata
        if "tags" in self.metadata:
            tags = self.metadata["tags"]
            if isinstance(tags, list):
                chunk.tags = [str(t).lstrip("#") for t in tags]
            elif isinstance(tags, str):
                chunk.tags = [t.strip().lstrip("#") for t in tags.split(",")]
        
        # PARA mapping from wing
        wing_mapping = {
            "10_projetos": PARACategory.PROJECT,
            "areas": PARACategory.AREA,
            "hermes_brain": PARACategory.SYSTEM,
            "inbox": PARACategory.META,
            "recursos": PARACategory.RESOURCE
        }
        chunk.para_category = wing_mapping.get(self.wing, PARACategory.META)
        
        # Layer based on drawer type
        if self.drawer_type == DrawerType.ENTITY:
            chunk.para_layer = PARALayer.ATOMIC
        elif self.drawer_type == DrawerType.TUNNEL:
            chunk.para_layer = PARALayer.RESOURCE
        else:
            chunk.para_layer = PARALayer.LITERATURE
        
        return chunk


@dataclass
class SkillManifest:
    """Skill manifest v2"""
    name: str
    version: str
    description: str
    category: str
    author: str = "Hermes Agent"
    license: str = "MIT"
    min_hermes_version: str = "0.20.0"
    tags: List[str] = field(default_factory=list)
    
    # Dependencies
    dependencies: Dict[str, List[str]] = field(default_factory=lambda: {
        "required": [],
        "optional": []
    })
    
    # Capabilities
    capabilities: Dict[str, List[str]] = field(default_factory=lambda: {
        "provides": [],
        "consumes": []
    })
    
    # Config schema
    config_schema: Dict[str, Any] = field(default_factory=dict)
    
    # Entry points
    entry_points: Dict[str, str] = field(default_factory=lambda: {
        "main": "",
        "cli": "",
        "api": ""
    })
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_chunk(self) -> MemoryChunk:
        """Convert to MemoryChunk"""
        chunk = MemoryChunk(
            source=SourceType.SKILL,
            source_id=self.name,
            content=f"{self.description}\n\nCapabilities: {self.capabilities}",
            title=self.name,
            skill_name=self.name,
            skill_version=self.version,
            tags=self.tags,
            metadata={
                "version": self.version,
                "category": self.category,
                "dependencies": self.dependencies,
                "capabilities": self.capabilities,
                "entry_points": self.entry_points
            }
        )
        chunk.para_category = PARACategory.SYSTEM
        chunk.para_layer = PARALayer.RESOURCE
        return chunk


@dataclass
class SearchResult:
    """Unified search result"""
    chunk: MemoryChunk
    score: float
    match_type: str  # "semantic" | "lexical" | "graph" | "hybrid"
    highlights: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.chunk.id,
            "source": self.chunk.source.value,
            "title": self.chunk.title,
            "summary": self.chunk.summary,
            "content": self.chunk.content[:500],
            "score": self.score,
            "match_type": self.match_type,
            "highlights": self.highlights,
            "tags": self.chunk.tags,
            "para_category": self.chunk.para_category.value,
            "para_layer": self.chunk.para_layer.value,
            "wing": self.chunk.wing,
            "skill_name": self.chunk.skill_name
        }


@dataclass
class QueryPlan:
    """Execution plan for a query"""
    intent: str  # "list" | "find" | "synthesize" | "traverse" | "compare"
    entities: List[str]
    filters: Dict[str, Any]
    sources: List[SourceType]
    required_capabilities: List[str]
    max_results: int = 20
    synthesize: bool = False
    citation_style: str = "wiki"


@dataclass
class SynthesizedAnswer:
    """Synthesized answer from query"""
    answer: str
    citations: List[SearchResult]
    confidence: float
    gaps: List[str]
    follow_up_questions: List[str]
    token_count: int
    latency_ms: float