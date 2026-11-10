"""
Testing Manager - Test execution and management
"""

import subprocess
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class TestResult:
    success: bool
    framework: str
    tests_run: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    coverage: float = 0.0
    duration: float = 0.0
    error: str = ""

class TestingManager:
    """Manage test execution across multiple frameworks."""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.workspace = Path(self.config.get("workspace", "."))
    
    def run_pytest(self, paths: List[str] = None, options: List[str] = None) -> TestResult:
        """Run pytest with coverage."""
        import time
        paths = paths or [str(self.workspace)]
        options = options or ["-v", "--tb=short", "--json-report"]
        
        start = time.time()
        try:
            result = subprocess.run(
                ["pytest"] + options + paths,
                capture_output=True, text=True, timeout=120
            )
            duration = time.time() - start
            
            tests_run = passed = failed = errors = 0
            
            # Parse JSON report if available
            for opt in options:
                if opt.startswith("--json-report"):
                    report_path = Path("pytest_report.json")
                    if report_path.exists():
                        with open(report_path) as f:
                            data = json.load(f)
                            tests_run = data.get("summary", {}).get("total", 0)
                            passed = data.get("summary", {}).get("passed", 0)
                            failed = data.get("summary", {}).get("failed", 0)
                            errors = data.get("summary", {}).get("error", 0)
            
            return TestResult(
                success=result.returncode == 0,
                framework="pytest",
                tests_run=tests_run,
                passed=passed,
                failed=failed,
                errors=errors,
                duration=duration
            )
        except Exception as e:
            return TestResult(success=False, framework="pytest", error=str(e))
    
    def run_unittest(self, paths: List[str] = None) -> TestResult:
        """Run Python unittest."""
        import time
        paths = paths or [str(self.workspace)]
        
        start = time.time()
        try:
            result = subprocess.run(
                ["python", "-m", "unittest", "discover", "-v"] + paths,
                capture_output=True, text=True, timeout=120
            )
            duration = time.time() - start
            
            # Parse output
            output = result.stdout + result.stderr
            tests_run = output.count("test_")
            failed = output.count("FAIL")
            errors = output.count("ERROR")
            passed = tests_run - failed - errors
            
            return TestResult(
                success=result.returncode == 0,
                framework="unittest",
                tests_run=tests_run,
                passed=passed,
                failed=failed,
                errors=errors,
                duration=duration
            )
        except Exception as e:
            return TestResult(success=False, framework="unittest", error=str(e))
    
    def run_jest(self, paths: List[str] = None) -> TestResult:
        """Run Jest for JavaScript/TypeScript."""
        import time
        paths = paths or [str(self.workspace)]
        
        start = time.time()
        try:
            result = subprocess.run(
                ["jest", "--json", "--outputFile=jest_report.json"] + paths,
                capture_output=True, text=True, timeout=120
            )
            duration = time.time() - start
            
            report_path = Path("jest_report.json")
            if report_path.exists():
                with open(report_path) as f:
                    data = json.load(f)
                return TestResult(
                    success=data.get("success", False),
                    framework="jest",
                    tests_run=data.get("numTotalTests", 0),
                    passed=data.get("numPassedTests", 0),
                    failed=data.get("numFailedTests", 0),
                    errors=0,
                    duration=duration
                )
            return TestResult(success=result.returncode == 0, framework="jest", duration=duration)
        except Exception as e:
            return TestResult(success=False, framework="jest", error=str(e))
    
    def run_all(self, paths: List[str] = None) -> Dict[str, TestResult]:
        """Run all available test frameworks."""
        results = {}
        paths = paths or [str(self.workspace)]
        
        has_python = any(Path(p).rglob("*.py") for p in paths)
        has_js = any(Path(p).rglob("*.js") or Path(p).rglob("*.ts") for p in paths)
        
        if has_python:
            results["pytest"] = self.run_pytest(paths)
            results["unittest"] = self.run_unittest(paths)
        if has_js:
            results["jest"] = self.run_jest(paths)
        
        return results


def create_testing_manager(config: dict = None) -> TestingManager:
    return TestingManager(config)