"""
Formatting Manager - Code formatting for multiple languages
"""

import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class FormatResult:
    success: bool
    tool: str
    files_formatted: int = 0
    error: str = ""

class FormattingManager:
    """Manage code formatting across multiple languages."""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.workspace = Path(self.config.get("workspace", "."))
    
    def format_python(self, paths: List[str] = None, tools: List[str] = None) -> FormatResult:
        """Format Python code with black, ruff, isort."""
        tools = tools or ["black", "ruff", "isort"]
        paths = paths or [str(self.workspace)]
        files_formatted = 0
        
        for tool in tools:
            try:
                if tool == "black":
                    result = subprocess.run(["black"] + paths, capture_output=True, text=True, timeout=60)
                    if "reformatted" in result.stdout:
                        files_formatted += result.stdout.count("reformatted")
                
                elif tool == "ruff":
                    result = subprocess.run(["ruff", "format"] + paths, capture_output=True, text=True, timeout=60)
                
                elif tool == "isort":
                    result = subprocess.run(["isort"] + paths, capture_output=True, text=True, timeout=60)
                    if "Fixing" in result.stdout:
                        files_formatted += result.stdout.count("Fixing")
                        
            except Exception as e:
                return FormatResult(success=False, tool=tool, error=str(e))
        
        return FormatResult(success=True, tool=", ".join(tools), files_formatted=files_formatted)
    
    def format_javascript(self, paths: List[str] = None) -> FormatResult:
        """Format JavaScript/TypeScript with prettier."""
        paths = paths or [str(self.workspace)]
        
        try:
            result = subprocess.run(["prettier", "--write"] + paths, capture_output=True, text=True, timeout=60)
            files_formatted = result.stdout.count("reformatted") if "reformatted" in result.stdout else 0
            return FormatResult(success=True, tool="prettier", files_formatted=files_formatted)
        except Exception as e:
            return FormatResult(success=False, tool="prettier", error=str(e))
    
    def format_all(self, paths: List[str] = None) -> Dict[str, FormatResult]:
        """Run all available formatters."""
        results = {}
        paths = paths or [str(self.workspace)]
        
        has_python = any(Path(p).rglob("*.py") for p in paths)
        has_js = any(Path(p).rglob("*.js") or Path(p).rglob("*.ts") for p in paths)
        
        if has_python:
            results["python"] = self.format_python(paths)
        if has_js:
            results["javascript"] = self.format_javascript(paths)
        
        return results


def create_formatting_manager(config: dict = None) -> FormattingManager:
    return FormattingManager(config)