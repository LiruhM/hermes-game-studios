from knowledge_pipeline import PipelineOrchestrator
p = PipelineOrchestrator()

# Run capture from external sources
captured = p.capture_engine.scan_external_sources(dry_run=False)
print(f"Captured: {len(captured)} new items")
for item in captured[:5]:
    print(f"  - {item.id}: {item.type.value} | {item.context} | {item.vault_path}")

# Check status again
pending = p.get_pending_work()
print(f"\nPending work after capture: {pending}")