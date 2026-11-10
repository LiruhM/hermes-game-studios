"""
Ansible Manager - Playbooks, inventory, roles
"""

import subprocess
import json
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

@dataclass
class AnsibleResult:
    success: bool
    stdout: str
    stderr: str
    stats: Dict[str, Any]

class AnsibleManager:
    """Manage Ansible automation."""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.inventory = self.config.get("inventory", "inventory.yml")
        self.playbook_dir = Path(self.config.get("playbook_dir", "playbooks"))
        self.private_key = self.config.get("private_key")
    
    def _ansible(self, args: List[str]) -> subprocess.CompletedProcess:
        """Run ansible command."""
        cmd = ["ansible"] + args
        if self.inventory:
            cmd.extend(["-i", self.inventory])
        if self.private_key:
            cmd.extend(["--private-key", self.private_key])
        return subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    
    def _ansible_playbook(self, args: List[str]) -> subprocess.CompletedProcess:
        """Run ansible-playbook command."""
        cmd = ["ansible-playbook"] + args
        if self.inventory:
            cmd.extend(["-i", self.inventory])
        if self.private_key:
            cmd.extend(["--private-key", self.private_key])
        return subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    
    def ping(self, pattern: str = "all") -> Dict[str, bool]:
        """Ping hosts."""
        result = self._ansible(["-m", "ping", pattern])
        hosts = {}
        for line in result.stdout.split('\n'):
            if "SUCCESS" in line or "UNREACHABLE" in line or "FAILED" in line:
                parts = line.split()
                if parts:
                    host = parts[0].replace("|", "")
                    hosts[host] = "SUCCESS" in line
        return hosts
    
    def run_module(self, pattern: str, module: str, args: str = "") -> Dict[str, Any]:
        """Run an Ansible module on hosts."""
        cmd_args = [pattern, "-m", module]
        if args:
            cmd_args.extend(["-a", args])
        result = self._ansible(cmd_args)
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    
    def run_playbook(self, playbook: str, extra_vars: Dict = None,
                     tags: List[str] = None, limit: str = None) -> AnsibleResult:
        """Run an Ansible playbook."""
        playbook_path = self.playbook_dir / playbook
        if not playbook_path.exists():
            playbook_path = Path(playbook)
        
        args = [str(playbook_path)]
        if extra_vars:
            for k, v in extra_vars.items():
                args.extend(["-e", f"{k}={v}"])
        if tags:
            args.extend(["-t", ",".join(tags)])
        if limit:
            args.extend(["-l", limit])
        
        result = self._ansible_playbook(args)
        return AnsibleResult(
            success=result.returncode == 0,
            stdout=result.stdout,
            stderr=result.stderr,
            stats={}
        )
    
    def list_tasks(self, playbook: str) -> List[str]:
        """List tasks in a playbook."""
        playbook_path = self.playbook_dir / playbook
        result = self._ansible_playbook(["--list-tasks", str(playbook_path)])
        tasks = []
        for line in result.stdout.split('\n'):
            if "task:" in line.lower():
                tasks.append(line.strip())
        return tasks
    
    def list_hosts(self, pattern: str = "all") -> List[str]:
        """List hosts matching pattern."""
        result = self._ansible(["--list-hosts", pattern])
        hosts = []
        for line in result.stdout.split('\n'):
            line = line.strip()
            if line and not line.startswith("hosts"):
                hosts.append(line.strip())
        return hosts
    
    def vault_encrypt(self, file_path: str) -> bool:
        """Encrypt a file with Ansible Vault."""
        result = subprocess.run(
            ["ansible-vault", "encrypt", file_path],
            capture_output=True, text=True
        )
        return result.returncode == 0
    
    def vault_decrypt(self, file_path: str) -> bool:
        """Decrypt a file with Ansible Vault."""
        result = subprocess.run(
            ["ansible-vault", "decrypt", file_path],
            capture_output=True, text=True
        )
        return result.returncode == 0

def create_ansible_manager(config: dict = None) -> AnsibleManager:
    return AnsibleManager(config)