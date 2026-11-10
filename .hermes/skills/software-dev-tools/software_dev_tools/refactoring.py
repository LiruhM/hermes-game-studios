"""
Refactoring Manager - Automated code refactoring
"""

import subprocess
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class RefactorResult:
    success: bool
    operation: str
    files_changed: int = 0
    changes: List[Dict] = None
    error: str = ""

class RefactoringManager:
    """Automated code refactoring operations."""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.workspace = Path(self.config.get("workspace", "."))
    
    def rename_symbol(self, old_name: str, new_name: str, paths: List[str] = None) -> RefactorResult:
        """Rename a symbol across the codebase using rope."""
        paths = paths or [str(self.workspace)]
        changes = []
        
        try:
            # Use rope for Python refactoring
            result = subprocess.run([
                "rope", "rename", old_name, new_name
            ] + paths, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                # Parse changes from output
                files_changed = result.stdout.count("Changed")
                return RefactorResult(
                    success=True,
                    operation=f"rename:{old_name}->{new_name}",
                    files_changed=files_changed,
                    changes=[{"old": old_name, "new": new_name}]
                )
            else:
                return RefactorResult(success=False, operation="rename", error=result.stderr)
        except Exception as e:
            return RefactorResult(success=False, operation="rename", error=str(e))
    
    def extract_method(self, file_path: str, start_line: int, end_line: int, method_name: str) -> RefactorResult:
        """Extract a code block into a new method."""
        try:
            # Use rope for method extraction
            result = subprocess.run([
                "rope", "extract", "method", file_path, str(start_line), str(end_line), method_name
            ], capture_output=True, text=True, timeout=60)
            
            return RefactorResult(
                success=result.returncode == 0,
                operation="extract_method",
                error=result.stderr if result.returncode != 0 else ""
            )
        except Exception as e:
            return RefactorResult(success=False, operation="extract_method", error=str(e))
    
    def extract_variable(self, file_path: str, start_line: int, end_line: int, var_name: str) -> RefactorResult:
        """Extract an expression into a variable."""
        try:
            result = subprocess.run([
                "rope", "extract", "variable", file_path, str(start_line), str(end_line), var_name
            ], capture_output=True, text=True, timeout=60)
            
            return RefactorResult(
                success=result.returncode == 0,
                operation="extract_variable",
                error=result.stderr if result.returncode != 0 else ""
            )
        except Exception as e:
            return RefactorResult(success=False, operation="extract_variable", error=str(e))
    
    def inline_variable(self, file_path: str, line: int, var_name: str) -> RefactorResult:
        """Inline a variable."""
        try:
            result = subprocess.run([
                "rope", "inline", file_path, str(line), var_name
            ], capture_output=True, text=True, timeout=60)
            
            return RefactorResult(
                success=result.returncode == 0,
                operation="inline_variable",
                error=result.stderr if result.returncode != 0 else ""
            )
        except Exception as e:
            return RefactorResult(success=False, operation="inline_variable", error=str(e))
    
    def move_module(self, module_path: str, destination: str) -> RefactorResult:
        """Move a module to a different location."""
        try:
            result = subprocess.run([
                "rope", "move", module_path, destination
            ], capture_output=True, text=True, timeout=60)
            
            return RefactorResult(
                success=result.returncode == 0,
                operation="move_module",
                error=result.stderr if result.returncode != 0 else ""
            )
        except Exception as e:
            return RefactorResult(success=False, operation="move_module", error=str(e))
    
    def organize_imports(self, paths: List[str] = None) -> RefactorResult:
        """Organize imports using isort."""
        paths = paths or [str(self.workspace)]
        
        try:
            result = subprocess.run(["isort"] + paths, capture_output=True, text=True, timeout=60)
            
            files_changed = 0
            if "Fixing" in result.stdout:
                files_changed = result.stdout.count("Fixing")
            
            return RefactorResult(
                success=result.returncode == 0,
                operation="organize_imports",
                files_changed=files_changed
            )
        except Exception as e:
            return RefactorResult(success=False, operation="organize_imports", error=str(e))


def create_refactoring_manager(config: dict = None) -> RefactoringManager:
    return RefactoringManager(config)