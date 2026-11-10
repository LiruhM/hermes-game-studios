"""
Knowledge Compounding Pipeline v1.0 — Express Stage
Generate outputs from atomic notes: article, report, doc, newsletter.
"""

import re
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum


class OutputType(str, Enum):
    ARTICLE = "article"
    REPORT = "report"
    DOC = "doc"
    NEWSLETTER = "newsletter"


@dataclass
class OutputConfig:
    """Configuration for an output type."""
    name: str
    template: str
    sections: List[str]
    description: str = ""


@dataclass
class ExpressConfig:
    """Configuration for express stage."""
    vault_path: str = "C:/Users/mathe/Hermes_Brain"
    output_types: Dict[str, OutputConfig] = field(default_factory=lambda: {
        "article": OutputConfig(
            name="Article",
            template="templates/express-article.md",
            sections=["intro", "body", "conclusion", "references"],
            description="Long-form article for blog/publication"
        ),
        "report": OutputConfig(
            name="Report",
            template="templates/express-report.md",
            sections=["executive_summary", "findings", "recommendations", "appendix"],
            description="Structured report for stakeholders"
        ),
        "doc": OutputConfig(
            name="Documentation",
            template="templates/express-doc.md",
            sections=["overview", "details", "examples", "see_also"],
            description="Technical documentation"
        ),
        "newsletter": OutputConfig(
            name="Newsletter",
            template="templates/express-newsletter.md",
            sections=["headline", "stories", "insights", "cta"],
            description="Email newsletter format"
        )
    })
    
    # Synthesis
    synthesis_model: str = "nemotron-3-ultra"
    max_sources: int = 15
    citation_style: str = "wiki"  # wiki | markdown | apa
    
    # Output
    output_dir: str = "10-Projetos/_outputs/express/"
    auto_save: bool = True
    
    # Quality
    min_sources: int = 3
    max_tokens_per_section: int = 1000


@dataclass
class ExpressResult:
    """Result of express generation."""
    output_type: str
    topic: str
    sources: List[str]
    output_path: Optional[str] = None
    content: str = ""
    citations: List[Dict[str, str]] = field(default_factory=list)
    tokens_used: int = 0
    success: bool = False
    error: Optional[str] = None


class ExpressEngine:
    """
    Output generation engine from atomic notes.
    
    Takes atomic notes (Layer 4) and synthesizes them into:
    - Articles: Long-form content
    - Reports: Structured analysis
    - Docs: Technical documentation
    - Newsletters: Curated updates
    
    Uses citation tracking and token optimization.
    """
    
    def __init__(self, config: Optional[ExpressConfig] = None):
        self.config = config or ExpressConfig()
        self._vault_path = Path(self.config.vault_path)
        # Resolve output_dir relative to vault_path if not absolute
        output_dir = Path(self.config.output_dir)
        if not output_dir.is_absolute():
            self._output_path = self._vault_path / output_dir
        else:
            self._output_path = output_dir
        self._output_path.mkdir(parents=True, exist_ok=True)
    
    def _load_template(self, output_type: str) -> str:
        """Load template for output type."""
        template_path = self._vault_path / self.config.output_types[output_type].template
        if template_path.exists():
            return template_path.read_text(encoding="utf-8")
        
        # Default templates
        defaults = {
            "article": """---
title: "{{title}}"
type: article
topic: "{{topic}}"
sources: {{sources}}
created: {{date}}
tags: {{tags}}
---

# {{title}}

## Introduction
{{intro}}

## Body
{{body}}

## Conclusion
{{conclusion}}

## References
{{references}}
""",
            "report": """---
title: "{{title}}"
type: report
topic: "{{topic}}"
sources: {{sources}}
created: {{date}}
tags: {{tags}}
---

# {{title}}

## Executive Summary
{{executive_summary}}

## Findings
{{findings}}

## Recommendations
{{recommendations}}

## Appendix
{{appendix}}

## Sources
{{references}}
""",
            "doc": """---
title: "{{title}}"
type: doc
topic: "{{topic}}"
sources: {{sources}}
created: {{date}}
tags: {{tags}}
---

# {{title}}

## Overview
{{overview}}

## Details
{{details}}

## Examples
{{examples}}

## See Also
{{see_also}}

## References
{{references}}
""",
            "newsletter": """---
title: "{{title}}"
type: newsletter
topic: "{{topic}}"
sources: {{sources}}
created: {{date}}
tags: {{tags}}
---

# {{headline}}

{{intro}}

## Stories
{{stories}}

## Insights
{{insights}}

## Call to Action
{{cta}}

---
*Sources: {{references}}*
"""
        }
        return defaults.get(output_type, "")
    
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
    
    def _find_atomic_notes(self, topic: str, max_sources: int = None) -> List[Path]:
        """Find atomic notes related to topic."""
        max_sources = max_sources or self.config.max_sources
        atomic_notes = []
        
        # Search in atomic notes folder
        atomic_folder = self._vault_path / "30-Recursos/Atomic-Notes"
        if atomic_folder.exists():
            for note_path in atomic_folder.rglob("*.md"):
                fm, body = self._parse_note(note_path)
                if fm.get("layer") == 4:  # Atomic layer
                    # Check relevance (simple keyword match)
                    tags = fm.get("tags", [])
                    title = fm.get("title", note_path.stem).lower()
                    content = (body + " " + " ".join(tags) + " " + title).lower()
                    
                    if any(kw in content for kw in topic.lower().split()):
                        atomic_notes.append(note_path)
                        
                        if len(atomic_notes) >= max_sources:
                            break
        
        # Also search literature and resource notes
        for folder_name in ["Literature-Notes", "Resource-Notes"]:
            folder = self._vault_path / f"30-Recursos/{folder_name}"
            if folder.exists():
                for note_path in folder.rglob("*.md"):
                    fm, body = self._parse_note(note_path)
                    if fm.get("layer") in [2, 3]:
                        tags = fm.get("tags", [])
                        title = fm.get("title", note_path.stem).lower()
                        content = (body + " " + " ".join(tags) + " " + title).lower()
                        
                        if any(kw in content for kw in topic.lower().split()):
                            atomic_notes.append(note_path)
                            
                            if len(atomic_notes) >= max_sources:
                                break
        
        return atomic_notes[:max_sources]
    
    def _synthesize_section(self, section: str, topic: str, sources: List[Dict], context: str) -> str:
        """
        Synthesize a section using LLM.
        Placeholder - would integrate with actual LLM.
        """
        # This would call the actual LLM with token optimization
        # For now, return structured placeholder
        source_refs = "\n".join([f"- {s['title']} ({s['path']})" for s in sources])
        
        return f"[{section.upper()} for '{topic}' synthesized from {len(sources)} sources]\n\n{context[:500]}...\n\nSources:\n{source_refs}"
    
    def _extract_citations(self, sources: List[Dict]) -> List[Dict[str, str]]:
        """Extract citations from sources."""
        citations = []
        for i, source in enumerate(sources, 1):
            citations.append({
                "id": str(i),
                "title": source.get("title", "Untitled"),
                "path": source.get("path", ""),
                "layer": str(source.get("layer", "?")),
                "style": self.config.citation_style
            })
        return citations
    
    def _format_references(self, citations: List[Dict[str, str]]) -> str:
        """Format references based on citation style."""
        if self.config.citation_style == "wiki":
            refs = []
            for c in citations:
                path = c['path']
                title = c['title']
                layer = c['layer']
                refs.append("[[{}|{}]] (Layer {})".format(path, title, layer))
            return "\n".join(refs)
        elif self.config.citation_style == "markdown":
            refs = []
            for c in citations:
                title = c['title']
                path = c['path']
                refs.append("- [{}]({})".format(title, path))
            return "\n".join(refs)
        else:  # apa
            refs = []
            for c in citations:
                title = c['title']
                path = c['path']
                refs.append("{}. Retrieved from {}".format(title, path))
            return "\n".join(refs)
    
    def generate(
        self,
        topic: str,
        output_type: str = "article",
        sources: Optional[List[str]] = None,
        max_sources: int = None,
        context: str = "",
        additional_instructions: str = ""
    ) -> ExpressResult:
        """
        Generate output from atomic notes.
        
        Args:
            topic: Topic/theme for the output
            output_type: article | report | doc | newsletter
            sources: Specific source note paths (optional)
            max_sources: Maximum sources to use
            context: Additional context for synthesis
            additional_instructions: Extra instructions for LLM
            
        Returns:
            ExpressResult with generated content
        """
        if output_type not in self.config.output_types:
            return ExpressResult(
                output_type=output_type,
                topic=topic,
                sources=[],
                success=False,
                error="Unknown output type: {}".format(output_type)
            )
        
        # Find sources
        source_notes = []
        if sources:
            for src in sources:
                path = self._vault_path / src
                if path.exists():
                    fm, body = self._parse_note(path)
                    source_notes.append({
                        "path": src,
                        "title": fm.get("title", path.stem),
                        "layer": fm.get("layer", 0),
                        "content": body,
                        "tags": fm.get("tags", []),
                        "frontmatter": fm
                    })
        else:
            # Auto-find atomic notes
            note_paths = self._find_atomic_notes(topic, max_sources or self.config.max_sources)
            for path in note_paths:
                fm, body = self._parse_note(path)
                source_notes.append({
                    "path": str(path.relative_to(self._vault_path)),
                    "title": fm.get("title", path.stem),
                    "layer": fm.get("layer", 0),
                    "content": body,
                    "tags": fm.get("tags", []),
                    "frontmatter": fm
                })
        
        if len(source_notes) < self.config.min_sources:
            return ExpressResult(
                output_type=output_type,
                topic=topic,
                sources=[s["path"] for s in source_notes],
                success=False,
                error="Insufficient sources: {} < {}".format(len(source_notes), self.config.min_sources)
            )
        
        # Extract citations
        citations = self._extract_citations(source_notes)
        references = self._format_references(citations)
        
        # Get template
        template = self._load_template(output_type)
        output_config = self.config.output_types[output_type]
        
        # Synthesize each section
        sections_content = {}
        for section in output_config.sections:
            section_content = self._synthesize_section(
                section, topic, source_notes, context
            )
            sections_content[section] = section_content
        
        # Build content from template
        title = "{}: {}".format(output_config.name, topic)
        date = datetime.now().strftime("%Y-%m-%d")
        tags = ["#express", "#topic:{}".format(topic.lower().replace(" ", "-")), "#type:{}".format(output_type)]
        
        # Build replacements
        content = template.replace("{{title}}", title)\
                          .replace("{{topic}}", topic)\
                          .replace("{{sources}}", str([s["path"] for s in source_notes]))\
                          .replace("{{date}}", date)\
                          .replace("{{tags}}", str(tags))\
                          .replace("{{references}}", references)\
                          .replace("{{headline}}", title)\
                          .replace("{{intro}}", sections_content.get("intro", sections_content.get("overview", "")))\
                          .replace("{{body}}", sections_content.get("body", sections_content.get("details", "")))\
                          .replace("{{conclusion}}", sections_content.get("conclusion", sections_content.get("see_also", "")))\
                          .replace("{{executive_summary}}", sections_content.get("executive_summary", ""))\
                          .replace("{{findings}}", sections_content.get("findings", ""))\
                          .replace("{{recommendations}}", sections_content.get("recommendations", ""))\
                          .replace("{{appendix}}", sections_content.get("appendix", ""))\
                          .replace("{{overview}}", sections_content.get("overview", ""))\
                          .replace("{{details}}", sections_content.get("details", ""))\
                          .replace("{{examples}}", sections_content.get("examples", ""))\
                          .replace("{{see_also}}", sections_content.get("see_also", ""))\
                          .replace("{{stories}}", sections_content.get("stories", ""))\
                          .replace("{{insights}}", sections_content.get("insights", ""))\
                          .replace("{{cta}}", sections_content.get("cta", ""))
        
        # Save output
        output_filename = "{}-{}-{}.md".format(
            datetime.now().strftime("%Y-%m-%d"),
            output_type,
            topic.lower().replace(" ", "-")[:40]
        )
        output_file = self._output_path / output_filename
        
        if self.config.auto_save:
            output_file.write_text(content, encoding="utf-8")
        
        return ExpressResult(
            output_type=output_type,
            topic=topic,
            sources=[s["path"] for s in source_notes],
            output_path=str(output_file.relative_to(self._vault_path)) if self.config.auto_save else None,
            content=content,
            citations=citations,
            success=True
        )
    
    def batch_generate(
        self,
        topics: List[str],
        output_type: str = "article",
        max_sources: int = None
    ) -> List[ExpressResult]:
        """Generate multiple outputs."""
        results = []
        for topic in topics:
            result = self.generate(topic, output_type, max_sources=max_sources)
            results.append(result)
        return results


def create_express_engine(config: Optional[ExpressConfig] = None) -> ExpressEngine:
    """Factory function to create express engine."""
    return ExpressEngine(config)


__all__ = [
    "ExpressEngine",
    "ExpressConfig",
    "ExpressResult",
    "OutputType",
    "OutputConfig",
    "create_express_engine"
]