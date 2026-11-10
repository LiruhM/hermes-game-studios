"""
Docker Manager - Build, run, compose, registry management
"""

import subprocess
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

@dataclass
class DockerImage:
    name: str
    tag: str
    id: str
    size: int
    created: str

@dataclass
class Container:
    id: str
    name: str
    image: str
    status: str
    ports: Dict[str, str]

class DockerManager:
    """Manage Docker containers, images, and compose."""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.registry = self.config.get("registry", "docker.io")
        self.compose_file = self.config.get("compose_file", "docker-compose.yml")
    
    def build(self, path: str = ".", tag: str = None, dockerfile: str = "Dockerfile") -> DockerImage:
        """Build a Docker image."""
        cmd = ["docker", "build", "-f", dockerfile]
        if tag:
            cmd.extend(["-t", tag])
        cmd.append(path)
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"Docker build failed: {result.stderr}")
        
        # Extract image ID from output
        image_id = result.stdout.strip().split()[-1] if result.stdout else "unknown"
        return DockerImage(name=tag or "local", tag="latest", id=image_id, size=0, created="")
    
    def run(self, image: str, name: str = None, ports: Dict[str, int] = None, 
            env: Dict[str, str] = None, volumes: Dict[str, str] = None,
            detach: bool = True) -> Container:
        """Run a Docker container."""
        cmd = ["docker", "run"]
        if detach:
            cmd.append("-d")
        if name:
            cmd.extend(["--name", name])
        if ports:
            for host, container in ports.items():
                cmd.extend(["-p", f"{host}:{container}"])
        if env:
            for k, v in env.items():
                cmd.extend(["-e", f"{k}={v}"])
        if volumes:
            for host, container in volumes.items():
                cmd.extend(["-v", f"{host}:{container}"])
        cmd.append(image)
        
        result = subprocess.run(["docker", "run", "-d"] + cmd[2:], capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Docker run failed: {result.stderr}")
        
        container_id = result.stdout.strip()
        return Container(id=container_id, name=name or container_id[:12], 
                        image=image, status="running", ports={})
    
    def stop(self, container: str) -> bool:
        """Stop a container."""
        result = subprocess.run(["docker", "stop", container], capture_output=True)
        return result.returncode == 0
    
    def remove(self, container: str, force: bool = False) -> bool:
        """Remove a container."""
        cmd = ["docker", "rm"]
        if force:
            cmd.append("-f")
        cmd.append(container)
        result = subprocess.run(cmd, capture_output=True)
        return result.returncode == 0
    
    def list_containers(self, all: bool = False) -> List[Container]:
        """List containers."""
        cmd = ["docker", "ps", "--format", "json"]
        if all:
            cmd.insert(2, "-a")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return []
        
        containers = []
        for line in result.stdout.strip().split('\n'):
            if line:
                data = json.loads(line)
                containers.append(Container(
                    id=data.get("ID", ""),
                    name=data.get("Names", ""),
                    image=data.get("Image", ""),
                    status=data.get("Status", ""),
                    ports={}
                ))
        return containers
    
    def compose_up(self, detach: bool = True) -> bool:
        """Run docker-compose up."""
        cmd = ["docker-compose", "-f", self.compose_file, "up"]
        if detach:
            cmd.append("-d")
        result = subprocess.run(cmd, capture_output=True)
        return result.returncode == 0
    
    def compose_down(self) -> bool:
        """Run docker-compose down."""
        result = subprocess.run(["docker-compose", "-f", self.compose_file, "down"], capture_output=True)
        return result.returncode == 0
    
    def push(self, image: str, tag: str = "latest") -> bool:
        """Push image to registry."""
        full_tag = f"{self.registry}/{image}:{tag}" if "/" not in image else f"{image}:{tag}"
        result = subprocess.run(["docker", "push", full_tag], capture_output=True)
        return result.returncode == 0

def create_docker_manager(config: dict = None) -> DockerManager:
    return DockerManager(config)