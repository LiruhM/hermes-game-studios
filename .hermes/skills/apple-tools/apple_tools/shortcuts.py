"""
Shortcuts Manager - Manage iOS/macOS Shortcuts
"""

import subprocess
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

@dataclass
class Shortcut:
    name: str
    identifier: str
    actions: List[Dict[str, Any]]
    icon: Optional[str] = None
    color: Optional[str] = None

class ShortcutsManager:
    """Manage Shortcuts on macOS/iOS."""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.shortcuts_dir = Path(self.config.get("shortcuts_dir", 
            "~/Library/Shortcuts")).expanduser()
    
    def list_shortcuts(self) -> List[Shortcut]:
        """List all available shortcuts."""
        # On macOS, shortcuts are in ~/Library/Shortcuts/
        # This is a simplified implementation
        shortcuts = []
        if self.shortcuts_dir.exists():
            for f in self.shortcuts_dir.glob("*.shortcut"):
                try:
                    data = json.loads(f.read_text())
                    shortcuts.append(Shortcut(
                        name=data.get("name", f.stem),
                        identifier=data.get("identifier", f.stem),
                        actions=data.get("actions", []),
                        icon=data.get("icon"),
                        color=data.get("color")
                    ))
                except:
                    pass
        return shortcuts
    
    def run_shortcut(self, name: str, input_data: Any = None) -> Any:
        """Run a shortcut by name."""
        # Use shortcuts command line tool on macOS
        cmd = ["shortcuts", "run", name]
        if input_data is not None:
            cmd.extend(["-i", json.dumps(input_data)])
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout
        raise RuntimeError(f"Shortcut failed: {result.stderr}")
    
    def create_shortcut(self, name: str, actions: List[Dict]) -> Shortcut:
        """Create a new shortcut."""
        shortcut = Shortcut(name=name, identifier=name.lower().replace(" ", "-"), actions=actions)
        # Save to file
        self.shortcuts_dir.mkdir(parents=True, exist_ok=True)
        shortcut_file = self.shortcuts_dir / f"{shortcut.identifier}.shortcut"
        shortcut_file.write_text(json.dumps({
            "name": shortcut.name,
            "identifier": shortcut.identifier,
            "actions": shortcut.actions,
            "icon": shortcut.icon,
            "color": shortcut.color
        }, indent=2))
        return shortcut

def create_shortcuts_manager(config: Dict = None) -> ShortcutsManager:
    return ShortcutsManager(config)