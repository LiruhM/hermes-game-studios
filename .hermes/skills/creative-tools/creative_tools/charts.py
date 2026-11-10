"""
Chart Generator - Terminal charts: sparkline, bar, pie
"""

from typing import Dict, List, Any
from dataclasses import dataclass

@dataclass
class Chart:
    data: Dict[str, float]
    chart_type: str
    width: int = 80

class ChartGenerator:
    """Generate terminal-based charts."""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.sparkline_chars = " ▁▂▃▄▅▆▇█"
        self.bar_chars = " ▏▎▍▌▋▊▉█"
    
    def sparkline(self, data: List[float], width: int = 40) -> str:
        """Generate sparkline chart."""
        if not data:
            return ""
        
        min_val = min(data)
        max_val = max(data)
        range_val = max_val - min_val if max_val != min_val else 1
        
        result = ""
        for val in data[-width:]:
            normalized = (val - min_val) / range_val
            idx = int(normalized * (len(self.sparkline_chars) - 1))
            result += self.sparkline_chars[idx]
        return result
    
    def bar_chart(self, data: Dict[str, float], width: int = 40) -> str:
        """Generate horizontal bar chart."""
        if not data:
            return ""
        
        max_val = max(data.values()) if data else 1
        max_label_len = max(len(k) for k in data.keys())
        
        lines = []
        for label, value in data.items():
            bar_width = int((value / max_val) * (width - max_label_len - 5))
            bar = "█" * bar_width
            lines.append(f"{label:>{max_label_len}} │{bar} {value}")
        
        return "\n".join(lines)
    
    def pie_chart(self, data: Dict[str, float], width: int = 20) -> str:
        """Generate ASCII pie chart."""
        if not data:
            return ""
        
        total = sum(data.values())
        if total == 0:
            return ""
        
        # Simple text-based pie
        lines = []
        for label, value in data.items():
            pct = (value / total) * 100
            bar_len = int(pct / 5)
            bar = "█" * bar_len
            lines.append(f"{label}: {bar} {pct:.1f}%")
        
        return "\n".join(lines)

def create_chart_generator(config: dict = None) -> ChartGenerator:
    return ChartGenerator(config)