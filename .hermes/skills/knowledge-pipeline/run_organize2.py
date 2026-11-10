from knowledge_pipeline import PipelineOrchestrator
p = PipelineOrchestrator()
result = p.organize_engine.process_inbox(auto=True, dry_run=False, max_files=200)
print(f'Moved: {len(result.moved)}')
print(f'Errors: {len(result.errors)}')
for m in result.moved[:10]:
    print(f'  {m["source"]} -> {m["destination"]} ({m["para_destination"]})')
if result.errors:
    for e in result.errors[:5]:
        print(f'  ERROR: {e}')