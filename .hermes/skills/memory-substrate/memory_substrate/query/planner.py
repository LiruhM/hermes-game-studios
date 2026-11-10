"""
Memory Substrate v1.0 — Query Engine: Planner
Natural language query analysis and execution planning.
"""

import re
import json
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class QueryIntent(str, Enum):
    LIST = "list"           # "quais skills tenho?"
    FIND = "find"           # "onde está o arquivo X?"
    SYNTHESIZE = "synthesize"  # "explique como funciona Y"
    TRAVERSE = "traverse"   # "o que conecta A a B?"
    COMPARE = "compare"     # "diferença entre X e Y"
    SUMMARIZE = "summarize" # "resuma o projeto Z"
    COUNT = "count"         # "quantos drawers no wing X?"


class QuerySource(str, Enum):
    VAULT = "vault"
    MEMPALACE = "mempalace"
    SKILL = "skill"
    ALL = "all"


@dataclass
class QueryEntity:
    """Extracted entity from query."""
    text: str
    type: str  # "skill" | "project" | "concept" | "file" | "entity" | "wing" | "person"
    confidence: float
    metadata: Dict = field(default_factory=dict)


@dataclass
class QueryFilter:
    """Structured filter for query."""
    field: str
    operator: str  # "eq" | "in" | "contains" | "gt" | "lt" | "exists"
    value: Any


@dataclass
class QueryPlan:
    """Execution plan for a query."""
    intent: QueryIntent
    entities: List[QueryEntity]
    filters: List[QueryFilter]
    sources: List[QuerySource]
    required_capabilities: List[str] = field(default_factory=list)
    max_results: int = 20
    synthesize: bool = False
    citation_style: str = "wiki"  # wiki | markdown | numeric
    sort_by: str = "relevance"  # relevance | date | title
    sort_order: str = "desc"
    expand_entities: bool = True  # Follow graph connections
    max_depth: int = 2
    
    def to_dict(self) -> Dict:
        return {
            "intent": self.intent.value,
            "entities": [{"text": e.text, "type": e.type, "confidence": e.confidence} for e in self.entities],
            "filters": [{"field": f.field, "operator": f.operator, "value": f.value} for f in self.filters],
            "sources": [s.value for s in self.sources],
            "required_capabilities": self.required_capabilities,
            "max_results": self.max_results,
            "synthesize": self.synthesize,
            "citation_style": self.citation_style,
            "sort_by": self.sort_by,
            "sort_order": self.sort_order,
            "expand_entities": self.expand_entities,
            "max_depth": self.max_depth
        }


class QueryPlanner:
    """
    Analyzes natural language queries and creates execution plans.
    Extracts intent, entities, filters, and determines required sources/capabilities.
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self._init_patterns()
        self._init_entity_patterns()
        self._init_intent_keywords()
        self._init_source_keywords()
    
    def _init_patterns(self):
        """Regex patterns for query parsing."""
        self.patterns = {
            # Question words
            "question_starters": [
                r"^(o que|oque|que|qual|quais|quem|onde|quando|como|por que|porque)\b",
                r"^(liste|lista|mostre|me mostre|encontre|ache|busque|procure)\b",
                r"^(explique|explique-me|descreva|resuma|resumo|compare|diferença)\b",
                r"^(quantos|quantas|conte|conta)\b"
            ],
            
            # Intent patterns
            "list": [
                r"\b(liste|lista|mostre|quais|todas?|todos?)\b",
                r"\b(todas as|todos os)\b"
            ],
            "find": [
                r"\b(onde|encontre|ache|localize|busque|procure)\b",
                r"\b(caminho|path|localização)\b"
            ],
            "synthesize": [
                r"\b(explique|explique-me|como funciona|o que é|definição)\b",
                r"\b(por que|porque|reason|motivo)\b"
            ],
            "traverse": [
                r"\b(conecta|conectado|liga|relaciona|associa)\b",
                r"\b(caminho entre|ligação|relação)\b",
                r"\b(tunnel|túnel|ponte)\b"
            ],
            "compare": [
                r"\b(compare|diferença|diferente|versus|vs|contra)\b",
                r"\b(semelhança|similar|parecido)\b"
            ],
            "summarize": [
                r"\b(resuma|resumo|sumário|visão geral|overview)\b",
                r"\b(principais pontos|key points|highlights)\b"
            ],
            "count": [
                r"\b(quantos|quantas|conte|conta|número|total)\b",
                r"\b(contagem|count)\b"
            ],
            
            # Entity patterns
            "skill": r"\b(skill|habilidade|capability)\b",
            "project": r"\b(projeto|project)\b",
            "concept": r"\b(conceito|concept|tópico|topic)\b",
            "file": r"\b(arquivo|file|documento|doc|nota|note)\b",
            "entity": r"\b(entidade|entity|objeto|object)\b",
            "wing": r"\b(wing|asa)\b",
            "person": r"\b(pessoa|pessoa|usuário|user|autor|author)\b",
            
            # Source patterns
            "vault": r"\b(vault|obsidian|notas|notes|zettelkasten)\b",
            "mempalace": r"\b(mempalace|palace|palácio|drawer|gaveta)\b",
            "skill": r"\b(skill|habilidade|capability|código|code)\b"
        }
    
    def _init_entity_patterns(self):
        """Patterns for entity extraction."""
        self.entity_patterns = {
            "skill": [
                r"\b(token.optimization|token-optimization|second.brain|second-brain-pipeline|hermes.squad|hermes-squad-core|productivity.tools|productivity-tools|creative.tools|creative-tools|devops.tools|devops-tools|mlops.tools|mlops-tools|research.tools|research-tools|note.taking|note-taking-tools|software.dev|software-dev-tools|media.tools|media-tools|apple.tools|apple-tools|memory.substrate|memory-substrate)\b",
                r"\b\w+-\w+(?:-\w+)*\b"  # kebab-case words
            ],
            "project": [
                r"\b(Hermes.Agent|Hermes-Agent|Token.Optimization|Token-Optimization|RPG.Platform|RPG-Platform|Ecosystem.Improvements|Ecosystem-Improvements)\b",
                r"\b[A-Z][a-z]+(?:\.[A-Z][a-z]+)+\b"  # PascalCase with dots
            ],
            "wing": [
                r"\b(10_projetos|areas|hermes_brain|inbox|recursos)\b"
            ],
            "person": [
                r"\b(Ray Dalio|Charlie Munger|Naval Ravikant|Peter Thiel|Reid Hoffman|Simon Sinek|Matheus Sousa)\b"
            ],
            "advisor": [
                r"\b(Dalio|Munger|Naval|Thiel|Hoffman|Sinek)\b"
            ],
            "c_level": [
                r"\b(CEO|CTO|CMO|COO|CIO|CAIO)\b"
            ]
        }
    
    def _init_intent_keywords(self):
        """Keywords mapped to intents."""
        self.intent_keywords = {
            QueryIntent.LIST: ["liste", "lista", "mostre", "quais", "todas", "todos", "enumerate"],
            QueryIntent.FIND: ["onde", "encontre", "ache", "localize", "busque", "procure", "caminho", "localização"],
            QueryIntent.SYNTHESIZE: ["explique", "como funciona", "o que é", "definição", "por que", "porque", "reason"],
            QueryIntent.TRAVERSE: ["conecta", "conectado", "liga", "relaciona", "associa", "caminho entre", "relação", "tunnel", "túnel"],
            QueryIntent.COMPARE: ["compare", "diferença", "diferente", "versus", "vs", "contra", "semelhança", "similar"],
            QueryIntent.SUMMARIZE: ["resuma", "resumo", "sumário", "visão geral", "overview", "principais pontos", "highlights"],
            QueryIntent.COUNT: ["quantos", "quantas", "conte", "conta", "número", "total", "contagem", "count"]
        }
    
    def _init_source_keywords(self):
        """Keywords mapped to sources."""
        self.source_keywords = {
            QuerySource.VAULT: ["vault", "obsidian", "notas", "notes", "zettelkasten", "arquivos", "files"],
            QuerySource.MEMPALACE: ["mempalace", "palace", "palácio", "drawer", "gaveta", "wing", "asa"],
            QuerySource.SKILL: ["skill", "habilidade", "capability", "código", "code", "função", "function"]
        }
    
    # ============================================================
    # MAIN PLANNING METHOD
    # ============================================================
    
    def plan(self, query: str, context: Dict = None) -> QueryPlan:
        """
        Create execution plan from natural language query.
        
        Args:
            query: Natural language query
            context: Optional context (current project, user preferences, etc.)
            
        Returns:
            QueryPlan with intent, entities, filters, sources, etc.
        """
        query_lower = query.lower().strip()
        context = context or {}
        
        # 1. Detect intent
        intent = self._detect_intent(query_lower)
        
        # 2. Extract entities
        entities = self._extract_entities(query, query_lower)
        
        # 3. Determine sources
        sources = self._determine_sources(query_lower, entities, context)
        
        # 4. Extract filters
        filters = self._extract_filters(query_lower, entities)
        
        # 5. Determine capabilities needed
        capabilities = self._determine_capabilities(intent, entities, sources)
        
        # 6. Determine synthesis need
        synthesize = intent in [QueryIntent.SYNTHESIZE, QueryIntent.SUMMARIZE, QueryIntent.COMPARE]
        
        # 7. Build plan
        plan = QueryPlan(
            intent=intent,
            entities=entities,
            filters=filters,
            sources=sources,
            required_capabilities=capabilities,
            max_results=context.get("max_results", 20),
            synthesize=synthesize,
            citation_style=context.get("citation_style", "wiki"),
            sort_by=context.get("sort_by", "relevance"),
            sort_order=context.get("sort_order", "desc"),
            expand_entities=context.get("expand_entities", True),
            max_depth=context.get("max_depth", 2)
        )
        
        return plan
    
    # ============================================================
    # INTENT DETECTION
    # ============================================================
    
    def _detect_intent(self, query: str) -> QueryIntent:
        """Detect query intent from keywords."""
        scores = {intent: 0 for intent in QueryIntent}
        
        for intent, keywords in self.intent_keywords.items():
            for kw in keywords:
                if kw in query:
                    scores[intent] += 1
        
        # Special patterns
        if re.search(r"\b(o que|oque|que)\b.*\b(é|são)\b", query):
            scores[QueryIntent.SYNTHESIZE] += 2
        
        if re.search(r"\b(versus|vs|versão)\b", query):
            scores[QueryIntent.COMPARE] += 2
        
        if re.search(r"\b(entre|entre.*e)\b", query):
            scores[QueryIntent.TRAVERSE] += 2
        
        # Return highest scoring intent
        best_intent = max(scores, key=scores.get)
        
        # Default to LIST if no clear intent
        if scores[best_intent] == 0:
            return QueryIntent.LIST
        
        return best_intent
    
    # ============================================================
    # ENTITY EXTRACTION
    # ============================================================
    
    def _extract_entities(self, query: str, query_lower: str) -> List[QueryEntity]:
        """Extract entities from query."""
        entities = []
        
        # Extract by patterns
        for entity_type, patterns in self.entity_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, query, re.IGNORECASE)
                for match in matches:
                    entity_text = match.group()
                    entities.append(QueryEntity(
                        text=entity_text,
                        type=entity_type,
                        confidence=0.9,
                        metadata={"match": match.group(0)}
                    ))
        
        # Extract quoted strings as potential entities
        quoted = re.findall(r'"([^"]+)"', query)
        for q in quoted:
            entities.append(QueryEntity(
                text=q,
                type="concept",
                confidence=0.7,
                metadata={"quoted": True}
            ))
        
        # Extract capitalized phrases (potential proper nouns)
        proper_nouns = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', query)
        for noun in proper_nouns:
            if noun.lower() not in ('the', 'and', 'for', 'with', 'this', 'that', 'como', 'onde', 'quando'):
                # Check if already captured
                if not any(e.text == noun for e in entities):
                    entities.append(QueryEntity(
                        text=noun,
                        type="concept",
                        confidence=0.5
                    ))
        
        # Deduplicate
        seen = set()
        unique = []
        for e in entities:
            key = (e.text.lower(), e.type)
            if key not in seen:
                seen.add(key)
                unique.append(e)
        
        return unique
    
    # ============================================================
    # SOURCE DETERMINATION
    # ============================================================
    
    def _determine_sources(self, query: str, entities: List[QueryEntity], context: Dict) -> List[QuerySource]:
        """Determine which sources to search."""
        sources = set()
        
        # Explicit source mentions
        for source, keywords in self.source_keywords.items():
            for kw in keywords:
                if kw in query:
                    sources.add(source)
        
        # Entity-based source inference
        for entity in entities:
            if entity.type in ["skill", "project"] and entity.type == "skill":
                sources.add(QuerySource.SKILL)
            elif entity.type in ["wing", "drawer"]:
                sources.add(QuerySource.MEMPALACE)
            elif entity.type in ["project", "file", "concept"]:
                sources.add(QuerySource.VAULT)
        
        # Context-based
        if context.get("default_source"):
            sources.add(context["default_source"])
        
        # If no sources determined, use all
        if not sources:
            sources = {QuerySource.VAULT, QuerySource.MEMPALACE, QuerySource.SKILL}
        
        return list(sources)
    
    # ============================================================
    # FILTER EXTRACTION
    # ============================================================
    
    def _extract_filters(self, query: str, entities: List[QueryEntity]) -> List[QueryFilter]:
        """Extract structured filters from query."""
        filters = []
        
        # Source filter
        source_entities = [e for e in entities if e.type in ["skill", "project", "wing"]]
        if source_entities:
            sources = [e.text for e in source_entities]
            filters.append(QueryFilter("source", "in", sources))
        
        # PARA category filter
        for entity in entities:
            if entity.type == "project":
                filters.append(QueryFilter("para_category", "eq", "projeto"))
            elif entity.type == "area":
                filters.append(QueryFilter("para_category", "eq", "area"))
            elif entity.type == "resource":
                filters.append(QueryFilter("para_category", "eq", "recurso"))
            elif entity.type == "wing":
                filters.append(QueryFilter("wing", "eq", entity.text))
        
        # Tag filter
        tag_matches = re.findall(r'#(\w+)', query)
        if tag_matches:
            filters.append(QueryFilter("tags", "contains", tag_matches))
        
        # Date filters (simplified)
        date_patterns = [
            (r"\b(hoje|today)\b", "today"),
            (r"\b(ontem|yesterday)\b", "yesterday"),
            (r"\b(esta semana|this week)\b", "this_week"),
            (r"\b(este mês|this month)\b", "this_month")
        ]
        for pattern, value in date_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                filters.append(QueryFilter("date", "eq", value))
        
        return filters
    
    # ============================================================
    # CAPABILITY DETERMINATION
    # ============================================================
    
    def _determine_capabilities(
        self, 
        intent: QueryIntent, 
        entities: List[QueryEntity], 
        sources: List[QuerySource]
    ) -> List[str]:
        """Determine required capabilities for query execution."""
        capabilities = []
        
        # Base capabilities by intent
        intent_capabilities = {
            QueryIntent.LIST: ["search", "list"],
            QueryIntent.FIND: ["search", "resolve_path"],
            QueryIntent.SYNTHESIZE: ["search", "retrieve", "synthesize"],
            QueryIntent.TRAVERSE: ["search", "graph_traverse", "resolve_entities"],
            QueryIntent.COMPARE: ["search", "retrieve", "compare"],
            QueryIntent.SUMMARIZE: ["search", "retrieve", "summarize"],
            QueryIntent.COUNT: ["search", "count"]
        }
        
        capabilities.extend(intent_capabilities.get(intent, ["search"]))
        
        # Source-specific capabilities
        for source in sources:
            if source == QuerySource.VAULT:
                capabilities.append("vault_search")
            elif source == QuerySource.MEMPALACE:
                capabilities.append("mempalace_search")
                capabilities.append("graph_traverse")
            elif source == QuerySource.SKILL:
                capabilities.append("skill_search")
        
        # Entity-specific capabilities
        entity_types = {e.type for e in entities}
        if "skill" in entity_types:
            capabilities.append("skill_manifest_parse")
        if "project" in entity_types:
            capabilities.append("project_metadata")
        if "wing" in entity_types or "drawer" in entity_types:
            capabilities.append("mempalace_structure")
        
        # Deduplicate
        return list(set(capabilities))
    
    # ============================================================
    # UTILITIES
    # ============================================================
    
    def explain_plan(self, plan: QueryPlan) -> str:
        """Generate human-readable explanation of query plan."""
        lines = [
            f"🎯 Intent: {plan.intent.value}",
            f"📦 Sources: {', '.join(s.value for s in plan.sources)}",
            f"🔍 Entities: {', '.join(f'{e.text} ({e.type})' for e in plan.entities) or 'none'}",
            f"🔧 Filters: {len(plan.filters)}",
            f"⚙️ Capabilities: {', '.join(plan.required_capabilities)}",
            f"📊 Max Results: {plan.max_results}",
            f"🧠 Synthesize: {'yes' if plan.synthesize else 'no'}",
            f"📝 Citation: {plan.citation_style}"
        ]
        return "\n".join(lines)


# ============================================================
# FACTORY
# ============================================================

def create_query_planner(config: Dict = None) -> QueryPlanner:
    """Create query planner with optional config."""
    return QueryPlanner(config)