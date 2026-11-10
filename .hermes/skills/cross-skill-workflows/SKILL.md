---
name: cross-skill-workflows
version: "1.0.0"
description: "Cross-Skill Workflow Orchestration Engine — Define, execute, and monitor multi-skill workflows with dependency resolution, parallel execution, and state persistence."
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [workflow, orchestration, cross-skill, automation, pipeline, dags]
    related_skills: [skill-composability, skill-marketplace, token-optimization, second-brain-pipeline, hermes-squad-core]
    replaces: []

---

# Cross-Skill Workflows v1.0.0 — Orquestração Multi-Skill

**Objetivo:** Engine para definir e executar workflows que combinam múltiplas skills (ex: pesquisar → organizar → destilar → notificar), com resolução de dependências, execução paralela, persistência de estado e observabilidade.

---

## 🎯 CAPABILITIES

| Capability | Description |
|------------|-------------|
| **Workflow Definition** | YAML-based workflow specs with steps, dependencies, parallelism |
| **DAG Execution** | Topological sort + parallel execution of independent steps |
| **State Persistence** | SQLite + Vault sync for resume/retry |
| **Skill Integration** | Native integration with skill-composability loader |
| **Observability Hooks** | Events for dashboard integration |
| **Error Handling** | Retry policies, compensation, dead letter queue |
| **Human-in-the-loop** | Approval gates, pause/resume |

---

## ⚙️ CONFIGURAÇÃO (config.yaml)

```yaml
cross_skill_workflows:
  # Storage
  state_db: "90-Sistema/_data/workflow-state.db"
  vault_sync: true
  vault_path: "C:/Users/mathe/Hermes_Brain/50-Meta/workflows"
  
  # Execution
  max_parallel_steps: 4
  default_timeout_seconds: 300
  retry_policy:
    max_attempts: 3
    backoff_seconds: [5, 30, 120]
    exponential: true
  
  # Skills available for workflows
  skill_registry:
    - skill-composability
    - skill-marketplace
    - token-optimization
    - second-brain-pipeline
    - hermes-squad-core
    - productivity-tools
    - research-tools
    - creative-tools
    - devops-tools
    - mlops-tools
    - media-tools
    - note-taking-tools
    - software-dev-tools
  
  # Observability
  events:
    enabled: true
    sink: "sqlite"  # or "mempalace", "ntfy"
    include_step_outputs: true
  
  # Human-in-the-loop
  approval_gates:
    enabled: true
    default_timeout_minutes: 60
```

---

## 🔧 API UNIFICADA

```python
from cross_skill_workflows import WorkflowEngine, Workflow, WorkflowStep

engine = WorkflowEngine(config)

# Define workflow
workflow = Workflow(
    name="research-to-report",
    version="1.0",
    description="Research topic → organize notes → distill → create report → notify",
    steps=[
        WorkflowStep(
            id="research",
            skill="research-tools",
            action="search",
            params={"query": "{{topic}}", "limit": 10},
            outputs=["papers", "sources"]
        ),
        WorkflowStep(
            id="organize",
            skill="second-brain-pipeline",
            action="capture",
            params={"content": "{{research.papers}}", "topic": "{{topic}}"},
            depends_on=["research"],
            outputs=["note_ids"]
        ),
        WorkflowStep(
            id="distill",
            skill="second-brain-pipeline",
            action="distill",
            params={"note_ids": "{{organize.note_ids}}"},
            depends_on=["organize"],
            outputs=["summary"]
        ),
        WorkflowStep(
            id="report",
            skill="productivity-tools",
            action="create_document",
            params={"template": "research-report", "data": {"summary": "{{distill.summary}}"}},
            depends_on=["distill"],
            outputs=["doc_path"]
        ),
        WorkflowStep(
            id="notify",
            skill="productivity-tools",
            action="ntfy_notify",
            params={"message": "Report ready: {{report.doc_path}}"},
            depends_on=["report"]
        )
    ]
)

# Execute
result = engine.execute(workflow, inputs={"topic": "token optimization"})

# Or load from YAML file
workflow = engine.load_workflow("workflows/research-to-report.yaml")
result = engine.execute(workflow, inputs={"topic": "AI agents"})
```

---

## 📁 WORKFLOW YAML FORMAT

```yaml
# workflows/research-to-report.yaml
name: research-to-report
version: "1.0"
description: "Full research pipeline"
inputs:
  topic:
    type: string
    required: true
  depth:
    type: string
    enum: [quick, deep]
    default: deep

steps:
  - id: research
    skill: research-tools
    action: search
    params:
      query: "{{inputs.topic}}"
      limit: 10
      depth: "{{inputs.depth}}"
    outputs: [papers, sources]
    timeout: 120

  - id: organize
    skill: second-brain-pipeline
    action: capture
    params:
      content: "{{steps.research.outputs.papers}}"
      topic: "{{inputs.topic}}"
    depends_on: [research]
    outputs: [note_ids]

  - id: distill
    skill: second-brain-pipeline
    action: distill
    params:
      note_ids: "{{steps.organize.outputs.note_ids}}"
    depends_on: [organize]
    outputs: [summary]

  - id: report
    skill: productivity-tools
    action: create_document
    params:
      template: research-report
      data:
        topic: "{{inputs.topic}}"
        summary: "{{steps.distill.outputs.summary}}"
        sources: "{{steps.research.outputs.sources}}"
    depends_on: [distill]
    outputs: [doc_path]

  - id: notify
    skill: productivity-tools
    action: ntfy_notify
    params:
      message: "✅ Research complete: {{inputs.topic}} — {{steps.report.outputs.doc_path}}"
    depends_on: [report]

# Parallel execution hint
execution:
  parallel_groups:
    - [research]
    - [organize]
    - [distill]
    - [report, notify]  # notify can run after report starts
```

---

## 🧪 TESTE DE VALIDAÇÃO

```bash
# No Hermes:
/skill cross-skill-workflows

# Teste rápido:
from cross_skill_workflows import WorkflowEngine
engine = WorkflowEngine()

# Workflow simples
result = engine.execute_quick(
    name="test-workflow",
    steps=[
        {"id": "a", "skill": "research-tools", "action": "search", "params": {"q": "test"}},
        {"id": "b", "skill": "productivity-tools", "action": "create_note", "params": {"content": "{{a.results}}"}, "depends_on": ["a"]}
    ],
    inputs={}
)
print(f"Status: {result.status}, Outputs: {result.outputs}")
```

---

## 📋 ARQUITETURA

```
cross-skill-workflows/
├── SKILL.md
├── __init__.py              # Entry point
├── config.yaml
├── cross_skill_workflows/   # Core engine
│   ├── __init__.py
│   ├── engine.py            # WorkflowEngine
│   ├── models.py            # Workflow, Step, ExecutionContext
│   ├── executor.py          # DAG executor with parallelism
│   ├── state.py             # SQLite state persistence
│   ├── loader.py            # YAML workflow loader
│   ├── registry.py          # Skill capability registry
│   └── events.py            # Event emission for observability
├── templates/
│   └── workflows/           # Example workflow YAMLs
└── test_workflows.py        # Integration tests
```

---

*cross-skill-workflows v1.0.0 — Orchestrating the Hermes Skill Ecosystem*