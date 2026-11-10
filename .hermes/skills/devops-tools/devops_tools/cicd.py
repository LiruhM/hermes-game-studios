"""
CICD Generator - Pipeline generation for GitHub Actions, GitLab CI, Jenkins
"""

from pathlib import Path
from typing import Dict, List, Any, Optional

class CICDGenerator:
    """Generate CI/CD pipeline configurations."""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.provider = self.config.get("provider", "github-actions")
    
    def github_actions(self, 
                       jobs: Dict[str, Dict],
                       on: Dict = None,
                       env: Dict = None) -> str:
        """Generate GitHub Actions workflow."""
        on = on or {"push": {"branches": ["main"]}, "pull_request": {}}
        env = env or {}
        
        yaml_lines = [
            "name: CI/CD Pipeline",
            "",
            "on:",
        ]
        
        for event, config in on.items():
            yaml_lines.append(f"  {event}:")
            if isinstance(config, dict):
                for k, v in config.items():
                    yaml_lines.append(f"    {k}: {v}")
            else:
                yaml_lines.append(f"    {config}")
        
        if env:
            yaml_lines.extend(["", "env:"])
            for k, v in env.items():
                yaml_lines.append(f"  {k}: {v}")
        
        yaml_lines.extend(["", "jobs:"])
        for job_name, job_config in jobs.items():
            yaml_lines.append(f"  {job_name}:")
            for k, v in job_config.items():
                if isinstance(v, dict):
                    yaml_lines.append(f"    {k}:")
                    for k2, v2 in v.items():
                        yaml_lines.append(f"      {k2}: {v2}")
                elif isinstance(v, list):
                    yaml_lines.append(f"    {k}:")
                    for item in v:
                        yaml_lines.append(f"      - {item}")
                else:
                    yaml_lines.append(f"    {k}: {v}")
        
        return "\n".join(yaml_lines)
    
    def gitlab_ci(self, 
                  stages: List[str],
                  jobs: Dict[str, Dict]) -> str:
        """Generate GitLab CI configuration."""
        yaml_lines = ["stages:"]
        for stage in stages:
            yaml_lines.append(f"  - {stage}")
        
        yaml_lines.append("")
        for job_name, job_config in jobs.items():
            yaml_lines.append(f"{job_name}:")
            for k, v in job_config.items():
                if isinstance(v, dict):
                    yaml_lines.append(f"  {k}:")
                    for k2, v2 in v.items():
                        yaml_lines.append(f"    {k2}: {v2}")
                elif isinstance(v, list):
                    yaml_lines.append(f"  {k}:")
                    for item in v:
                        yaml_lines.append(f"    - {item}")
                else:
                    yaml_lines.append(f"  {k}: {v}")
            yaml_lines.append("")
        
        return "\n".join(yaml_lines)
    
    def jenkinsfile(self, 
                    pipeline: Dict) -> str:
        """Generate Jenkinsfile (Declarative Pipeline)."""
        lines = ["pipeline {"]
        lines.append("  agent any")
        
        if "environment" in pipeline:
            lines.append("  environment {")
            for k, v in pipeline["environment"].items():
                lines.append(f'    {k} = "{v}"')
            lines.append("  }")
        
        if "stages" in pipeline:
            lines.append("  stages {")
            for stage_name, stage_config in pipeline["stages"].items():
                lines.append(f"    stage('{stage_name}') {{")
                if "steps" in stage_config:
                    lines.append("      steps {")
                    for step in stage_config["steps"]:
                        lines.append(f"        {step}")
                    lines.append("      }")
                lines.append("    }")
            lines.append("  }")
        
        if "post" in pipeline:
            lines.append("  post {")
            for condition, steps in pipeline["post"].items():
                lines.append(f"    {condition} {{")
                for step in steps:
                    lines.append(f"      {step}")
                lines.append("    }")
            lines.append("  }")
        
        lines.append("}")
        return "\n".join(lines)

def create_cicd_generator(config: dict = None) -> CICDGenerator:
    return CICDGenerator(config)