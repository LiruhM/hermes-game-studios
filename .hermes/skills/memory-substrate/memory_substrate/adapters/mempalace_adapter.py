"""
Memory Substrate v1.0 — MemPalace Adapter
MemPalace MCP operations: drawers, wings, rooms, tunnels, KG, wake-up.
"""

import requests
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..models import (
    MemoryChunk, SourceType, PARALayer, PARACategory, DrawerType,
    SearchResult
)


@dataclass
class MemPalaceAdapterConfig:
    mcp_endpoint: str = "http://localhost:8765"
    poll_interval_seconds: int = 300
    wings: List[str] = None
    timeout: int = 30
    retry_attempts: int = 3
    
    def __post_init__(self):
        if self.wings is None:
            self.wings = ["10_projetos", "areas", "hermes_brain", "inbox", "recursos"]


class MemPalaceAdapter:
    """
    Adapter for MemPalace MCP (Model Context Protocol).
    Provides drawer, wing, room, tunnel, KG, and wake-up operations.
    """
    
    def __init__(self, config: MemPalaceAdapterConfig):
        self.config = config
        # MCP endpoint must include /mcp path for MCP protocol
        base = config.mcp_endpoint.rstrip("/")
        if not base.endswith("/mcp"):
            self.endpoint = base + "/mcp"
        else:
            self.endpoint = base
        self.session = requests.Session()
        self.session.timeout = config.timeout
        
        # Wing to PARA category mapping
        self.wing_to_category = {
            "10_projetos": PARACategory.PROJECT,
            "areas": PARACategory.AREA,
            "hermes_brain": PARACategory.SYSTEM,
            "inbox": PARACategory.META,
            "recursos": PARACategory.RESOURCE
        }
        
        # Drawer type to PARA layer mapping
        self.type_to_layer = {
            DrawerType.ENTITY: PARALayer.ATOMIC,
            DrawerType.TUNNEL: PARALayer.RESOURCE,
            DrawerType.HALLWAY: PARALayer.RESOURCE,
            DrawerType.NOTE: PARALayer.LITERATURE
        }
    
    # ============================================================
    # LOW-LEVEL MCP CALLS
    # ============================================================
    
    def _call(self, method: str, params: Dict = None) -> Dict:
        """Call MCP method with retry logic."""
        # For MCP tools, we need to use tools/call
        if method.startswith("mempalace_"):
            payload = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": method,
                    "arguments": params or {}
                },
                "id": 1
            }
        else:
            payload = {
                "jsonrpc": "2.0",
                "method": method,
                "params": params or {},
                "id": 1
            }
        
        for attempt in range(self.config.retry_attempts):
            try:
                response = self.session.post(
                    self.endpoint,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                result = response.json()
                
                if "error" in result:
                    raise Exception(f"MCP Error: {result['error']}")
                
                return result.get("result", {})
                
            except requests.RequestException as e:
                if attempt == self.config.retry_attempts - 1:
                    raise Exception(f"MCP call failed after {self.config.retry_attempts} attempts: {e}")
    
    # ============================================================
    # DRAWER OPERATIONS
    # ============================================================
    
    def get_drawer(self, drawer_id: str) -> Dict:
        """Get a single drawer by ID."""
        result = self._call("mempalace_get_drawer", {"drawer_id": drawer_id})
        return self._parse_mcp_result(result)
    
    def list_drawers(
        self, 
        wing: str = None, 
        room: str = None, 
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """List drawers with optional filters."""
        params = {"limit": limit, "offset": offset}
        if wing:
            params["wing"] = wing
        if room:
            params["room"] = room
        result = self._call("mempalace_list_drawers", params)
        return self._parse_mcp_result(result)
    
    def create_drawer(
        self, 
        wing: str, 
        room: str, 
        content: str, 
        metadata: Dict = None,
        drawer_type: str = "note"
    ) -> Dict:
        """Create a new drawer."""
        result = self._call("mempalace_add_drawer", {
            "wing": wing,
            "room": room,
            "content": content,
            "metadata": metadata or {},
            "drawer_type": drawer_type
        })
        return self._parse_mcp_result(result)
    
    def update_drawer(
        self, 
        drawer_id: str, 
        content: str = None, 
        metadata: Dict = None
    ) -> Dict:
        """Update an existing drawer."""
        params = {"drawer_id": drawer_id}
        if content is not None:
            params["content"] = content
        if metadata is not None:
            params["metadata"] = metadata
        result = self._call("mempalace_update_drawer", params)
        return self._parse_mcp_result(result)
    
    def delete_drawer(self, drawer_id: str) -> bool:
        """Delete a drawer."""
        result = self._call("mempalace_delete_drawer", {"drawer_id": drawer_id})
        parsed = self._parse_mcp_result(result)
        return parsed.get("success", False)
    
    # ============================================================
    # STRUCTURE OPERATIONS
    # ============================================================
    
    def list_wings(self) -> Dict:
        """List all wings with drawer counts."""
        result = self._call("mempalace_list_wings", {})
        parsed = self._parse_mcp_result(result)
        # The API returns {wings: {...}}
        if isinstance(parsed, dict) and "wings" in parsed:
            return parsed["wings"]
        return parsed
    
    def list_rooms(self, wing: str = None) -> List[Dict]:
        """List rooms within a wing (or all rooms)."""
        params = {}
        if wing:
            params["wing"] = wing
        result = self._call("mempalace_list_rooms", params)
        return self._parse_mcp_result(result)
    
    def list_tunnels(self) -> List[Dict]:
        """List all cross-wing tunnels."""
        result = self._call("mempalace_list_tunnels", {})
        return self._parse_mcp_result(result)
    
    def list_hallways(self, wing: str = None) -> List[Dict]:
        """List within-wing hallway records."""
        params = {}
        if wing:
            params["wing"] = wing
        result = self._call("mempalace_list_hallways", params)
        return self._parse_mcp_result(result)
    
    # ============================================================
    # TUNNEL & GRAPH OPERATIONS
    # ============================================================
    
    def follow_tunnels(
        self, 
        wing: str, 
        room: str
    ) -> Dict:
        """Follow tunnels from a room to see what it connects to in other wings."""
        result = self._call("mempalace_follow_tunnels", {
            "wing": wing,
            "room": room
        })
        parsed = self._parse_mcp_result(result)
        # The API returns a list of connected rooms
        # Wrap in dict for consistency
        if isinstance(parsed, list):
            return {"connected_rooms": parsed, "count": len(parsed)}
        return parsed
    
    def find_tunnels(self, wing_a: str, wing_b: str) -> List[Dict]:
        """Find tunnels bridging two wings."""
        result = self._call("mempalace_find_tunnels", {
            "wing_a": wing_a,
            "wing_b": wing_b
        })
        return self._parse_mcp_result(result)
    
    def traverse(self, start_room: str, max_hops: int = 2) -> List[Dict]:
        """Walk the palace graph from a room."""
        result = self._call("mempalace_traverse", {
            "start_room": start_room,
            "max_hops": max_hops
        })
        return self._parse_mcp_result(result)
    
    # ============================================================
    # KNOWLEDGE GRAPH
    # ============================================================
    
    def kg_query(self, entity: str) -> Dict:
        """Query the knowledge graph for an entity's relationships."""
        result = self._call("mempalace_kg_query", {"entity": entity})
        return self._parse_mcp_result(result)
    
    def kg_stats(self) -> Dict:
        """Get KG overview: entities, triples, etc."""
        result = self._call("mempalace_kg_stats", {})
        return self._parse_mcp_result(result)
    
    def kg_timeline(self, entity: str = None) -> List[Dict]:
        """Chronological timeline of facts."""
        params = {}
        if entity:
            params["entity"] = entity
        result = self._call("mempalace_kg_timeline", params)
        parsed = self._parse_mcp_result(result)
        # The API returns {entity: "...", timeline: [...], count: N}
        if isinstance(parsed, dict) and "timeline" in parsed:
            return parsed["timeline"]
        return parsed
    
    def kg_entities(self, limit: int = 100) -> List[Dict]:
        """List all entities in the KG - not available in MCP, return empty list."""
        return []
    
    # ============================================================
    # OPERATIONS
    # ============================================================
    
    def wake_up(self, context: str = None) -> Dict:
        """Run MemPalace wake-up to inject relevant context.
        
        In MCP v3.6+, wake-up is done by calling mempalace_status which returns
        the palace overview, protocol, and AAAK spec.
        """
        result = self._call("mempalace_status", {})
        # The result contains content with text field that has JSON
        if "content" in result and isinstance(result["content"], list):
            for item in result["content"]:
                if item.get("type") == "text":
                    import json
                    try:
                        return json.loads(item["text"])
                    except json.JSONDecodeError:
                        return {"text": item["text"]}
        return result
    
    def status(self) -> Dict:
        """Get palace overview: drawers, wings, rooms."""
        result = self._call("mempalace_status", {})
        # The result contains content with text field that has JSON
        if "content" in result and isinstance(result["content"], list):
            for item in result["content"]:
                if item.get("type") == "text":
                    import json
                    try:
                        return json.loads(item["text"])
                    except json.JSONDecodeError:
                        return {"text": item["text"]}
        return result
    
    def check_duplicate(self, content: str, threshold: float = 0.9) -> Dict:
        """Check if content already exists in the palace."""
        result = self._call("mempalace_check_duplicate", {
            "content": content,
            "threshold": threshold
        })
        return self._parse_mcp_result(result)
    
    def get_aaak_spec(self) -> str:
        """Get the AAAK dialect specification."""
        result = self._call("mempalace_get_aaak_spec", {})
        parsed = self._parse_mcp_result(result)
        # The API returns {aaak_spec: "..."}
        if isinstance(parsed, dict) and "aaak_spec" in parsed:
            return parsed["aaak_spec"]
        return str(parsed)
    
    def diary_read(self, agent_name: str, last_n: int = 10, wing: str = None) -> List[Dict]:
        """Read recent diary entries."""
        params = {"agent_name": agent_name, "last_n": last_n}
        if wing:
            params["wing"] = wing
        result = self._call("mempalace_diary_read", params)
        return self._parse_mcp_result(result)
    
    def memories_filed_away(self) -> Dict:
        """Check if a recent palace checkpoint was saved."""
        result = self._call("mempalace_memories_filed_away", {})
        return self._parse_mcp_result(result)
    
    def hook_settings(self, settings: Dict = None) -> Dict:
        """Get or set hook behavior."""
        params = {}
        if settings:
            params["settings"] = settings
        result = self._call("mempalace_hook_settings", params)
        return self._parse_mcp_result(result)
    
    def reconnect(self) -> Dict:
        """Force reconnect to the palace database."""
        result = self._call("mempalace_reconnect", {})
        return self._parse_mcp_result(result)
    
    def _parse_mcp_result(self, result: Dict) -> Any:
        """Parse MCP result that contains content array with JSON text."""
        if "content" in result and isinstance(result["content"], list):
            for item in result["content"]:
                if item.get("type") == "text":
                    import json
                    try:
                        return json.loads(item["text"])
                    except json.JSONDecodeError:
                        return {"text": item["text"]}
        return result
    
    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """Semantic search in the palace."""
        result = self._call("mempalace_search", {
            "query": query,
            "limit": limit
        })
        parsed = self._parse_mcp_result(result)
        # The API returns {query, filters, total_before_filter, results}
        # Return just the results list for consistency
        if isinstance(parsed, dict) and "results" in parsed:
            return parsed["results"]
        return parsed
    
    # ============================================================
    # CONVERSION TO MEMORY CHUNKS
    # ============================================================
    
    def drawer_to_chunk(self, drawer: Dict) -> Dict:
        """Convert a MemPalace drawer to a MemoryChunk dict."""
        from ..models import (
            MemoryChunk, SourceType, PARALayer, PARACategory, DrawerType
        )
        
        # Determine PARA category from wing
        wing = drawer.get("wing", "")
        para_category = self._wing_to_para_category(wing)
        
        # Determine PARA layer from drawer type
        drawer_type_str = drawer.get("drawer_type", "note")
        drawer_type = DrawerType(drawer_type_str) if drawer_type_str in [e.value for e in DrawerType] else DrawerType.NOTE
        para_layer = self._drawer_type_to_layer(drawer_type)
        
        chunk = MemoryChunk(
            source=SourceType.MEMPALACE,
            source_id=drawer.get("id", ""),
            content=drawer.get("content", ""),
            title=drawer.get("metadata", {}).get("title", f"Drawer {drawer.get('id', '')[:8]}"),
            wing=drawer.get("wing"),
            room=drawer.get("room"),
            drawer_type=drawer_type,
            para_category=para_category,
            para_layer=para_layer,
            metadata=drawer.get("metadata", {}),
            links=drawer.get("links", []),
            created_at=drawer.get("created_at"),
            updated_at=drawer.get("updated_at")
        )
        
        # Extract tags from metadata
        if "tags" in drawer.get("metadata", {}):
            tags = drawer["metadata"]["tags"]
            if isinstance(tags, list):
                chunk.tags = [str(t).lstrip("#") for t in tags]
            elif isinstance(tags, str):
                chunk.tags = [t.strip().lstrip("#") for t in tags.split(",")]
        
        return chunk
    
    def _wing_to_para_category(self, wing: str) -> PARACategory:
        """Map wing to PARA category."""
        return self.wing_to_category.get(wing, PARACategory.META)
    
    def _drawer_type_to_layer(self, drawer_type) -> PARALayer:
        """Map drawer type to PARA layer."""
        return self.type_to_layer.get(drawer_type, PARALayer.LITERATURE)
    
    # ============================================================
    # HIGH-LEVEL OPERATIONS
    # ============================================================
    
    def get_all_drawers_as_chunks(self, limit_per_wing: int = 100) -> List[Dict]:
        """Get all drawers across all wings as MemoryChunk dicts."""
        all_chunks = []
        
        for wing in self.config.wings:
            drawers = self.list_drawers(wing=wing, limit=limit_per_wing)
            for drawer in drawers:
                chunk = self.drawer_to_chunk(drawer)
                all_chunks.append(chunk)
        
        return all_chunks
    
    def get_wing_stats(self) -> Dict:
        """Get statistics for each wing."""
        stats = {}
        for wing in self.config.wings:
            rooms_result = self.list_rooms(wing=wing)
            # list_rooms returns {wing: "...", rooms: {...}}
            rooms = rooms_result.get("rooms", {}) if isinstance(rooms_result, dict) else {}
            total_drawers = sum(rooms.values()) if isinstance(rooms, dict) else 0
            stats[wing] = {
                "rooms": len(rooms),
                "drawers": total_drawers,
                "room_details": rooms
            }
        return stats
    
    def health_check(self) -> Dict:
        """Comprehensive health check."""
        try:
            status = self.status()
            return {
                "healthy": True,
                "status": status,
                "wings": self.get_wing_stats(),
                "endpoint": self.endpoint
            }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "endpoint": self.endpoint
            }


# ============================================================
# FACTORY FUNCTION
# ============================================================

def create_mempalace_adapter(
    endpoint: str = "http://localhost:8765",
    **kwargs
) -> 'MemPalaceAdapter':
    """Create MemPalace adapter with default config."""
    config = MemPalaceAdapterConfig(mcp_endpoint=endpoint, **kwargs)
    return MemPalaceAdapter(config)