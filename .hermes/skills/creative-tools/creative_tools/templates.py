"""
Template Engine - Jinja2 templates for documents
"""

import jinja2
from pathlib import Path
from typing import Dict, Any, Optional

class TemplateEngine:
    """Render Jinja2 templates."""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        template_dir = self.config.get("template_dir", "30-Recursos/templates/creative")
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(template_dir),
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True
        )
        # Add custom filters
        self.env.filters['tojson'] = json.dumps
    
    def render(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render a template with context."""
        template = self.env.get_template(template_name)
        return template.render(**context)
    
    def render_string(self, template_str: str, context: Dict[str, Any]) -> str:
        """Render a template string with context."""
        template = self.env.from_string(template_str)
        return template.render(**context)
    
    def list_templates(self) -> list:
        """List available templates."""
        return self.env.list_templates()

import json

def create_template_engine(config: dict = None) -> TemplateEngine:
    return TemplateEngine(config)