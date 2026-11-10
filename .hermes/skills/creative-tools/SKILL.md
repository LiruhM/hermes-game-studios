---
name: creative-tools
version: "1.0.0"
description: "Creative Content Generation - ASCII art, diagrams, charts, templates, image generation prompts"
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [creative, ascii, diagrams, charts, templates, prompts, generation]
    related_skills: [media-tools, productivity-tools, software-dev-tools]
    replaces: []

---

# Creative Tools v1.0 — Geração de Conteúdo Criativo

**Objetivo:** Ferramentas para geração de conteúdo visual e textual: ASCII art, diagramas, charts, templates, prompts para geração de imagem.

---

## 🎯 FERRAMENTAS INCLUÍDAS

| Ferramenta | Função |
|------------|--------|
| **ASCII Art** | Gerar arte ASCII a partir de texto/imagem |
| **Diagrams** | Diagramas Mermaid, PlantUML, Graphviz |
| **Charts** | Gráficos ASCII/terminal (sparkline, bar, pie) |
| **Templates** | Templates Jinja2 para documentos |
| **Prompts** | Otimização de prompts para geração de imagem |

---

## ⚙️ CONFIGURAÇÃO (config.yaml)

```yaml
creative_tools:
  ascii:
    width: 80
    font: "standard"
  diagrams:
    mermaid: true
    plantuml: true
    graphviz: true
  charts:
    sparkline: true
    bar_chart: true
  templates:
    engine: "jinja2"
    template_dir: "30-Recursos/templates/creative"
```

---

## 🔧 API UNIFICADA

```python
from creative_tools import CreativeTools

ct = CreativeTools()

# ASCII Art
ascii_art = ct.ascii.text_to_ascii("HERMES", font="banner")
ascii_img = ct.ascii.image_to_ascii("image.png", width=80)

# Diagrams
mermaid = ct.diagrams.mermaid("graph TD; A-->B; B-->C")
plantuml = ct.diagrams.plantuml("@startuml\nAlice -> Bob: Hello\n@enduml")

# Charts
spark = ct.charts.sparkline([1, 3, 2, 5, 4, 6])
bar = ct.charts.bar_chart({"A": 10, "B": 20, "C": 15})

# Templates
rendered = ct.templates.render("email.j2", {"name": "João", "items": ["A", "B"]})
```

---

*creative-tools v1.0 — Criatividade no Terminal*