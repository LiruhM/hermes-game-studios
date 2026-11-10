"""
Static Analysis Manager - Code quality metrics and analysis
"""

import subprocess
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class AnalysisResult:
    success: bool
    tool: str
    metrics: Dict[str, Any] = None
    issues: List[Dict] = None
    error: str = ""

class StaticAnalysisManager:
    """Static code analysis for quality metrics."""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.workspace = Path(self.config.get("workspace", "."))
    
    def analyze_python(self, paths: List[str] = None) -> AnalysisResult:
        """Analyze Python code with radon, vulture, bandit."""
        paths = paths or [str(self.workspace)]
        metrics = {}
        issues = []
        
        try:
            # Radon - complexity metrics
            result = subprocess.run(
                ["radon", "cc", "-j"] + paths,
                capture_output=True, text=True, timeout=60
            )
            if result.stdout:
                metrics["cyclomatic_complexity"] = json.loads(result.stdout)
            
            result = subprocess.run(
                ["radon", "mi", "-j"] + paths,
                capture_output=True, text=True, timeout=60
            )
            if result.stdout:
                metrics["maintainability_index"] = json.loads(result.stdout)
            
            result = subprocess.run(
                ["radon", "raw", "-j"] + paths,
                capture_output=True, text=True, timeout=60
            )
            if result.stdout:
                metrics["raw_metrics"] = json.loads(result.stdout)
            
            # Vulture - dead code
            result = subprocess.run(
                ["vulture", "--json"] + paths,
                capture_output=True, text=True, timeout=60
            )
            if result.stdout:
                issues.extend(json.loads(result.stdout))
            
            # Bandit - security
            result = subprocess.run(
                ["bandit", "-r", "-f", "json"] + paths,
                capture_output=True, text=True, timeout=60
            )
            if result.stdout:
                data = json.loads(result.stdout)
                issues.extend(data.get("results", []))
            
        except Exception as e:
            return AnalysisResult(success=False, tool="python", error=str(e))
        
        return AnalysisResult(success=True, tool="python", metrics=metrics, issues=issues)
    
    def analyze_javascript(self, paths: List[str] = None) -> AnalysisResult:
        """Analyze JavaScript with eslint, complexity-report."""
        paths = paths or [str(self.workspace)]
        metrics = {}
        issues = []
        
        try:
            result = subprocess.run(
                ["eslint", "--format=json"] + paths,
                capture_output=True, text=True, timeout=60
            )
            if result.stdout:
                data = json.loads(result.stdout)
                for file_result in data:
                    for issue in file_result.get("messages", []):
                        issues.append({
                            "file": file_result["filePath"],
                            "line": issue.get("line"),
                            "column": issue.get("column"),
                            "message": issue.get("message"),
                            "rule": issue.get("ruleId"),
                            "severity": issue.get("severity")
                        })
        except Exception as e:
            return AnalysisResult(success=False, tool="javascript", error=str(e))
        
        return AnalysisResult(success=True, tool="javascript", issues=issues)
    
    def get_quality_gate(self, results: Dict[str, AnalysisResult]) -> Dict[str, Any]:
        """Evaluate quality gates."""
        gate = {
            "passed": True,
            "violations": []
        }
        
        for tool, result in results.items():
            if not result.success:
                continue
            
            if result.issues:
                for issue in result.issues:
                    severity = issue.get("severity", "warning")
                    if severity in ["error", "critical"]:
                        gate["passed"] = False
                        gate["violations"].append({
                            "tool": tool,
                            "file": issue.get("file"),
                            "message": issue.get("message"),
                            "severity": severity
                        })
        
        return gate


def create_static_analysis_manager(config: dict = None) -> StaticAnalysisManager:
    return StaticAnalysisManager(config)