"""
Knowledge Compounding Pipeline v1.0 — Distill Stage
Progressive summarization L1→L2→L3→L4 (Atomic Notes) with auto-linking and tagging.
"""

import re
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum


class DistillLayer(int, Enum):
    HIGHLIGHTS = 1      # Raw quotes, highlights, captures
    LITERATURE = 2      # Summary in own words, initial connections
    RESOURCE = 3        # Organized synthesis for practical use
    ATOMIC = 4          # One idea, own words, atomic, linkable


@dataclass
class LayerConfig:
    """Configuration for a distillation layer."""
    name: str
    description: str
    template: str
    min_length: int
    prompt_template: str = ""


@dataclass
class DistillConfig:
    """Configuration for distill stage."""
    vault_path: str = "C:/Users/mathe/Hermes_Brain"
    layers: Dict[int, LayerConfig] = field(default_factory=lambda: {
        1: LayerConfig(
            name="Highlights",
            description="Raw quotes, highlights, captures",
            template="templates/layer1-highlight.md",
            min_length=50,
            prompt_template="Extraia os highlights principais (citações, dados, insights) do texto abaixo. Mantenha aspas originais onde possível.\n\nTEXTO:\n{content}\n\nHIGHLIGHTS:"
        ),
        2: LayerConfig(
            name="Literature Notes",
            description="Summary in own words, initial connections",
            template="templates/layer2-literature.md",
            min_length=200,
            prompt_template="Escreva um resumo em suas próprias palavras do texto abaixo. Inclua conexões iniciais com outros conceitos.\n\nTEXTO:\n{content}\n\nLITERATURE NOTES:"
        ),
        3: LayerConfig(
            name="Project/Resource Notes",
            description="Organized synthesis for practical use",
            template="templates/layer3-resource.md",
            min_length=500,
            prompt_template="Crie uma nota de recurso organizada a partir do texto abaixo. Estruture para uso prático: conceitos-chave, aplicações, exemplos.\n\nTEXTO:\n{content}\n\nRESOURCE NOTE:"
        ),
        4: LayerConfig(
            name="Atomic Notes",
            description="One idea, own words, atomic, linkable",
            template="templates/layer4-atomic.md",
            min_length=100,
            prompt_template="Destile UMA ideia atômica do texto abaixo. Uma nota atômica = uma ideia, própria, atômica, linkável. Título claro, conceito único, conexões explícitas.\n\nTEXTO:\n{content}\n\nATOMIC NOTE:"
        )
    })
    
    # Auto-linking
    auto_link: Dict[str, Any] = field(default_factory=lambda: {
        "enabled": True,
        "min_similarity": 0.7,
        "max_links_per_note": 10,
        "link_types": ["references", "related", "contrasts", "extends"]
    })
    
    # Tagging
    tagging: Dict[str, Any] = field(default_factory=lambda: {
        "enabled": True,
        "suggest_tags": True,
        "tag_taxonomy_path": "30-Recursos/_taxonomy/tags.md",
        "max_tags_per_note": 8
    })
    
    # Processing
    target_layers: List[int] = field(default_factory=lambda: [1, 2, 3, 4])
    synthesis_model: str = "nemotron-3-ultra"
    max_concurrent: int = 3


@dataclass
class DistillResult:
    """Result of distillation operation."""
    source_path: str
    layer: int
    output_path: Optional[str] = None
    content: str = ""
    links_created: List[Dict[str, str]] = field(default_factory=list)
    tags_suggested: List[str] = field(default_factory=list)
    tokens_used: int = 0
    success: bool = False
    error: Optional[str] = None


class DistillEngine:
    """
    Progressive summarization engine (L1→L2→L3→L4).
    
    Layer 1 - Highlights: Raw quotes, verbatim captures
    Layer 2 - Literature Notes: Summary in own words, connections
    Layer 3 - Resource Notes: Organized for practical use
    Layer 4 - Atomic Notes: One atomic idea, linkable
    
    Each layer builds on the previous, creating a knowledge compounding effect.
    """
    
    def __init__(self, config: Optional[DistillConfig] = None):
        self.config = config or DistillConfig()
        self._vault_path = Path(self.config.vault_path)
    
    def _load_template(self, layer: int) -> str:
        """Load Jinja2 template for layer."""
        template_path = self._vault_path / self.config.layers[layer].template
        if template_path.exists():
            return template_path.read_text(encoding="utf-8")
        
        # Default templates
        defaults = {
            1: """---
id: {{id}}
layer: 1
name: Highlights
source: {{source}}
tags: {{tags}}
created: {{date}}
---

# Highlights: {{title}}

{{content}}

---
*Source: {{source_path}}*""",
            2: """---
id: {{id}}
layer: 2
name: Literature Notes
source: {{source}}
tags: {{tags}}
created: {{date}}
---

# Literature Notes: {{title}}

{{content}}

## Connections
{{connections}}

---
*Source: {{source_path}}*""",
            3: """---
id: {{id}}
layer: 3
name: Resource Notes
source: {{source}}
tags: {{tags}}
created: {{date}}
---

# Resource: {{title}}

## Key Concepts
{{key_concepts}}

## Applications
{{applications}}

## Examples
{{examples}}

---
*Source: {{source_path}}*""",
            4: """---
id: {{id}}
layer: 4
name: Atomic Note
source: {{source}}
tags: {{tags}}
created: {{date}}
links: {{links}}
---

# {{title}}

{{content}}

## Links
{{links_formatted}}

---
*Source: {{source_path}}*"""
        }
        return defaults.get(layer, "")
    
    def _generate_id(self, prefix: str = "atm") -> str:
        """Generate unique ID."""
        import uuid
        return f"{prefix}-{uuid.uuid4().hex[:8]}"
    
    def _parse_note(self, file_path: Path) -> Tuple[Dict[str, Any], str]:
        """Parse frontmatter and body from note."""
        content = file_path.read_text(encoding="utf-8")
        
        if content.startswith("---"):
            try:
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    frontmatter = yaml.safe_load(parts[1]) or {}
                    body = parts[2].strip()
                    return frontmatter, body
            except Exception:
                pass
        
        return {}, content
    
    def _write_note(self, file_path: Path, frontmatter: Dict[str, Any], body: str):
        """Write note with frontmatter."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("---\n")
            f.write(yaml.dump(frontmatter, allow_unicode=True, sort_keys=False))
            f.write("---\n\n")
            f.write(body)
    
    def _synthesize(self, prompt: str, layer: int) -> str:
        """
        Synthesize content using LLM.
        This is a placeholder - in production, call actual LLM.
        """
        # Placeholder - would integrate with token_optimization or direct LLM call
        # For now, return structured mock based on layer
        layer_names = {1: "Highlights", 2: "Literature Notes", 3: "Resource Notes", 4: "Atomic Note"}
        return f"[{layer_names[layer]} synthesized from source]\n\n{prompt[:500]}..."
    
    def _extract_links(self, content: str, existing_notes: List[Path]) -> List[Dict[str, str]]:
        """Extract potential links to other notes."""
        links = []
        if not self.config.auto_link.get("enabled", True):
            return links
        
        # Simple keyword-based linking
        keywords = re.findall(r'\b\w{5,}\b', content.lower())
        keyword_set = set(keywords)
        
        for note_path in existing_notes[:100]:  # Limit search
            try:
                fm, _ = self._parse_note(note_path)
                note_tags = set(fm.get("tags", []))
                note_title = fm.get("title", note_path.stem).lower()
                
                # Check tag overlap
                overlap = keyword_set & note_tags
                if overlap or any(kw in note_title for kw in keyword_set):
                    links.append({
                        "target": str(note_path.relative_to(self._vault_path)),
                        "title": note_title,
                        "type": "related",
                        "matched_keywords": list(overlap)[:3]
                    })
                    
                    if len(links) >= self.config.auto_link.get("max_links_per_note", 10):
                        break
            except Exception:
                pass
        
        return links
    
    def _suggest_tags(self, content: str, layer: int) -> List[str]:
        """Suggest tags for content."""
        if not self.config.tagging.get("enabled", True):
            return []
        
        tags = []
        content_lower = content.lower()
        
        # Layer-specific tags
        layer_tags = {
            1: ["#highlight", "#quote", "#capture"],
            2: ["#literature-note", "#summary", "#connection"],
            3: ["#resource", "#reference", "#practical"],
            4: ["#atomic", "#concept", "#linkable"]
        }
        tags.extend(layer_tags.get(layer, []))
        
        # Topic tags from content
        topic_patterns = {
            "#python": ["python", "py"],
            "#llm": ["llm", "gpt", "transformer", "token"],
            "#rag": ["rag", "retrieval", "embedding"],
            "#ml": ["machine learning", "ml", "model"],
            "#architecture": ["architecture", "system design", "microservices"],
            "#productivity": ["productivity", "workflow", "automation"],
            "#second-brain": ["second brain", "para", "zettelkasten", "atomic"]
        }
        
        for tag, keywords in topic_patterns.items():
            if any(kw in content_lower for kw in keywords):
                tags.append(tag)
        
        # Limit tags
        max_tags = self.config.tagging.get("max_tags_per_note", 8)
        return tags[:max_tags]
    
    def distill_note(
        self,
        source_path: str,
        target_layer: int = 4,
        auto_link: bool = True,
        auto_tag: bool = True
    ) -> DistillResult:
        """
        Distill a note to target layer (or all layers up to target).
        
        Args:
            source_path: Path to source note (relative to vault)
            target_layer: Target layer (1-4) or max layer to create
            auto_link: Create links to related notes
            auto_tag: Suggest and apply tags
            
        Returns:
            DistillResult for highest layer created
        """
        source_file = self._vault_path / source_path
        if not source_file.exists():
            return DistillResult(
                source_path=source_path,
                layer=target_layer,
                success=False,
                error=f"Source not found: {source_path}"
            )
        
        # Parse source
        frontmatter, body = self._parse_note(source_file)
        current_layer = frontmatter.get("layer", 0)
        
        # Already at or above target?
        if current_layer >= target_layer:
            return DistillResult(
                source_path=source_path,
                layer=current_layer,
                output_path=source_path,
                success=True,
                content=body
            )
        
        # Find all existing notes for linking
        all_notes = list(self._vault_path.rglob("*.md"))
        
        result = DistillResult(source_path=source_path, layer=target_layer)
        
        # Process each layer from current+1 to target
        for layer in range(max(current_layer + 1, 1), target_layer + 1):
            if layer not in self.config.target_layers:
                continue
            
            layer_config = self.config.layers[layer]
            
            # Build prompt
            prompt = layer_config.prompt_template.format(content=body)
            
            # Synthesize
            synthesized = self._synthesize(prompt, layer)
            
            # Generate output path
            output_path = self._get_output_path(source_path, layer)
            
            # Extract links
            links = []
            if auto_link:
                links = self._extract_links(synthesized, all_notes)
            
            # Suggest tags
            suggested_tags = []
            if auto_tag:
                suggested_tags = self._suggest_tags(synthesized, layer)
            
            # Build frontmatter
            new_frontmatter = {
                "id": self._generate_id(f"l{layer}"),
                "layer": layer,
                "name": layer_config.name,
                "source": source_path,
                "source_layer": current_layer,
                "tags": suggested_tags,
                "links": [l["target"] for l in links],
                "created": datetime.now().strftime("%Y-%m-%d"),
                "modified": datetime.now().strftime("%Y-%m-%d")
            }
            
            # Apply template
            template = self._load_template(layer)
            body_content = template.replace("{{id}}", new_frontmatter["id"])\
                                   .replace("{{title}}", frontmatter.get("title", source_file.stem))\
                                   .replace("{{content}}", synthesized)\
                                   .replace("{{source}}", source_path)\
                                   .replace("{{source_path}}", source_path)\
                                   .replace("{{tags}}", str(suggested_tags))\
                                   .replace("{{date}}", new_frontmatter["created"])\
                                   .replace("{{connections}}", "")\
                                   .replace("{{key_concepts}}", "")\
                                   .replace("{{applications}}", "")\
                                   .replace("{{examples}}", "")\
                                   .replace("{{links}}", str([l["target"] for l in links]))\
                                   .replace("{{links_formatted}}", "\n".join(["-[[" + l['target'] + "]]|" + l['title'] + "]" for l in links]))
            
            # Write file
            try:
                output_file = self._vault_path / output_path
                self._write_note(output_file, new_frontmatter, body_content)
                
                result.output_path = output_path
                result.content = body_content
                result.layer = layer
                result.links_created = links
                result.tags_suggested = suggested_tags
                result.success = True
                
                # Update for next layer
                body = synthesized
                current_layer = layer
                
            except Exception as e:
                result.error = str(e)
                result.success = False
                break
        
        return result
    
    def _get_output_path(self, source_path: str, layer: int) -> str:
        """Generate output path for distilled note."""
        source_file = Path(source_path)
        stem = source_file.stem
        parent = source_file.parent
        
        # Determine destination folder based on layer
        layer_folders = {
            1: "00-Inbox/Highlights",
            2: "30-Recursos/Literature-Notes",
            3: "30-Recursos/Resource-Notes",
            4: "30-Recursos/Atomic-Notes"
        }
        
        folder = layer_folders.get(layer, "30-Recursos")
        return f"{folder}/{stem}-L{layer}.md"
    
    def batch_distill(
        self,
        source_paths: List[str],
        target_layer: int = 4,
        auto_link: bool = True,
        auto_tag: bool = True
    ) -> List[DistillResult]:
        """Distill multiple notes."""
        results = []
        for path in source_paths:
            result = self.distill_note(path, target_layer, auto_link, auto_tag)
            results.append(result)
        return results
    
    def get_pending_distill(self, max_layer: int = 3) -> List[str]:
        """Get notes that can be distilled further."""
        pending = []
        for note_path in self._vault_path.rglob("*.md"):
            try:
                fm, _ = self._parse_note(note_path)
                layer = fm.get("layer", 0)
                if 0 < layer < max_layer:
                    pending.append(str(note_path.relative_to(self._vault_path)))
            except Exception:
                pass
        return pending


def create_distill_engine(config: Optional[DistillConfig] = None) -> DistillEngine:
    """Factory function to create distill engine."""
    return DistillEngine(config)


__all__ = [
    "DistillEngine",
    "DistillConfig",
    "DistillResult",
    "DistillLayer",
    "LayerConfig",
    "create_distill_engine"
]