from knowledge_pipeline import PipelineOrchestrator
p = PipelineOrchestrator()
pending = p.distill_engine.get_pending_distill(max_layer=3)
print(f'Pending distill: {len(pending)}')
for i, item in enumerate(pending[:10]):
    print(f'  {i+1}. {item}')