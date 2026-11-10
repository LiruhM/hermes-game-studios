"""
apple-tools v1.0 - Apple Ecosystem Automation
Automation for macOS/iOS: Shortcuts, AppleScript, iCloud, Continuity, AirDrop
"""

from .shortcuts import ShortcutsManager, create_shortcuts_manager
from .applescript import AppleScriptRunner, create_applescript_runner
from .icloud import iCloudSync, create_icloud_sync
from .continuity import ContinuityManager, create_continuity_manager

__version__ = "1.0.0"
__all__ = [
    "ShortcutsManager", "create_shortcuts_manager",
    "AppleScriptRunner", "create_applescript_runner", 
    "iCloudSync", "create_icloud_sync",
    "ContinuityManager", "create_continuity_manager",
]

def create_apple_tools(config: dict = None) -> dict:
    """Factory to create all apple tools."""
    return {
        "shortcuts": create_shortcuts_manager(config),
        "applescript": create_applescript_runner(config),
        "icloud": create_icloud_sync(config),
        "continuity": create_continuity_manager(config),
    }