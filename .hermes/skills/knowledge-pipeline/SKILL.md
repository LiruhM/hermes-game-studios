---
name: knowledge-pipeline
version: "1.0.0"
description: "Knowledge Compounding Pipeline v1.0 — Capture → Organize → Distill → Express → Review. Zero-config unified pipeline with cron scheduling, token optimization inheritance, and PARA-first organization."
category: infrastructure
author: "Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [knowledge, pipeline, capture, organize, distill, express, review, para, compounding, cron]
    related_skills: [second-brain-pipeline, token-optimization, memory-substrate, note-taking-tools, hermes-squad-core]
    inherits_token_optimization: true
    token_optimization_profile: "analysis"
    replaces: []
dependencies:
  required:
    - name: "second-brain-pipeline"
      version: ">=2.0.0"
      type: "required"
      reason: "Core PARA infrastructure and review capabilities"
    - name: "token-optimization"
      version: ">=3.0.0"
      type: "required"
      reason: "Token optimization runtime layer"
    - name: "memory-substrate"
      version: ">=1.0.0"
      type: "required"
      reason: "Unified memory layer for indexing and search"
    - name: "note-taking-tools"
      version: ">=2.0.0"
      type: "required"
      reason: "Vault operations and second brain automation"
  optional:
    - name: "hermes-squad-core"
      version: ">=2.0.0"
      type: "optional"
      reason: "Advisory board for pipeline decisions"
capabilities:
  provides:
    - name: "capture"
      description: "Unified capture from vault, external sources, user input, MemPalace"
      version: "1.0.0"
      tags: ["capture", "inbox", "external", "web", "api"]
    - name: "organize"
      description: "PARA routing, drift detection, auto-tagging, inbox processing"
      version: "1.0.0"
      tags: ["organize", "para", "routing", "drift", "tagging"]
    - name: "distill"
      description: "Progressive summarization L1→L2→L3→L4 (Atomic Notes)"
      version: "1.0.0"
      tags: ["distill", "summarization", "atomic-notes", "linking", "tagging"]
    - name: "express"
      description: "Generate outputs: article, report, doc, newsletter from atomic notes"
      version: "1.0.0"
      tags: ["express", "generation", "synthesis", "citation"]
    - name: "pipeline"
      description: "Full pipeline orchestration with scheduling"
      version: "1.0.0"
      tags: ["pipeline", "orchestration", "cron", "scheduling"]
    - name: "cron"
      description: "Unified cron scheduling for all stages"
      version: "1.0.0"
      tags: ["cron", "scheduler", "automation"]
  consumes:
    - name: "vault"
      description: "Vault read/write access"
      version: ">=1.0.0"
      tags: ["vault", "filesystem"]
    - name: "para"
      description: "PARA classification and routing"
      version: ">=1.0.0"
      tags: ["para", "classification"]
    - name: "token_optimization"
      description: "Token optimization pipeline"
      version: ">=3.0.0"
      tags: ["optimization", "tokens"]
config_schema:
  type: object
  properties:
    vault_path:
      type: string
      default: "C:/Users/mathe/Hermes_Brain"
      description: "Path to Obsidian vault"
    capture:
      type: object
      properties:
        inbox_paths:
          type: array
          items:
            type: string
          default: ["00-Inbox", "50-Meta/00-Inbox"]
        external_scan_paths:
          type: array
          items:
            type: string
          default:
            - "C:/Users/mathe/Downloads"
            - "C:/Users/mathe/Desktop"
            - "C:/Users/mathe/Documents"
        exclude_patterns:
          type: array
          items:
            type: string
          default: ["*.tmp", "*.log", ".git/", "node_modules/", "__pycache__/"]
        template:
          type: string
          default: "[[{{date}}]] | #{{type}} #{{context}}\n{{content}}\n#revisar"
        auto_tag_types:
          type: array
          items:
            type: string
          default: ["ideia", "tarefa", "referencia", "fleeting", "problema", "insight", "decisao"]
      default: {}
    organize:
      type: object
      properties:
        para_mapping:
          type: object
          properties:
            projeto:
              type: string
              default: "10-Projetos"
            area:
              type: string
              default: "20-Areas"
            recurso:
              type: string
              default: "30-Recursos"
            arquivo:
              type: string
              default: "40-Arquivo"
            meta:
              type: string
              default: "50-Meta"
            sistema:
              type: string
              default: "90-Sistema"
        routing_rules:
          type: object
          properties:
            ideia:
              type: string
              default: "projects"
            tarefa:
              type: string
              default: "projects"
            problema:
              type: string
              default: "projects"
            insight:
              type: string
              default: "resources"
            referencia:
              type: string
              default: "resources"
            decisao:
              type: string
              default: "meta"
            reuniao:
              type: string
              default: "meta"
            fleeting:
              type: string
              default: "inbox"
        drift_detection:
          type: object
          properties:
            enabled:
              type: boolean
              default: true
            scan_paths:
              type: array
              items:
                type: string
              default:
                - "C:/Users/mathe/Downloads"
                - "C:/Users/mathe/Desktop"
                - "C:/Users/mathe/Documents"
            exclude_patterns:
              type: array
              items:
                type: string
              default: ["*.tmp", "*.log", ".git/", "node_modules/", "__pycache__/"]
            dry_run_default:
              type: boolean
              default: true
            max_loose_files_alert:
              type: integer
              default: 10
      default: {}
    distill:
      type: object
      properties:
        layers:
          type: object
          properties:
            "1":
              type: object
              properties:
                name:
                  type: string
                  default: "Highlights"
                template:
                  type: string
                  default: "templates/layer1-highlight.md"
                min_length:
                  type: integer
                  default: 50
            "2":
              type: object
              properties:
                name:
                  type: string
                  default: "Literature Notes"
                template:
                  type: string
                  default: "templates/layer2-literature.md"
                min_length:
                  type: integer
                  default: 200
            "3":
              type: object
              properties:
                name:
                  type: string
                  default: "Resource Notes"
                template:
                  type: string
                  default: "templates/layer3-resource.md"
                min_length:
                  type: integer
                  default: 500
            "4":
              type: object
              properties:
                name:
                  type: string
                  default: "Atomic Notes"
                template:
                  type: string
                  default: "templates/layer4-atomic.md"
                min_length:
                  type: integer
                  default: 100
        auto_link:
          type: object
          properties:
            enabled:
              type: boolean
              default: true
            min_similarity:
              type: number
              default: 0.7
            max_links_per_note:
              type: integer
              default: 10
        tagging:
          type: object
          properties:
            enabled:
              type: boolean
              default: true
            tag_taxonomy_path:
              type: string
              default: "30-Recursos/_taxonomy/tags.md"
            max_tags_per_note:
              type: integer
              default: 8
      default: {}
    express:
      type: object
      properties:
        output_types:
          type: object
          properties:
            article:
              type: object
              properties:
                template:
                  type: string
                  default: "templates/express-article.md"
                sections:
                  type: array
                  items:
                    type: string
                  default: ["intro", "body", "conclusion", "references"]
            report:
              type: object
              properties:
                template:
                  type: string
                  default: "templates/express-report.md"
                sections:
                  type: array
                  items:
                    type: string
                  default: ["executive_summary", "findings", "recommendations", "appendix"]
            doc:
              type: object
              properties:
                template:
                  type: string
                  default: "templates/express-doc.md"
                sections:
                  type: array
                  items:
                    type: string
                  default: ["overview", "details", "examples", "see_also"]
            newsletter:
              type: object
              properties:
                template:
                  type: string
                  default: "templates/express-newsletter.md"
                sections:
                  type: array
                  items:
                    type: string
                  default: ["headline", "stories", "insights", "cta"]
        synthesis_model:
          type: string
          default: "nemotron-3-ultra"
        max_sources:
          type: integer
          default: 15
        citation_style:
          type: string
          enum: ["wiki", "markdown", "apa"]
          default: "wiki"
        output_dir:
          type: string
          default: "10-Projetos/_outputs/express/"
      default: {}
    schedule:
      type: object
      properties:
        capture_external:
          type: string
          default: "*/30 * * * *"
        organize_inbox:
          type: string
          default: "0 * * * *"
        detect_drift:
          type: string
          default: "0 9 * * *"
        distill_pending:
          type: string
          default: "0 2 * * *"
        express_scheduled:
          type: string
          default: "0 6 * * 1"
        review_weekly:
          type: string
          default: "0 8 * * 1"
        review_monthly:
          type: string
          default: "0 9 1 * *"
        index_update:
          type: string
          default: "*/30 * * * *"
      default: {}
    token_optimization:
      type: object
      properties:
        enabled:
          type: boolean
          default: true
        inherit_by_default:
          type: boolean
          default: true
        budget_profile:
          type: string
          enum: ["default", "coding", "analysis", "research", "creative"]
          default: "analysis"
      default: {}
  required: ["vault_path"]
  additionalProperties: true
default_config:
  vault_path: "C:/Users/mathe/Hermes_Brain"
  capture:
    inbox_paths:
      - "00-Inbox"
      - "50-Meta/00-Inbox"
    external_scan_paths:
      - "C:/Users/mathe/Downloads"
      - "C:/Users/mathe/Desktop"
      - "C:/Users/mathe/Documents"
    exclude_patterns:
      - "*.tmp"
      - "*.log"
      - ".git/"
      - "node_modules/"
      - "__pycache__/"
    template: "[[{{date}}]] | #{{type}} #{{context}}\n{{content}}\n#revisar"
    auto_tag_types:
      - "ideia"
      - "tarefa"
      - "referencia"
      - "fleeting"
      - "problema"
      - "insight"
      - "decisao"
  organize:
    para_mapping:
      projeto: "10-Projetos"
      area: "20-Areas"
      recurso: "30-Recursos"
      arquivo: "40-Arquivo"
      meta: "50-Meta"
      sistema: "90-Sistema"
    routing_rules:
      ideia: "projects"
      tarefa: "projects"
      problema: "projects"
      insight: "resources"
      referencia: "resources"
      decisao: "meta"
      reuniao: "meta"
      fleeting: "inbox"
    drift_detection:
      enabled: true
      scan_paths:
        - "C:/Users/mathe/Downloads"
        - "C:/Users/mathe/Desktop"
        - "C:/Users/mathe/Documents"
      exclude_patterns:
        - "*.tmp"
        - "*.log"
        - ".git/"
        - "node_modules/"
        - "__pycache__/"
      dry_run_default: true
      max_loose_files_alert: 10
  distill:
    layers:
      "1":
        name: "Highlights"
        template: "templates/layer1-highlight.md"
        min_length: 50
      "2":
        name: "Literature Notes"
        template: "templates/layer2-literature.md"
        min_length: 200
      "3":
        name: "Resource Notes"
        template: "templates/layer3-resource.md"
        min_length: 500
      "4":
        name: "Atomic Notes"
        template: "templates/layer4-atomic.md"
        min_length: 100
    auto_link:
      enabled: true
      min_similarity: 0.7
      max_links_per_note: 10
    tagging:
      enabled: true
      tag_taxonomy_path: "30-Recursos/_taxonomy/tags.md"
      max_tags_per_note: 8
  express:
    output_types:
      article:
        template: "templates/express-article.md"
        sections: ["intro", "body", "conclusion", "references"]
      report:
        template: "templates/express-report.md"
        sections: ["executive_summary", "findings", "recommendations", "appendix"]
      doc:
        template: "templates/express-doc.md"
        sections: ["overview", "details", "examples", "see_also"]
      newsletter:
        template: "templates/express-newsletter.md"
        sections: ["headline", "stories", "insights", "cta"]
    synthesis_model: "nemotron-3-ultra"
    max_sources: 15
    citation_style: "wiki"
    output_dir: "10-Projetos/_outputs/express/"
  schedule:
    capture_external: "*/30 * * * *"
    organize_inbox: "0 * * * *"
    detect_drift: "0 9 * * *"
    distill_pending: "0 2 * * *"
    express_scheduled: "0 6 * * 1"
    review_weekly: "0 8 * * 1"
    review_monthly: "0 9 1 * *"
    index_update: "*/30 * * * *"
  token_optimization:
    enabled: true
    inherit_by_default: true
    budget_profile: "analysis"
entry_points:
  main:
    type: "main"
    target: "knowledge_pipeline.orchestrator:PipelineOrchestrator"
    description: "Main pipeline orchestrator"
  cli:
    type: "cli"
    target: "knowledge_pipeline.cli:main"
    description: "CLI entry point"
  capture:
    type: "cli"
    target: "knowledge_pipeline.capture:capture_cli"
    description: "Capture command"
  organize:
    type: "cli"
    target: "knowledge_pipeline.organize:organize_cli"
    description: "Organize command"
  distill:
    type: "cli"
    target: "knowledge_pipeline.distill:distill_cli"
    description: "Distill command"
  express:
    type: "cli"
    target: "knowledge_pipeline.express:express_cli"
    description: "Express command"
  cron:
    type: "cli"
    target: "knowledge_pipeline.cron:cron_cli"
    description: "Cron scheduler command"
metadata:
  author: "Hermes Agent"
  license: MIT
  min_hermes_version: "0.20.0"
  tags:
    - knowledge
    - pipeline
    - capture
    - organize
    - distill
    - express
    - review
    - para
    - compounding
    - cron
  homepage: ""
  repository: ""
  documentation: ""
  maintainers: []
  created_at: "2026-08-08"
  updated_at: "2026-08-08"
  deprecated: false
  deprecation_reason: ""
  superseded_by: ""
---

# Knowledge Compounding Pipeline v1.0 — Pipeline Unificado de Conhecimento

**Objetivo:** Pipeline único zero-config que implementa todo o ciclo de conhecimento: Capture → Organize → Distill → Express → Review. Com cron unificado, herança de token optimization, e PARA-first.

---

## 🎯 ARQUITETURA DO PIPELINE

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    KNOWLEDGE COMPOUNDING PIPELINE v1.0                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────┐  │
│  │   CAPTURE    │───▶│   ORGANIZE   │───▶│   DISTILL    │───▶│ EXPRESS  │  │
│  │              │    │              │    │              │    │          │  │
│  │ • User input │    │ • PARA route │    │ • L1 High-   │    │ • Article│  │
│  │ • Vault inbox│    │ • Drift det  │    │   lights     │    │ • Report │  │
│  │ • External   │    │ • Auto-tag   │    │ • L2 Lit.    │    │ • Doc    │  │
│  │   files      │    │ • Frontmatter│    │   notes      │    │ • Newslt │  │
│  │ • MemPalace  │    │   update     │    │ • L3 Res.    │    │          │  │
│  │ • Web/API    │    │              │    │ • L4 Atomic  │    │          │  │
│  └──────────────┘    └──────────────┘    └──────────────┘    └──────────┘  │
│         │                  │                  │                  │          │
│         └──────────────────┼──────────────────┼──────────────────┘          │
│                            ▼                  ▼                            │
│                   ┌─────────────────────────────────────────┐              │
│                   │           CRON SCHEDULER                │              │
│                   │  • 30min: capture_external, index       │              │
│                   │  • Hourly: organize_inbox               │              │
│                   │  • Daily 9am: detect_drift              │              │
│                   │  • Daily 2am: distill_pending           │              │
│                   │  • Mon 6am: express_scheduled           │              │
│                   │  • Mon 8am: review_weekly               │              │
│                   │  • Monthly: review_monthly              │              │
│                   └─────────────────────────────────────────┘              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 STAGES DETALHADOS

### 1. CAPTURE — Entrada Unificada
```python
from knowledge_pipeline import PipelineOrchestrator

pipeline = PipelineOrchestrator()

# Captura direta do usuário
item = pipeline.capture_user_input(
    content="Ideia: usar SQLite para embeddings locais",
    type="ideia",
    context="token-opt"
)

# Scan automático de fontes externas (cron 30min)
captured = pipeline.capture_engine.scan_external_sources(dry_run=False)
```

**Fontes:** User input, Vault inbox (00-Inbox, 50-Meta/00-Inbox), External files (Downloads, Desktop, Documents), MemPalace drawers, Web clippings, API responses

---

### 2. ORGANIZE — Roteamento PARA + Drift Detection
```python
# Processa inbox → PARA (cron hourly)
result = pipeline.organize_now(dry_run=False)

# Detecta arquivos soltos fora do PARA (cron daily 9am)
drift = pipeline.organize_engine.detect_drift(dry_run=False)
```

**Funcionalidades:**
- Roteamento automático por tipo/contexto → 10-Projetos, 20-Areas, 30-Recursos, 40-Arquivo, 50-Meta, 90-Sistema
- Drift detection: scan home directory → alerta/move para inbox
- Auto-tagging baseado em conteúdo
- Frontmatter update com `para_destination`

---

### 3. DISTILL — Sumarização Progressiva L1→L4
```python
# Distila nota específica
result = pipeline.distill_now("30-Recursos/livro-deep-work.md", target_layer=4)

# Batch distila todas pendentes (cron daily 2am)
pending = pipeline.distill_engine.get_pending_distill()
results = pipeline.distill_engine.batch_distill(pending, target_layer=4)
```

**Layers:**
| Layer | Nome | Descrição | Template |
|-------|------|-----------|----------|
| 1 | Highlights | Citações brutas, captures | `layer1-highlight.md` |
| 2 | Literature Notes | Resumo próprio, conexões | `layer2-literature.md` |
| 3 | Resource Notes | Síntese prática | `layer3-resource.md` |
| 4 | Atomic Notes | Uma ideia, atômica, linkável | `layer4-atomic.md` |

**Features:** Auto-linking (similaridade semântica), Auto-tagging (taxonomia), Herança de token optimization

---

### 4. EXPRESS — Geração de Outputs
```python
# Gera artigo a partir de atomic notes
result = pipeline.express_now("Deep Work para times", "article", max_sources=10)

# Batch para múltiplos tópicos
topics = ["Token Optimization", "PARA Method", "Second Brain"]
results = pipeline.express_engine.batch_generate(topics, "report")
```

**Tipos de Output:**
| Tipo | Template | Seções | Uso |
|------|----------|--------|-----|
| article | `express-article.md` | intro, body, conclusion, references | Blog, publicação |
| report | `express-report.md` | exec_summary, findings, recommendations, appendix | Stakeholders |
| doc | `express-doc.md` | overview, details, examples, see_also | Documentação técnica |
| newsletter | `express-newsletter.md` | headline, stories, insights, cta | Email newsletter |

**Features:** Citation tracking (wiki/markdown/APA), Token optimization, Múltiplas fontes atômicas

---

### 5. CRON — Agendamento Unificado
```python
# Inicia scheduler completo
pipeline.start_scheduler()

# Jobs automáticos:
# • */30 * * * *  → capture_external + index_update
# • 0 * * * *     → organize_inbox
# • 0 9 * * *     → detect_drift
# • 0 2 * * *     → distill_pending
# • 0 6 * * 1     → express_scheduled
# • 0 8 * * 1     → review_weekly
# • 0 9 1 * *     → review_monthly
```

---

## ⚙️ CONFIGURAÇÃO (config.yaml)

```yaml
knowledge_pipeline:
  vault_path: "C:/Users/mathe/Hermes_Brain"
  
  # Capture settings
  capture:
    inbox_paths: ["00-Inbox", "50-Meta/00-Inbox"]
    external_scan_paths:
      - "C:/Users/mathe/Downloads"
      - "C:/Users/mathe/Desktop"
      - "C:/Users/mathe/Documents"
    template: "[[{{date}}]] | #{{type}} #{{context}}\n{{content}}\n#revisar"
  
  # Organize settings
  organize:
    para_mapping:
      projeto: "10-Projetos"
      area: "20-Areas"
      recurso: "30-Recursos"
      arquivo: "40-Arquivo"
      meta: "50-Meta"
      sistema: "90-Sistema"
    drift_detection:
      enabled: true
      scan_paths: ["C:/Users/mathe/Downloads", "C:/Users/mathe/Desktop"]
      dry_run_default: true
  
  # Distill settings
  distill:
    layers:
      1: {name: "Highlights", template: "templates/layer1-highlight.md", min_length: 50}
      2: {name: "Literature Notes", template: "templates/layer2-literature.md", min_length: 200}
      3: {name: "Resource Notes", template: "templates/layer3-resource.md", min_length: 500}
      4: {name: "Atomic Notes", template: "templates/layer4-atomic.md", min_length: 100}
    auto_link: {enabled: true, min_similarity: 0.7, max_links_per_note: 10}
  
  # Express settings
  express:
    output_types:
      article: {template: "templates/express-article.md", sections: ["intro", "body", "conclusion", "references"]}
      report: {template: "templates/express-report.md", sections: ["executive_summary", "findings", "recommendations", "appendix"]}
    synthesis_model: "nemotron-3-ultra"
    max_sources: 15
    citation_style: "wiki"
  
  # Schedule (cron expressions)
  schedule:
    capture_external: "*/30 * * * *"
    organize_inbox: "0 * * * *"
    detect_drift: "0 9 * * *"
    distill_pending: "0 2 * * *"
    express_scheduled: "0 6 * * 1"
    review_weekly: "0 8 * * 1"
    review_monthly: "0 9 1 * *"
  
  # Token Optimization (herdado automaticamente)
  token_optimization:
    enabled: true
    inherit_by_default: true
    budget_profile: "analysis"
```

---

## 🔧 API UNIFICADA

```python
from knowledge_pipeline import (
    PipelineOrchestrator, CaptureEngine, OrganizeEngine,
    DistillEngine, ExpressEngine, CronScheduler,
    create_pipeline_orchestrator, create_capture_engine,
    create_organize_engine, create_distill_engine,
    create_express_engine, create_cron_scheduler
)

# Pipeline completo
pipeline = PipelineOrchestrator()

# Engines individuais
capture = create_capture_engine()
organize = create_organize_engine()
distill = create_distill_engine()
express = create_express_engine()
cron = create_cron_scheduler(pipeline)

# Uso direto
item = capture.capture("Nova ideia", type="ideia", context="projeto")
org = organize.process_inbox(auto=True)
dist = distill.distill_note("00-Inbox/nota.md", target_layer=4)
exp = express.generate("Tópico", "article")
cron.start()
```

---

## 📁 ESTRUTURA DE ARQUIVOS

```
knowledge-pipeline/
├── SKILL.md                          # Este arquivo
├── __init__.py                       # Entry point + exports
├── config.yaml                       # Configuração unificada
├── capture.py                        # Capture engine
├── organize.py                       # Organize engine
├── distill.py                        # Distill engine
├── express.py                        # Express engine
├── orchestrator.py                   # Pipeline orchestrator
├── cron.py                           # Cron scheduler
├── cli.py                            # CLI commands
├── templates/                        # Jinja2 templates
│   ├── layer1-highlight.md
│   ├── layer2-literature.md
│   ├── layer3-resource.md
│   ├── layer4-atomic.md
│   ├── express-article.md
│   ├── express-report.md
│   ├── express-doc.md
│   └── express-newsletter.md
└── test_pipeline.py                  # Testes integrados
```

---

## 🧪 TESTE DE VALIDAÇÃO

```bash
# No Hermes:
/skill knowledge-pipeline

# Testes rápidos:
from knowledge_pipeline import PipelineOrchestrator
p = PipelineOrchestrator()

# Capture
item = p.capture_user_input("Teste capture", "ideia", "teste")

# Organize
org = p.organize_now(dry_run=True)

# Distill
dist = p.distill_now("00-Inbox/teste.md", target_layer=2)

# Express
exp = p.express_now("Teste Pipeline", "article")

# Pipeline completo
result = p.run_full_pipeline(capture_external=True, organize=True, distill=True)

# Cron
p.start_scheduler()
status = p.get_status()
pending = p.get_pending_work()
```

---

## 🔗 INTEGRAÇÕES

| Skill | Integração |
|-------|------------|
| `second-brain-pipeline` | Review stage, templates PARA, dataview queries |
| `token-optimization` | Herdado automaticamente (budget_profile: analysis) |
| `memory-substrate` | Indexação vetorial para busca semântica no distill/express |
| `note-taking-tools` | Vault operations, PARA routing, drift detection |
| `hermes-squad-core` | Advisory board para decisões de pipeline |

---

*knowledge-pipeline v1.0.0 — Pipeline de Conhecimento Unificado de Produção*  
*Capture → Organize → Distill → Express → Review com cron unificado e token optimization nativo*