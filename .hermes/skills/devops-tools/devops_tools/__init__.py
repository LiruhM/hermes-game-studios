"""
DevOps Tools - Main Package
"""

from .docker import DockerManager, create_docker_manager
from .kubernetes import KubernetesManager, create_kubernetes_manager
from .terraform import TerraformManager, create_terraform_manager
from .ansible import AnsibleManager, create_ansible_manager
from .cicd import CICDGenerator, create_cicd_generator
from .monitoring import MonitoringManager, create_monitoring_manager

__version__ = "1.0.0"
__all__ = [
    "DockerManager", "create_docker_manager",
    "KubernetesManager", "create_kubernetes_manager",
    "TerraformManager", "create_terraform_manager",
    "AnsibleManager", "create_ansible_manager",
    "CICDGenerator", "create_cicd_generator",
    "MonitoringManager", "create_monitoring_manager",
]

def create_devops_tools(config: dict = None) -> dict:
    """Factory to create all devops tools."""
    return {
        "docker": create_docker_manager(config),
        "kubernetes": create_kubernetes_manager(config),
        "terraform": create_terraform_manager(config),
        "ansible": create_ansible_manager(config),
        "cicd": create_cicd_generator(config),
        "monitoring": create_monitoring_manager(config),
    }