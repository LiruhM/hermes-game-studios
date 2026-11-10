---
name: devops-tools
version: "1.0.0"
description: "DevOps/Infrastructure Tools - Docker, Kubernetes, Terraform, Ansible, CI/CD, Monitoring"
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [devops, docker, kubernetes, terraform, ansible, cicd, monitoring, infrastructure]
    related_skills: [software-dev-tools, mlops-tools, media-tools]
    replaces: []

---

# DevOps Tools v1.0 — Infraestrutura e DevOps

**Objetivo:** Ferramentas para automação de infraestrutura: Docker, Kubernetes, Terraform, Ansible, CI/CD, monitoramento.

---

## 🎯 FERRAMENTAS INCLUÍDAS

| Ferramenta | Função |
|------------|--------|
| **Docker** | Build, run, compose, registry management |
| **Kubernetes** | kubectl wrapper, manifests, helm charts |
| **Terraform** | Plan, apply, state management |
| **Ansible** | Playbooks, inventory, roles |
| **CI/CD** | Pipeline generation, GitHub Actions, GitLab CI |
| **Monitoring** | Prometheus, Grafana, alerting |

---

## ⚙️ CONFIGURAÇÃO (config.yaml)

```yaml
devops_tools:
  docker:
    registry: "docker.io"
    compose_file: "docker-compose.yml"
  kubernetes:
    kubeconfig: "~/.kube/config"
    namespace: "default"
    helm_repo: "https://charts.helm.sh/stable"
  terraform:
    backend: "local"
    state_path: "terraform.tfstate"
  ansible:
    inventory: "inventory.yml"
    playbook_dir: "playbooks"
  cicd:
    provider: "github-actions"
  monitoring:
    prometheus_url: "http://localhost:9090"
    grafana_url: "http://localhost:3000"
```

---

*devops-tools v1.0 — Infraestrutura como Código*