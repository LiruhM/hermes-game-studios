"""
Linting Manager - Code linting for multiple languages
"""

import subprocess
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class LintResult:
    success: bool
    tool: str
    files_checked: int = 0
    issues: List[Dict] = None
    error: str = ""

class LintingManager:
    """Manage code linting across multiple languages and tools."""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.workspace = Path(self.config.get("workspace", "."))
    
    def lint_python(self, paths: List[str] = None, tools: List[str] = None) -> LintResult:
        """Lint Python code with ruff, flake8, pylint, mypy."""
        tools = tools or ["ruff", "flake8"]
        paths = paths or [str(self.workspace)]
        
        all_issues = []
        files_checked = 0
        
        for tool in tools:
            try:
                if tool == "ruff":
                    result = subprocess.run(
                        ["ruff", "check", "--output-format=json"] + paths,
                        capture_output=True, text=True, timeout=60
                    )
                    if result.stdout:
                        issues = json.loads(result.stdout)
                        for issue in issues:
                            issue["tool"] = "ruff"
                        all_issues.extend(issues)
                        files_checked += len(paths)
                
                elif tool == "flake8":
                    result = subprocess.run(
                        ["flake8", "--format=json"] + paths,
                        capture_output=True, text=True, timeout=60
                    )
                    # flake8 doesn't have native JSON, parse manually
                
                elif tool == "mypy":
                    result = subprocess.run(
                        ["mypy", "--json"] + paths,
                        capture_output=True, text=True, timeout=60
                    )
                    if result.stdout:
                        issues = json.loads(result.stdout)
                        for issue in issues:
                            issue["tool"] = "mypy"
                        all_issues.extend(issues)
                
            except Exception as e:
                return LintResult(success=False, tool=tool, error=str(e))
        
        return LintResult(
            success=True,
            tool=", ".join(tools),
            files_checked=files_checked,
            issues=all_issues
        )
    
    def lint_javascript(self, paths: List[str] = None, tools: List[str] = None) -> LintResult:
        """Lint JavaScript/TypeScript with eslint."""
        tools = tools or ["eslint"]
        paths = paths or [str(self.workspace)]
        
        all_issues = []
        
        try:
            result = subprocess.run(
                ["eslint", "--format=json"] + paths,
                capture_output=True, text=True, timeout=60
            )
            if result.stdout:
                results = json.loads(result.stdout)
                for file_result in results:
                    for issue in file_result.get("messages", []):
                        issue["file"] = file_result["filePath"]
                        issue["tool"] = "eslint"
                    all_issues.extend(file_result.get("messages", []))
        except Exception as e:
            return LintResult(success=False, tool="eslint", error=str(e))
        
        return LintResult(success=True, tool="eslint", issues=all_issues)
    
    def lint_all(self, paths: List[str] = None) -> Dict[str, LintResult]:
        """Run all available linters."""
        results = {}
        
        # Detect languages
        paths = paths or [str(self.workspace)]
        has_python = any(Path(p).rglob("*.py") for p in paths)
        has_js = any(Path(p).rglob("*.js") or Path(p).rglob("*.ts") for p in paths)
        
        if has_python:
            results["python"] = self.lint_python(paths)
        if has_js:
            results["javascript"] = self.lint_javascript(paths)
        
        return results
    
    def fix_python(self, paths: List[str] = None) -> LintResult:
        """Auto-fix Python issues with ruff."""
        paths = paths or [str(self.workspace)]
        
        try:
            result = subprocess.run(
                ["ruff", "check", "--fix"] + paths,
                capture_output=True, text=True, timeout=60
            )
            return LintResult(success=True, tool="ruff", error=result.stderr if result.returncode != 0 else "")
        except Exception as e:
            return LintResult(success=False, tool="ruff", error=str(e))


def create_linting_manager(config: dict = None) -> LintingManager:
    return LintingManager(config)