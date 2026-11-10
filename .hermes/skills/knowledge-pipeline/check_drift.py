from knowledge_pipeline import PipelineOrchestrator
p = PipelineOrchestrator()

# Check drift
drift_result = p.organize_engine.detect_drift(dry_run=True)
print(f"Drift detected: {len(drift_result.drifted)} files")
for d in drift_result.drifted[:5]:
    print(f"  {d['file']}")

# Check inbox again
pending = p.get_pending_work()
print(f"\nPending work: {pending}")