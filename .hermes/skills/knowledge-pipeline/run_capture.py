import sys
sys.path.insert(0, r'C:/Users/mathe/AppData/Local/hermes/skills/knowledge-pipeline')

from knowledge_pipeline import PipelineOrchestrator

p = PipelineOrchestrator()
captured = p.capture_engine.scan_external_sources(dry_run=False)
print(f'Captured: {len(captured)} items')
for item in captured[:10]:
    print(f'  - {item}')