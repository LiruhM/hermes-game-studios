"""
Memory Substrate v1.0 — Graph Index
NetworkX-based knowledge graph for entity relationships and tunnel traversal.
"""

import json
import pickle
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict
import networkx as nx


@dataclass
class GraphIndexConfig:
    db_path: str
    entity_extraction: bool = True
    relation_extraction: bool = True
    max_nodes_per_chunk: int = 10
    similarity_threshold: float = 0.8
    
    def __post_init__(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)


class GraphIndex:
    """
    NetworkX-based knowledge graph for entity relationships.
    Supports tunnel traversal, entity linking, and graph queries.
    """
    
    def __init__(self, config: GraphIndexConfig):
        self.config = config
        self.graph = nx.MultiDiGraph()
        self._entity_to_chunks: Dict[str, Set[str]] = defaultdict(set)
        self._chunk_to_entities: Dict[str, Set[str]] = defaultdict(set)
        self._load_graph()
    
    def _load_graph(self):
        """Load graph from disk if exists."""
        if Path(self.config.db_path).exists():
            try:
                with open(self.config.db_path, 'rb') as f:
                    data = pickle.load(f)
                    self.graph = data.get('graph', nx.MultiDiGraph())
                    self._entity_to_chunks = data.get('entity_to_chunks', defaultdict(set))
                    self._chunk_to_entities = data.get('chunk_to_entities', defaultdict(set))
            except Exception:
                self.graph = nx.MultiDiGraph()
                self._entity_to_chunks = defaultdict(set)
                self._chunk_to_entities = defaultdict(set)
    
    def _save_graph(self):
        """Save graph to disk."""
        data = {
            'graph': self.graph,
            'entity_to_chunks': self._entity_to_chunks,
            'chunk_to_entities': self._chunk_to_entities
        }
        with open(self.config.db_path, 'wb') as f:
            pickle.dump(data, f)
    
    # ============================================================
    # ENTITY MANAGEMENT
    # ============================================================
    
    def add_chunk_entities(self, chunk_id: str, entities: List[str]):
        """Associate entities with a chunk."""
        for entity in entities:
            entity = entity.strip().lower()
            if not entity:
                continue
            
            # Add node if not exists
            if not self.graph.has_node(entity):
                self.graph.add_node(entity, type='entity', count=0)
            
            # Update count
            self.graph.nodes[entity]['count'] = self.graph.nodes[entity].get('count', 0) + 1
            
            # Link chunk to entity
            self._entity_to_chunks[entity].add(chunk_id)
            self._chunk_to_entities[chunk_id].add(entity)
    
    def remove_chunk_entities(self, chunk_id: str):
        """Remove chunk's entity associations."""
        entities = self._chunk_to_entities.get(chunk_id, set())
        for entity in entities:
            self._entity_to_chunks[entity].discard(chunk_id)
            
            # Update count
            if entity in self.graph:
                self.graph.nodes[entity]['count'] = max(0, self.graph.nodes[entity].get('count', 1) - 1)
                
                # Remove node if no more chunks
                if self.graph.nodes[entity].get('count', 0) == 0:
                    self.graph.remove_node(entity)
                    self._entity_to_chunks.pop(entity, None)
        
        self._chunk_to_entities.pop(chunk_id, None)
    
    def get_chunk_entities(self, chunk_id: str) -> Set[str]:
        """Get entities for a chunk."""
        return self._chunk_to_entities.get(chunk_id, set())
    
    def get_entity_chunks(self, entity: str) -> Set[str]:
        """Get chunks containing an entity."""
        return self._entity_to_chunks.get(entity.lower(), set())
    
    # ============================================================
    # RELATIONSHIP MANAGEMENT
    # ============================================================
    
    def add_relation(
        self, 
        source: str, 
        target: str, 
        relation_type: str = "related",
        weight: float = 1.0,
        metadata: Dict = None
    ):
        """Add a relationship between two entities."""
        source = source.strip().lower()
        target = target.strip().lower()
        
        if source == target:
            return
        
        # Ensure nodes exist
        for entity in [source, target]:
            if not self.graph.has_node(entity):
                self.graph.add_node(entity, type='entity', count=0)
        
        # Add edge
        self.graph.add_edge(
            source, target,
            type=relation_type,
            weight=weight,
            metadata=metadata or {}
        )
    
    def get_relations(self, entity: str) -> List[Dict]:
        """Get all relations for an entity."""
        entity = entity.strip().lower()
        relations = []
        
        if not self.graph.has_node(entity):
            return relations
        
        # Outgoing edges
        for _, target, data in self.graph.out_edges(entity, data=True):
            relations.append({
                "source": entity,
                "target": target,
                "type": data.get('type', 'related'),
                "weight": data.get('weight', 1.0),
                "metadata": data.get('metadata', {}),
                "direction": "outgoing"
            })
        
        # Incoming edges
        for source, _, data in self.graph.in_edges(entity, data=True):
            relations.append({
                "source": source,
                "target": entity,
                "type": data.get('type', 'related'),
                "weight": data.get('weight', 1.0),
                "metadata": data.get('metadata', {}),
                "direction": "incoming"
            })
        
        return relations
    
    def get_neighbors(self, entity: str, max_depth: int = 1) -> Set[str]:
        """Get neighboring entities within max_depth."""
        entity = entity.strip().lower()
        if not self.graph.has_node(entity):
            return set()
        
        neighbors = set()
        current_level = {entity}
        
        for _ in range(max_depth):
            next_level = set()
            for node in current_level:
                if self.graph.has_node(node):
                    # Outgoing
                    for _, target in self.graph.out_edges(node):
                        if target not in neighbors:
                            next_level.add(target)
                            neighbors.add(target)
                    
                    # Incoming
                    for source, _ in self.graph.in_edges(node):
                        if source not in neighbors:
                            next_level.add(source)
                            neighbors.add(source)
            
            current_level = next_level
            if not current_level:
                break
        
        neighbors.discard(entity)  # Remove self
        return neighbors
    
    # ============================================================
    # TUNNEL TRAVERSAL (MemPalace specific)
    # ============================================================
    
    def find_tunnels_between(self, wing_a: str, wing_b: str) -> List[Dict]:
        """Find tunnel entities connecting two wings."""
        tunnels = []
        
        # Find entities tagged with both wings
        wing_a_entities = set()
        wing_b_entities = set()
        
        for node, data in self.graph.nodes(data=True):
            metadata = data.get('metadata', {})
            if metadata.get('wing') == wing_a:
                wing_a_entities.add(node)
            elif metadata.get('wing') == wing_b:
                wing_b_entities.add(node)
        
        # Find connections between wing entities
        for entity_a in wing_a_entities:
            for entity_b in wing_b_entities:
                if self.graph.has_edge(entity_a, entity_b):
                    for _, _, data in self.graph.out_edges(entity_a, data=True):
                        if data.get('type') == 'tunnel':
                            tunnels.append({
                                "from_wing": wing_a,
                                "to_wing": wing_b,
                                "from_entity": entity_a,
                                "to_entity": entity_b,
                                "tunnel_type": data.get('metadata', {}).get('tunnel_type', 'unknown'),
                                "weight": data.get('weight', 1.0)
                            })
        
        return tunnels
    
    def traverse_from(self, entity: str, max_depth: int = 3, direction: str = "both") -> List[Dict]:
        """Traverse graph from an entity, returning path information."""
        entity = entity.strip().lower()
        if not self.graph.has_node(entity):
            return []
        
        paths = []
        visited = set()
        
        def dfs(current: str, path: List[str], depth: int):
            if depth > max_depth or current in visited:
                return
            
            visited.add(current)
            
            # Get neighbors based on direction
            neighbors = set()
            if direction in ("outgoing", "both"):
                neighbors.update(self.graph.successors(current))
            if direction in ("incoming", "both"):
                neighbors.update(self.graph.predecessors(current))
            
            for neighbor in neighbors:
                if neighbor not in visited:
                    edge_data = self.graph.get_edge_data(current, neighbor)
                    edge_info = list(edge_data.values())[0] if edge_data else {}
                    
                    new_path = path + [{
                        "entity": neighbor,
                        "relation": edge_info.get('type', 'related'),
                        "weight": edge_info.get('weight', 1.0),
                        "metadata": edge_info.get('metadata', {})
                    }]
                    
                    paths.append({
                        "start": entity,
                        "path": new_path,
                        "depth": depth + 1
                    })
                    
                    dfs(neighbor, new_path, depth + 1)
        
        dfs(entity, [], 0)
        return paths
    
    # ============================================================
    # ENTITY EXTRACTION
    # ============================================================
    
    def extract_entities_from_text(self, text: str) -> List[str]:
        """Extract entities from text using simple patterns."""
        import re
        
        entities = set()
        
        # Pattern 1: Capitalized phrases (potential proper nouns)
        # Matches: "Token Optimization", "MemPalace", "Hermes Agent"
        proper_nouns = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
        for noun in proper_nouns:
            if len(noun) > 2 and noun.lower() not in ('the', 'and', 'for', 'with', 'this', 'that'):
                entities.add(noun.lower())
        
        # Pattern 2: Technical terms with hyphens/underscores
        # Matches: "token-optimization", "sql_vec", "llm_eval"
        tech_terms = re.findall(r'\b[a-z]+(?:[-_][a-z]+)+\b', text, re.IGNORECASE)
        for term in tech_terms:
            if len(term) > 3:
                entities.add(term.lower())
        
        # Pattern 3: Acronyms
        # Matches: "RAG", "API", "CPU", "GPU"
        acronyms = re.findall(r'\b[A-Z]{2,}\b', text)
        for acronym in acronyms:
            if acronym not in ('THE', 'AND', 'FOR', 'WITH', 'THIS', 'THAT'):
                entities.add(acronym.lower())
        
        return list(entities)
    
    def auto_link_chunk(self, chunk_id: str, text: str, existing_entities: List[str] = None):
        """Automatically extract and link entities for a chunk."""
        # Extract new entities
        new_entities = self.extract_entities_from_text(text)
        
        # Combine with existing
        all_entities = set(new_entities)
        if existing_entities:
            all_entities.update(e.lower() for e in existing_entities)
        
        # Add to graph
        self.add_chunk_entities(chunk_id, list(all_entities))
        
        # Link co-occurring entities
        entities_list = list(all_entities)
        for i, e1 in enumerate(entities_list):
            for e2 in entities_list[i+1:]:
                self.add_relation(e1, e2, "co_occurs", weight=0.5)
        
        return list(all_entities)
    
    # ============================================================
    # QUERY OPERATIONS
    # ============================================================
    
    def search_entities(self, query: str, limit: int = 10) -> List[Dict]:
        """Search for entities matching query."""
        query = query.lower()
        results = []
        
        for node, data in self.graph.nodes(data=True):
            if query in node.lower():
                results.append({
                    "entity": node,
                    "count": data.get('count', 0),
                    "type": data.get('type', 'entity'),
                    "metadata": data.get('metadata', {})
                })
        
        # Sort by count (popularity)
        results.sort(key=lambda x: x['count'], reverse=True)
        return results[:limit]
    
    def get_subgraph(self, entities: List[str], max_depth: int = 1) -> nx.MultiDiGraph:
        """Extract subgraph for given entities."""
        subgraph = nx.MultiDiGraph()
        entities_lower = [e.lower() for e in entities]
        
        for entity in entities_lower:
            if self.graph.has_node(entity):
                # Add node
                subgraph.add_node(entity, **self.graph.nodes[entity])
                
                # Add neighbors up to max_depth
                neighbors = self.get_neighbors(entity, max_depth)
                for neighbor in neighbors:
                    if self.graph.has_node(neighbor):
                        subgraph.add_node(neighbor, **self.graph.nodes[neighbor])
                        
                        # Add edges between them
                        for _, target, data in self.graph.out_edges(entity, data=True):
                            if target in neighbors:
                                subgraph.add_edge(entity, target, **data)
                        
                        for source, _, data in self.graph.in_edges(entity, data=True):
                            if source in neighbors:
                                subgraph.add_edge(source, entity, **data)
        
        return subgraph
    
    def get_central_entities(self, limit: int = 20) -> List[Dict]:
        """Get most central entities by degree centrality."""
        if self.graph.number_of_nodes() == 0:
            return []
        
        centrality = nx.degree_centrality(self.graph)
        sorted_entities = sorted(centrality.items(), key=lambda x: x[1], reverse=True)
        
        return [
            {"entity": entity, "centrality": score, "degree": self.graph.degree(entity)}
            for entity, score in sorted_entities[:limit]
        ]
    
    def get_stats(self) -> Dict:
        """Get graph statistics."""
        return {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "density": nx.density(self.graph) if self.graph.number_of_nodes() > 1 else 0,
            "connected_components": nx.number_weakly_connected_components(self.graph),
            "avg_clustering": nx.average_clustering(self.graph.to_undirected()) if self.graph.number_of_nodes() > 0 else 0
        }
    
    def save(self):
        """Save graph to disk."""
        self._save_graph()
    
    def clear(self):
        """Clear the graph."""
        self.graph.clear()
        self._entity_to_chunks.clear()
        self._chunk_to_entities.clear()
        self._save_graph()


# ============================================================
# FACTORY
# ============================================================

def create_graph_index(config: GraphIndexConfig = None) -> GraphIndex:
    """Create graph index with default or custom config."""
    if config is None:
        config = GraphIndexConfig(
            db_path="90-Sistema/_embeddings/graph.pkl"
        )
    return GraphIndex(config)