from knowledge_pipeline import PipelineOrchestrator
p = PipelineOrchestrator()
result = p.organize_engine.detect_drift(dry_run=False)
print(f'Drifted: {len(result.drifted)}')
print(f'Moved to inbox: {len(result.moved)}')
print(f'Errors: {len(result.errors)}')
for d in result.drifted[:5]:
    print(f'  {d["file"]}')
if result.errors:
    for e in result.errors[:5]:
        print(f'  ERROR: {e}')