"""
AppleScript Runner - Execute AppleScript from Python
"""

import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List

class AppleScriptRunner:
    """Execute AppleScript code from Python."""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.timeout = self.config.get("timeout", 30)
    
    def run_script(self, script: str, args: List[str] = None) -> str:
        """Run an AppleScript string."""
        cmd = ["osascript", "-e", script]
        if args:
            for arg in args:
                cmd.extend(["-e", f'on run argv\nreturn item 1 of argv\nend run', arg])
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout)
        if result.returncode == 0:
            return result.stdout.strip()
        raise RuntimeError(f"AppleScript failed: {result.stderr}")
    
    def run_file(self, script_path: Path, args: List[str] = None) -> str:
        """Run an AppleScript file."""
        cmd = ["osascript", str(script_path)]
        if args:
            cmd.extend(args)
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout)
        if result.returncode == 0:
            return result.stdout.strip()
        raise RuntimeError(f"AppleScript failed: {result.stderr}")
    
    def tell_app(self, app_name: str, command: str) -> str:
        """Send a command to an application."""
        script = f'tell application "{app_name}" to {command}'
        return self.run_script(script)
    
    def get_app_property(self, app_name: str, property_name: str) -> str:
        """Get a property from an application."""
        script = f'tell application "{app_name}" to get {property_name}'
        return self.run_script(script)
    
    def activate_app(self, app_name: str) -> str:
        """Activate (bring to front) an application."""
        return self.tell_app(app_name, "activate")
    
    def quit_app(self, app_name: str) -> str:
        """Quit an application."""
        return self.tell_app(app_name, "quit")

def create_applescript_runner(config: Dict = None) -> AppleScriptRunner:
    return AppleScriptRunner(config)