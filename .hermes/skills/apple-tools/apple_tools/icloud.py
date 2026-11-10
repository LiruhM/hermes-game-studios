"""
iCloud Sync - Manage iCloud Drive and CloudKit
"""

import subprocess
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

@dataclass
class iCloudFile:
    path: str
    size: int
    modified: str
    is_downloaded: bool
    is_shared: bool

class iCloudSync:
    """Manage iCloud Drive synchronization."""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.icloud_dir = Path(self.config.get("icloud_dir", 
            "~/Library/Mobile Documents/com~apple~CloudDocs")).expanduser()
    
    def list_files(self, path: str = "") -> List[Dict]:
        """List files in iCloud Drive."""
        target = self.icloud_dir / path
        if not target.exists():
            return []
        
        files = []
        for f in target.iterdir():
            stat = f.stat()
            files.append({
                "name": f.name,
                "path": str(f.relative_to(self.icloud_dir)),
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "is_dir": f.is_dir(),
                "is_downloaded": not f.name.endswith(".icloud"),
            })
        return files
    
    def download_file(self, relative_path: str) -> bool:
        """Trigger download of a file from iCloud."""
        target = self.icloud_dir / relative_path
        if target.exists() and target.name.endswith(".icloud"):
            # Trigger download by reading
            try:
                target.read_bytes()
                return True
            except:
                pass
        return False
    
    def upload_file(self, local_path: Path, icloud_path: str) -> bool:
        """Upload a file to iCloud Drive."""
        target = self.icloud_dir / icloud_path
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            target.write_bytes(local_path.read_bytes())
            return True
        except:
            return False
    
    def get_storage_info(self) -> Dict:
        """Get iCloud storage usage."""
        # Use system_profiler on macOS
        import subprocess
        result = subprocess.run(
            ["system_profiler", "SPiCloudStorageDataType", "-json"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        return {}

def create_icloud_sync(config: Dict = None) -> iCloudSync:
    return iCloudSync(config)