"""
Dependency Manager - Dependency analysis and management
"""

import subprocess
import json
import toml
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class DependencyResult:
    success: bool
    operation: str
    dependencies: List[Dict] = None
    outdated: List[Dict] = None
    vulnerabilities: List[Dict] = None
    error: str = ""

class DependencyManager:
    """Manage project dependencies."""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.workspace = Path(self.config.get("workspace", "."))
    
    def list_dependencies(self, paths: List[str] = None) -> DependencyResult:
        """List all dependencies for Python and JavaScript projects."""
        paths = paths or [str(self.workspace)]
        dependencies = []
        
        try:
            # Python - pip list
            result = subprocess.run(
                ["pip", "list", "--format=json"],
                capture_output=True, text=True, timeout=30
            )
            if result.stdout:
                for dep in json.loads(result.stdout):
                    dependencies.append({
                        "name": dep["name"],
                        "version": dep["version"],
                        "language": "python",
                        "source": "pip"
                    })
            
            # Python - poetry
            poetry_lock = self.workspace / "poetry.lock"
            if poetry_lock.exists():
                import toml
                with open(poetry_lock) as f:
                    lock_data = toml.load(f)
                for pkg in lock_data.get("package", []):
                    dependencies.append({
                        "name": pkg["name"],
                        "version": pkg["version"],
                        "language": "python",
                        "source": "poetry"
                    })
            
            # JavaScript - package.json
            package_json = self.workspace / "package.json"
            if package_json.exists():
                with open(package_json) as f:
                    pkg_data = json.load(f)
                for dep_type in ["dependencies", "devDependencies", "peerDependencies"]:
                    for name, version in pkg_data.get(dep_type, {}).items():
                        dependencies.append({
                            "name": name,
                            "version": version,
                            "language": "javascript",
                            "type": dep_type
                        })
            
        except Exception as e:
            return DependencyResult(success=False, operation="list", error=str(e))
        
        return DependencyResult(success=True, operation="list", dependencies=dependencies)
    
    def check_outdated(self, paths: List[str] = None) -> DependencyResult:
        """Check for outdated dependencies."""
        paths = paths or [str(self.workspace)]
        outdated = []
        
        try:
            # Python - pip list --outdated
            result = subprocess.run(
                ["pip", "list", "--outdated", "--format=json"],
                capture_output=True, text=True, timeout=30
            )
            if result.stdout:
                for dep in json.loads(result.stdout):
                    outdated.append({
                        "name": dep["name"],
                        "current": dep["version"],
                        "latest": dep["latest_version"],
                        "language": "python"
                    })
            
            # JavaScript - npm outdated
            result = subprocess.run(
                ["npm", "outdated", "--json"],
                capture_output=True, text=True, timeout=30
            )
            if result.stdout:
                data = json.loads(result.stdout)
                for name, info in data.items():
                    outdated.append({
                        "name": name,
                        "current": info.get("current"),
                        "latest": info.get("latest"),
                        "language": "javascript"
                    })
                    
        except Exception as e:
            return DependencyResult(success=False, operation="outdated", error=str(e))
        
        return DependencyResult(success=True, operation="outdated", outdated=outdated)
    
    def check_vulnerabilities(self, paths: List[str] = None) -> DependencyResult:
        """Check for security vulnerabilities in dependencies."""
        paths = paths or [str(self.workspace)]
        vulnerabilities = []
        
        try:
            # Python - pip-audit
            result = subprocess.run(
                ["pip-audit", "--format=json"],
                capture_output=True, text=True, timeout=60
            )
            if result.stdout:
                data = json.loads(result.stdout)
                for vuln in data.get("vulnerabilities", []):
                    vulnerabilities.append({
                        "package": vuln.get("package"),
                        "version": vuln.get("installed_version"),
                        "id": vuln.get("id"),
                        "description": vuln.get("description"),
                        "severity": vuln.get("severity"),
                        "language": "python"
                    })
            
            # JavaScript - npm audit
            result = subprocess.run(
                ["npm", "audit", "--json"],
                capture_output=True, text=True, timeout=60
            )
            if result.stdout:
                data = json.loads(result.stdout)
                for name, vuln in data.get("vulnerabilities", {}).items():
                    vulnerabilities.append({
                        "package": name,
                        "id": vuln.get("id"),
                        "description": vuln.get("title"),
                        "severity": vuln.get("severity"),
                        "language": "javascript"
                    })
                    
        except Exception as e:
            return DependencyResult(success=False, operation="vulnerabilities", error=str(e))
        
        return DependencyResult(success=True, operation="vulnerabilities", vulnerabilities=vulnerabilities)
    
    def update_dependencies(self, packages: List[str] = None, upgrade: bool = False) -> DependencyResult:
        """Update dependencies."""
        try:
            if upgrade:
                # Python - pip install --upgrade
                cmd = ["pip", "install", "--upgrade"] + (packages or [])
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                
                # JavaScript - npm update
                result = subprocess.run(["npm", "update"] + (packages or []), capture_output=True, text=True, timeout=120)
            
            return DependencyResult(success=True, operation="update")
        except Exception as e:
            return DependencyResult(success=False, operation="update", error=str(e))
    
    def generate_sbom(self, paths: List[str] = None) -> DependencyResult:
        """Generate Software Bill of Materials (SBOM)."""
        paths = paths or [str(self.workspace)]
        
        try:
            # Use cyclonedx for SBOM generation
            result = subprocess.run(
                ["cyclonedx-bom", "-o", "sbom.json"] + paths,
                capture_output=True, text=True, timeout=60
            )
            
            sbom_path = self.workspace / "sbom.json"
            if sbom_path.exists():
                with open(sbom_path) as f:
                    sbom = json.load(f)
                return DependencyResult(success=True, operation="sbom", dependencies=[sbom])
            
        except Exception as e:
            return DependencyResult(success=False, operation="sbom", error=str(e))
        
        return DependencyResult(success=False, operation="sbom", error="SBOM generation failed")


def create_dependency_manager(config: dict = None) -> DependencyManager:
    return DependencyManager(config)