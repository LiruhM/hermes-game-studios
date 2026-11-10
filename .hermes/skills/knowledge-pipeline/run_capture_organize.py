from knowledge_pipeline import PipelineOrchestrator
p = PipelineOrchestrator()

# Stage 1: Capture
print('=== CAPTURE ===')
captured = p.capture_engine.scan_external_sources(dry_run=False)
print(f'Captured: {len(captured)} items')

# Stage 2: Organize
print('=== ORGANIZE ===')
result = p.organize_engine.process_inbox(auto=True, dry_run=False, max_files=200)
print(f'Moved: {len(result.moved)}')
print(f'Errors: {len(result.errors)}')
if result.errors:
    for e in result.errors[:5]:
        print(f'  ERROR: {e}')