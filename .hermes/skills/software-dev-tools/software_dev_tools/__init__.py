"""
Software Dev Tools - Main Package
"""

from .linting import LintingManager, create_linting_manager
from .formatting import FormattingManager, create_formatting_manager
from .testing import TestingManager, create_testing_manager
from .static_analysis import StaticAnalysisManager, create_static_analysis_manager
from .refactoring import RefactoringManager, create_refactoring_manager
from .dependencies import DependencyManager, create_dependency_manager

__version__ = "1.0.0"
__all__ = [
    "LintingManager", "create_linting_manager",
    "FormattingManager", "create_formatting_manager",
    "TestingManager", "create_testing_manager",
    "StaticAnalysisManager", "create_static_analysis_manager",
    "RefactoringManager", "create_refactoring_manager",
    "DependencyManager", "create_dependency_manager",
]

def create_software_dev_tools(config: dict = None) -> dict:
    """Factory to create all software dev tools."""
    return {
        "linting": create_linting_manager(config),
        "formatting": create_formatting_manager(config),
        "testing": create_testing_manager(config),
        "static_analysis": create_static_analysis_manager(config),
        "refactoring": create_refactoring_manager(config),
        "dependencies": create_dependency_manager(config),
    }