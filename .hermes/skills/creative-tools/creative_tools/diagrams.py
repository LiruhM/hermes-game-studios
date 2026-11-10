"""
Diagram Generator - Mermaid, PlantUML, Graphviz
"""

import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass

@dataclass
class Diagram:
    source: str
    format: str  # mermaid, plantuml, graphviz
    output: Optional[str] = None

class DiagramGenerator:
    """Generate diagrams from text definitions."""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.mermaid_enabled = self.config.get("mermaid", True)
        self.plantuml_enabled = self.config.get("plantuml", True)
        self.graphviz_enabled = self.config.get("graphviz", True)
    
    def mermaid(self, diagram: str, output: str = None) -> str:
        """Generate Mermaid diagram."""
        if not self.mermaid_enabled:
            return "[Mermaid disabled]"
        
        # Try mermaid-cli (mmdc)
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False) as f:
                f.write(diagram)
                mmd_file = f.name
            
            out_file = output or tempfile.mktemp(suffix='.svg')
            result = subprocess.run(
                ["mmdc", "-i", mmd_file, "-o", out_file],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode == 0:
                return Path(out_file).read_text()
        except FileNotFoundError:
            pass
        
        return f"```mermaid\n{diagram}\n```"
    
    def plantuml(self, diagram: str, output: str = None) -> str:
        """Generate PlantUML diagram."""
        if not self.plantuml_enabled:
            return "[PlantUML disabled]"
        
        # Try plantuml jar
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.puml', delete=False) as f:
                f.write(diagram)
                puml_file = f.name
            
            out_file = output or tempfile.mktemp(suffix='.png')
            result = subprocess.run(
                ["java", "-jar", "plantuml.jar", "-tsvg", puml_file],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode == 0:
                svg_file = puml_file.replace('.puml', '.svg')
                if Path(svg_file).exists():
                    return Path(svg_file).read_text()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        return f"```plantuml\n{diagram}\n```"
    
    def graphviz(self, diagram: str, output: str = None) -> str:
        """Generate Graphviz (DOT) diagram."""
        if not self.graphviz_enabled:
            return "[Graphviz disabled]"
        
        try:
            out_file = output or tempfile.mktemp(suffix='.svg')
            result = subprocess.run(
                ["dot", "-Tsvg", "-o", out_file],
                input=diagram, text=True, capture_output=True, timeout=10
            )
            
            if result.returncode == 0:
                return Path(out_file).read_text()
        except FileNotFoundError:
            pass
        
        return f"```dot\n{diagram}\n```"

def create_diagram_generator(config: dict = None) -> DiagramGenerator:
    return DiagramGenerator(config)