import sys
sys.path.insert(0, r'C:/Users/mathe/AppData/Local/hermes/skills/knowledge-pipeline')

from knowledge_pipeline import PipelineOrchestrator

p = PipelineOrchestrator()

# Also check drift detection
print("=== DRIFT DETECTION (dry_run=True) ===")
drift = p.organize_engine.detect_drift(dry_run=True)
print(f"Drift result: {drift}")
if hasattr(drift, 'drifted') and drift.drifted:
    print(f"Drift items: {len(drift.drifted)}")
    for item in drift.drifted[:5]:
        print(f"  - {item}")
elif hasattr(drift, 'drifted_files'):
    print(f"Drift items: {len(drift.drifted_files)}")
    for item in drift.drifted_files[:5]:
        print(f"  - {item}")

# Check remaining inbox
from pathlib import Path
inbox = Path("C:/Users/mathe/Hermes_Brain/00-Inbox")
files = list(inbox.glob("*.md"))
print(f"\nTotal files in 00-Inbox: {len(files)}")