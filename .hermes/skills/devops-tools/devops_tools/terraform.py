"""
Terraform Manager - Plan, apply, state management
"""

import subprocess
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

@dataclass
class TerraformPlan:
    additions: int
    changes: int
    destructions: int
    output: str

class TerraformManager:
    """Manage Terraform infrastructure."""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.backend = self.config.get("backend", "local")
        self.state_path = self.config.get("state_path", "terraform.tfstate")
        self.working_dir = Path(self.config.get("working_dir", "."))
    
    def _tf(self, args: List[str]) -> subprocess.CompletedProcess:
        """Run terraform command."""
        cmd = ["terraform"] + args
        return subprocess.run(cmd, cwd=self.working_dir, capture_output=True, text=True, timeout=120)
    
    def init(self, upgrade: bool = False) -> bool:
        """Initialize Terraform."""
        args = ["init"]
        if upgrade:
            args.append("-upgrade")
        result = self._tf(args)
        return result.returncode == 0
    
    def fmt(self) -> bool:
        """Format Terraform files."""
        result = self._tf(["fmt", "-recursive"])
        return result.returncode == 0
    
    def validate(self) -> bool:
        """Validate Terraform configuration."""
        result = self._tf(["validate"])
        return result.returncode == 0
    
    def plan(self, out: str = None) -> TerraformPlan:
        """Create execution plan."""
        args = ["plan"]
        if out:
            args.extend(["-out", out])
        args.append("-input=false")
        
        result = self._tf(args)
        if result.returncode != 0 and result.returncode != 2:  # 2 = plan has changes
            raise RuntimeError(f"Terraform plan failed: {result.stderr}")
        
        # Parse plan output for summary
        additions = changes = destructions = 0
        for line in result.stdout.split('\n'):
            if "Plan:" in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part.isdigit():
                        if i+1 < len(parts):
                            if "add" in parts[i+1]:
                                additions = int(part)
                            elif "change" in parts[i+1]:
                                changes = int(part)
                            elif "destroy" in parts[i+1]:
                                destructions = int(part)
        
        return TerraformPlan(
            additions=additions,
            changes=changes,
            destructions=destructions,
            output=result.stdout
        )
    
    def apply(self, plan_file: str = None, auto_approve: bool = True) -> bool:
        """Apply Terraform plan."""
        args = ["apply"]
        if auto_approve:
            args.append("-auto-approve")
        if plan_file:
            args.append(plan_file)
        else:
            args.append("-input=false")
        
        result = self._tf(args)
        return result.returncode == 0
    
    def destroy(self, auto_approve: bool = True) -> bool:
        """Destroy Terraform resources."""
        args = ["destroy"]
        if auto_approve:
            args.append("-auto-approve")
        result = self._tf(args)
        return result.returncode == 0
    
    def output(self, name: str = None, json_output: bool = True) -> Any:
        """Get Terraform outputs."""
        args = ["output"]
        if json_output:
            args.append("-json")
        if name:
            args.append(name)
        
        result = self._tf(args)
        if result.returncode != 0:
            return None
        
        if json_output:
            return json.loads(result.stdout)
        return result.stdout
    
    def state_list(self) -> List[str]:
        """List resources in state."""
        result = self._tf(["state", "list"])
        if result.returncode != 0:
            return []
        return result.stdout.strip().split('\n')
    
    def state_show(self, resource: str) -> Any:
        """Show resource in state."""
        result = self._tf(["state", "show", resource])
        if result.returncode != 0:
            return None
        return result.stdout
    
    def import_resource(self, resource: str, id: str) -> bool:
        """Import existing resource into state."""
        result = self._tf(["import", resource, id])
        return result.returncode == 0

def create_terraform_manager(config: dict = None) -> TerraformManager:
    return TerraformManager(config)