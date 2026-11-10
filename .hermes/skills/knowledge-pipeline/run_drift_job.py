from knowledge_pipeline import PipelineOrchestrator
p = PipelineOrchestrator()

# Detect and move drift files to inbox
result = p.organize_engine.detect_drift(dry_run=False)
print(f"Drift detected: {len(result.drifted)}")
print(f"Moved to inbox: {len(result.moved)}")
for d in result.drifted:
    print(f"  {d['file']}")

# Now organize the inbox again (includes drift files)
result2 = p.organize_engine.process_inbox(auto=True, dry_run=False, max_files=50)
print(f"\nMoved from inbox: {len(result2.moved)}")
print(f"Errors: {len(result2.errors)}")
for m in result2.moved[:10]:
    print(f"  {m['source']} -> {m['destination']} ({m['para_destination']})")

pending = p.get_pending_work()
print(f"\nPending work: {pending}")