"""
Memory Substrate v1.0 — Adapters Package
Unified interface for all storage adapters.
"""

from .vault_adapter import VaultAdapter, VaultAdapterConfig, create_vault_adapter
from .mempalace_adapter import MemPalaceAdapter, MemPalaceAdapterConfig, create_mempalace_adapter
from .skill_adapter import SkillAdapter, SkillAdapterConfig, create_skill_adapter

__all__ = [
    "VaultAdapter",
    "VaultAdapterConfig",
    "create_vault_adapter",
    "MemPalaceAdapter",
    "MemPalaceAdapterConfig",
    "create_mempalace_adapter",
    "SkillAdapter",
    "SkillAdapterConfig",
    "create_skill_adapter"
]