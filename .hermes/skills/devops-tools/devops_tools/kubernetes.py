"""
Kubernetes Manager - kubectl wrapper, manifests, helm charts
"""

import subprocess
import json
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

@dataclass
class K8sResource:
    kind: str
    name: str
    namespace: str
    spec: Dict[str, Any]

class KubernetesManager:
    """Manage Kubernetes clusters via kubectl."""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.kubeconfig = self.config.get("kubeconfig", "~/.kube/config")
        self.namespace = self.config.get("namespace", "default")
        self.helm_repo = self.config.get("helm_repo", "https://charts.helm.sh/stable")
    
    def _kubectl(self, args: List[str], namespace: str = None) -> subprocess.CompletedProcess:
        """Run kubectl command."""
        cmd = ["kubectl"]
        if self.kubeconfig != "~/.kube/config":
            cmd.extend(["--kubeconfig", self.kubeconfig])
        ns = namespace or self.namespace
        cmd.extend(["-n", ns])
        cmd.extend(args)
        return subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    
    def apply(self, manifest: str, namespace: str = None) -> bool:
        """Apply a Kubernetes manifest."""
        result = self._kubectl(["apply", "-f", "-"], namespace)
        return result.returncode == 0
    
    def apply_file(self, file_path: str, namespace: str = None) -> bool:
        """Apply a Kubernetes manifest file."""
        result = self._kubectl(["apply", "-f", file_path], namespace)
        return result.returncode == 0
    
    def delete(self, resource: str, name: str, namespace: str = None) -> bool:
        """Delete a Kubernetes resource."""
        result = self._kubectl(["delete", resource, name], namespace)
        return result.returncode == 0
    
    def get(self, resource: str, name: str = None, namespace: str = None, 
            output: str = "json") -> Any:
        """Get Kubernetes resources."""
        args = ["get", resource]
        if name:
            args.append(name)
        args.extend(["-o", output])
        
        result = self._kubectl(args, namespace)
        if result.returncode != 0:
            return None
        
        if output == "json":
            return json.loads(result.stdout)
        return result.stdout
    
    def logs(self, pod: str, container: str = None, follow: bool = False, 
             namespace: str = None) -> str:
        """Get pod logs."""
        args = ["logs", pod]
        if container:
            args.extend(["-c", container])
        if follow:
            args.append("-f")
        
        result = self._kubectl(args, namespace)
        return result.stdout
    
    def exec(self, pod: str, command: List[str], container: str = None,
             namespace: str = None) -> str:
        """Execute command in pod."""
        args = ["exec", pod, "--"] + command
        if container:
            args.insert(1, "-c")
            args.insert(2, container)
        
        result = self._kubectl(args, namespace)
        return result.stdout
    
    def helm_install(self, release: str, chart: str, namespace: str = None,
                     values: Dict = None) -> bool:
        """Install Helm chart."""
        cmd = ["helm", "install", release, chart]
        if namespace:
            cmd.extend(["-n", namespace])
        if values:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(values, f)
                values_file = f.name
            cmd.extend(["-f", values_file])
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return result.returncode == 0
    
    def helm_upgrade(self, release: str, chart: str, namespace: str = None,
                     values: Dict = None) -> bool:
        """Upgrade Helm release."""
        cmd = ["helm", "upgrade", release, chart]
        if namespace:
            cmd.extend(["-n", namespace])
        if values:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(values, f)
                values_file = f.name
            cmd.extend(["-f", values_file])
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return result.returncode == 0
    
    def helm_list(self, namespace: str = None) -> List[Dict]:
        """List Helm releases."""
        cmd = ["helm", "list", "-o", "json"]
        if namespace:
            cmd.extend(["-n", namespace])
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return json.loads(result.stdout)
        return []

def create_kubernetes_manager(config: dict = None) -> KubernetesManager:
    return KubernetesManager(config)