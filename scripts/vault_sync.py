#!/usr/bin/env python3
"""
Vault Sync Script
Syncs Obsidian vault (PARA structure) with Hermes memory substrate.
"""

import json
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional


def get_vault_path() -> Path:
    """Get the Obsidian vault path."""
    # Default to ~/Hermes_Brain as per project.yaml
    userprofile = os.environ.get("USERPROFILE", "")
    if userprofile:
        return Path(userprofile) / "Hermes_Brain"
    return Path.home() / "Hermes_Brain"


def get_memory_substrate_url() -> str:
    """Get the memory substrate API URL."""
    return "http://127.0.0.1:8766"


def scan_vault(vault_path: Path) -> Dict[str, Any]:
    """Scan the Obsidian vault for PARA structure."""
    if not vault_path.exists():
        return {"error": f"Vault not found at {vault_path}"}
    
    para_dirs = ["Projects", "Areas", "Resources", "Archives"]
    results = {
        "vault_path": str(vault_path),
        "timestamp": datetime.now().isoformat(),
        "para": {},
        "total_files": 0,
        "total_size": 0,
    }
    
    for para_dir in para_dirs:
        dir_path = vault_path / para_dir
        if dir_path.exists():
            files = list(dir_path.rglob("*.md"))
            results["para"][para_dir] = {
                "path": str(dir_path),
                "file_count": len(files),
                "files": [{"name": f.name, "path": str(f.relative_to(vault_path)), "size": f.stat().st_size, "mtime": f.stat().st_mtime} for f in files]
            }
            results["total_files"] += len(files)
            results["total_size"] += sum(f.stat().st_size for f in files)
        else:
            results["para"][para_dir] = {"path": str(dir_path), "file_count": 0, "files": [], "missing": True}
    
    return results


def sync_to_memory_substrate(vault_data: Dict[str, Any]) -> Dict[str, Any]:
    """Sync vault data to memory substrate API."""
    url = get_memory_substrate_url()
    results = {"synced": 0, "failed": 0, "errors": []}
    
    try:
        import requests
        
        # Health check first
        health_resp = requests.get(f"{url}/health", timeout=5)
        if health_resp.status_code != 200:
            results["errors"].append(f"Memory substrate unhealthy: {health_resp.status_code}")
            return results
        
        # Sync each PARA category
        for category, data in vault_data.get("para", {}).items():
            if "files" not in data:
                continue
            
            for file_info in data["files"]:
                try:
                    file_path = Path(vault_data["vault_path"]) / file_info["path"]
                    content = file_path.read_text(encoding="utf-8")
                    
                    payload = {
                        "content": content,
                        "metadata": {
                            "source": "obsidian_vault",
                            "para_category": category,
                            "file_name": file_info["name"],
                            "file_path": file_info["path"],
                            "vault_path": vault_data["vault_path"],
                            "synced_at": datetime.now().isoformat(),
                        }
                    }
                    
                    resp = requests.post(f"{url}/ingest", json=payload, timeout=10)
                    if resp.status_code in (200, 201):
                        results["synced"] += 1
                    else:
                        results["failed"] += 1
                        results["errors"].append(f"Failed to sync {file_info['path']}: {resp.status_code}")
                        
                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append(f"Error syncing {file_info['path']}: {e}")
    
    except Exception as e:
        results["errors"].append(f"Connection error: {e}")
    
    return results


def pull_from_memory_substrate(query: str = "", limit: int = 100) -> Dict[str, Any]:
    """Pull recent memories from memory substrate."""
    url = get_memory_substrate_url()
    results = {"memories": [], "error": None}
    
    try:
        import requests
        payload = {"query": query, "limit": limit} if query else {"limit": limit}
        resp = requests.post(f"{url}/search", json=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            results["memories"] = data.get("results", [])
        else:
            results["error"] = f"Search failed: {resp.status_code}"
    except Exception as e:
        results["error"] = str(e)
    
    return results


def create_vault_index(vault_data: Dict[str, Any]) -> Path:
    """Create a local index file for the vault."""
    localappdata = os.environ.get("LOCALAPPDATA", "")
    index_dir = Path(localappdata) / "hermes" / "memory" / "vault-index"
    index_dir.mkdir(parents=True, exist_ok=True)
    
    index_file = index_dir / f"vault-index-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    index_file.write_text(json.dumps(vault_data, indent=2, ensure_ascii=False), encoding="utf-8")
    
    # Latest symlink
    latest = index_dir / "latest.json"
    if latest.exists():
        latest.unlink()
    latest.symlink_to(index_file.name)
    
    return index_file


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Vault Sync Manager")
    parser.add_argument("--scan", action="store_true", help="Scan vault only")
    parser.add_argument("--push", action="store_true", help="Push vault to memory substrate")
    parser.add_argument("--pull", action="store_true", help="Pull from memory substrate")
    parser.add_argument("--query", type=str, default="", help="Query for pull")
    parser.add_argument("--full-sync", action="store_true", help="Full bidirectional sync")
    parser.add_argument("--index", action="store_true", help="Create local vault index")
    args = parser.parse_args()
    
    # Default action: scan (for cron compatibility)
    if not any([args.scan, args.push, args.pull, args.full_sync, args.index]):
        args.scan = True
    
    vault_path = get_vault_path()
    
    if args.scan or args.index or args.push or args.full_sync:
        print(f"Scanning vault at {vault_path}...")
        vault_data = scan_vault(vault_path)
        if "error" in vault_data:
            print(f"Error: {vault_data['error']}", file=sys.stderr)
            return 1
        
        print(f"Found {vault_data['total_files']} files ({vault_data['total_size']} bytes)")
        for cat, data in vault_data["para"].items():
            status = "MISSING" if data.get("missing") else f"{data['file_count']} files"
            print(f"  {cat}: {status}")
        
        if args.index:
            index_file = create_vault_index(vault_data)
            print(f"Index saved: {index_file}")
        
        if args.push or args.full_sync:
            print("Pushing to memory substrate...")
            sync_results = sync_to_memory_substrate(vault_data)
            print(f"Synced: {sync_results['synced']}, Failed: {sync_results['failed']}")
            if sync_results["errors"]:
                for err in sync_results["errors"][:5]:
                    print(f"  ERROR: {err}")
    
    if args.pull or args.full_sync:
        print("Pulling from memory substrate...")
        pull_results = pull_from_memory_substrate(args.query)
        if pull_results["error"]:
            print(f"Error: {pull_results['error']}", file=sys.stderr)
        else:
            print(f"Retrieved {len(pull_results['memories'])} memories")
            for mem in pull_results["memories"][:5]:
                print(f"  - {mem.get('content', '')[:80]}...")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())