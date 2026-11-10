---
name: observability-dashboard
version: "1.0.0"
description: "Observability Dashboard — Real-time metrics, health monitoring, and visual dashboards for the Hermes skill ecosystem. Integrates with cross-skill-workflows, token-optimization, and all consolidated skills."
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [observability, dashboard, metrics, monitoring, health, visualization, prometheus, grafana]
    related_skills: [cross-skill-workflows, token-optimization, skill-composability, skill-marketplace, hermes-squad-core]
    replaces: []

---

# Observability Dashboard v1.0.0 — Métricas & Monitoramento Visual

**Objetivo:** Dashboard unificado para monitorar saúde, performance e uso de todas as skills do ecossistema Hermes. Coleta métricas em tempo real, alertas, dashboards visuais (Rich/TUI, Web, Prometheus/Grafana) e integração nativa com workflows.

---

## 🎯 CAPABILITIES

| Capability | Description |
|------------|-------------|
| **Metrics Collection** | Coleta automática de métricas de skills, workflows, tokens, latency |
| **Health Monitoring** | Health checks contínuos, SLA/SLO tracking, alertas |
| **Real-time Dashboard** | TUI (Rich), Web (FastAPI + HTMX), Prometheus/Grafana export |
| **Workflow Observability** | Integração nativa com cross-skill-workflows events |
| **Token Tracking** | Integração com token-optimization budget governor |
| **Skill Registry Sync** | Auto-descoberta de skills consolidadas (16 skills) |
| **Alerting** | Threshold-based alerts via NTFY, console, webhook |
| **Historical Analysis** | Trends, anomalias, capacity planning |

---

## ⚙️ CONFIGURAÇÃO (config.yaml)

```yaml
observability_dashboard:
  # Collection
  collection_interval_seconds: 30
  retention_days: 30
  
  # Storage
  metrics_db: "90-Sistema/_data/observability.db"
  vault_sync: true
  vault_path: "C:/Users/mathe/Hermes_Brain/50-Meta/observability"
  
  # Data sources
  sources:
    - cross_skill_workflows    # workflow events
    - token_optimization       # token budgets, latency
    - skill_composability      # skill health, load times
    - skill_marketplace        # install/publish rates
    - hermes_squad_core        # agent performance
    - system                   # CPU, RAM, disk, GPU
  
  # Dashboards
  dashboards:
    tui:
      enabled: true
      refresh_rate: 5  # seconds
      theme: "monokai"
    web:
      enabled: true
      host: "0.0.0.0"
      port: 8080
      auth: false
    prometheus:
      enabled: true
      port: 9090
      path: "/metrics"
    grafana:
      enabled: false  # external
      datasource: "prometheus"
  
  # Alerts
  alerts:
    enabled: true
    channels:
      - console
      - ntfy
      - webhook
    rules:
      - name: high_token_usage
        metric: "token_usage_pct"
        threshold: 80
        operator: ">"
        severity: "warning"
      - name: workflow_failure_rate
        metric: "workflow_failure_rate"
        threshold: 0.1
        operator: ">"
        severity: "critical"
      - name: skill_load_time
        metric: "skill_load_time_ms"
        threshold: 5000
        operator: ">"
        severity: "warning"
      - name: system_memory
        metric: "memory_usage_pct"
        threshold: 85
        operator: ">"
        severity: "warning"
      - name: workflow_queue_depth
        metric: "workflow_queue_depth"
        threshold: 50
        operator: ">"
        severity: "warning"
  
  # Token Optimization Integration
  token_optimization:
    enabled: true
    track_budgets: true
    track_latency: true
    track_compression_ratio: true
```

---

## 🔧 API UNIFICADA

```python
from observability_dashboard import ObservabilityDashboard, MetricsCollector

dashboard = ObservabilityDashboard(config)

# Start collection
dashboard.start()

# Get current metrics snapshot
metrics = dashboard.get_metrics()
print(f"Workflows: {metrics['workflows']['active']} active, {metrics['workflows']['completed']} completed")
print(f"Tokens: {metrics['tokens']['usage_pct']}% used")
print(f"Skills: {metrics['skills']['loaded']}/{metrics['skills']['total']} loaded")

# Query time series
token_history = dashboard.query_metric("token_usage_pct", hours=24)
workflow_trends = dashboard.query_metric("workflow_duration_ms", hours=168)  # 1 week

# Get health status
health = dashboard.get_health()
print(f"Overall: {health['overall']}")  # healthy | degraded | critical
for component, status in health['components'].items():
    print(f"  {component}: {status}")

# Check alerts
alerts = dashboard.get_active_alerts()
for alert in alerts:
    print(f"🚨 {alert['severity']}: {alert['message']}")

# Export for Prometheus
prometheus_metrics = dashboard.export_prometheus()

# Generate dashboard snapshot (for reports)
snapshot = dashboard.generate_snapshot()
dashboard.save_snapshot(snapshot, "daily-report-2026-08-09")

# Stop collection
dashboard.stop()
```

---

## 📊 METRICS COLLECTED

### Workflow Metrics
| Metric | Type | Description |
|--------|------|-------------|
| `workflows_started_total` | Counter | Total workflows started |
| `workflows_completed_total` | Counter | Successful completions |
| `workflows_failed_total` | Counter | Failed executions |
| `workflow_duration_ms` | Histogram | End-to-end latency |
| `workflow_step_duration_ms` | Histogram | Per-step latency |
| `workflow_queue_depth` | Gauge | Pending executions |

### Token Metrics (via token-optimization)
| Metric | Type | Description |
|--------|------|-------------|
| `token_usage_pct` | Gauge | Budget utilization % |
| `token_budget_remaining` | Gauge | Tokens left in budget |
| `token_compression_ratio` | Gauge | Achieved compression |
| `token_latency_ms` | Histogram | Token processing time |

### Skill Metrics
| Metric | Type | Description |
|--------|------|-------------|
| `skill_load_time_ms` | Histogram | Skill initialization time |
| `skill_memory_mb` | Gauge | Memory per skill |
| `skill_errors_total` | Counter | Errors by skill |
| `skill_health` | Gauge | 0=down, 1=degraded, 2=healthy |

### System Metrics
| Metric | Type | Description |
|--------|------|-------------|
| `system_cpu_pct` | Gauge | CPU usage |
| `system_memory_pct` | Gauge | RAM usage |
| `system_disk_pct` | Gauge | Disk usage |
| `system_gpu_pct` | Gauge | GPU usage (if available) |

---

## 📁 ARQUITETURA

```
observability-dashboard/
├── SKILL.md
├── __init__.py
├── config.yaml
├── observability_dashboard/
│   ├── __init__.py
│   ├── collector.py          # Metrics collection from sources
│   ├── storage.py            # SQLite + time-series storage
│   ├── dashboard_tui.py      # Rich TUI dashboard
│   ├── dashboard_web.py      # FastAPI + HTMX web dashboard
│   ├── prometheus_exporter.py # Prometheus metrics endpoint
│   ├── alerting.py           # Alert engine
│   ├── health.py             # Health check orchestrator
│   └── snapshot.py           # Dashboard snapshots for reports
├── templates/
│   ├── tui/                  # Rich layout templates
│   ├── web/                  # HTML/JS templates
│   └── grafana/              # Grafana dashboard JSON
└── test_dashboard.py
```

---

## 🧪 TESTE DE VALIDAÇÃO

```bash
# No Hermes:
/skill observability-dashboard

# Teste rápido:
from observability_dashboard import ObservabilityDashboard
d = ObservabilityDashboard()
d.start()

# Aguarda coleta
import time
time.sleep(2)

metrics = d.get_metrics()
print(f"Workflows: {metrics['workflows']}")
print(f"Tokens: {metrics['tokens']}")
print(f"System: {metrics['system']}")

health = d.get_health()
print(f"Health: {health['overall']}")

alerts = d.get_active_alerts()
print(f"Alerts: {len(alerts)}")

d.stop()
```

---

*observability-dashboard v1.0.0 — Seeing Everything, Understanding Everything*