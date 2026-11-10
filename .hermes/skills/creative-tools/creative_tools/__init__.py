"""
Creative Tools - Main Package
"""

from .ascii import ASCIIGenerator, create_ascii_generator
from .diagrams import DiagramGenerator, create_diagram_generator
from .charts import ChartGenerator, create_chart_generator
from .templates import TemplateEngine, create_template_engine
from .prompts import PromptOptimizer, create_prompt_optimizer

__version__ = "1.0.0"
__all__ = [
    "ASCIIGenerator", "create_ascii_generator",
    "DiagramGenerator", "create_diagram_generator",
    "ChartGenerator", "create_chart_generator",
    "TemplateEngine", "create_template_engine",
    "PromptOptimizer", "create_prompt_optimizer",
]

def create_creative_tools(config: dict = None) -> dict:
    """Factory to create all creative tools."""
    return {
        "ascii": create_ascii_generator(config),
        "diagrams": create_diagram_generator(config),
        "charts": create_chart_generator(config),
        "templates": create_template_engine(config),
        "prompts": create_prompt_optimizer(config),
    }