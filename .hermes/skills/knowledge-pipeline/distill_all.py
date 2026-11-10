from knowledge_pipeline import PipelineOrchestrator
p = PipelineOrchestrator()
pending = p.distill_engine.get_pending_distill(max_layer=3)
print(f'Pending distill: {len(pending)}')

# Distill all remaining notes to layer 4 (Atomic)
results = p.distill_engine.batch_distill(pending, target_layer=4, auto_link=True, auto_tag=True)
success = 0
for r in results:
    if r.success:
        print(f'✓ {r.source_path} -> L{r.layer}: {r.output_path}')
        success += 1
    else:
        print(f'✗ {r.source_path}: {r.error}')
print(f'Total success: {success}/{len(results)}')