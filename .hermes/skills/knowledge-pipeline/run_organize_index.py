import sys
sys.path.insert(0, r'C:/Users/mathe/AppData/Local/hermes/skills/knowledge-pipeline')

from knowledge_pipeline import PipelineOrchestrator

p = PipelineOrchestrator()

# Organize inbox
print("=== ORGANIZE INBOX ===")
result = p.organize_now(dry_run=False)
print(f"Processed: {result}")

# Index update
print("\n=== INDEX UPDATE ===")
# The index is handled by memory-substrate, but we can trigger it
try:
    import requests
    resp = requests.post("http://127.0.0.1:8766/index", json={"full": False}, timeout=30)
    print(f"Index response: {resp.status_code} - {resp.text}")
except Exception as e:
    print(f"Index API not available: {e}")