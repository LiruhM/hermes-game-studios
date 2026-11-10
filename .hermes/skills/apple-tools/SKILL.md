---
name: apple-tools
version: "1.0.0"
description: "Apple Ecosystem Automation - Shortcuts, AppleScript, iCloud, Continuity, AirDrop"
author: Hermes Agent
license: MIT
platforms: [darwin]  # macOS only
metadata:
  hermes:
    tags: [apple, macos, ios, shortcuts, applescript, icloud, continuity, airdrop]
    related_skills: [creative-tools, media-tools, productivity-tools]
    replaces: []

---

# Apple Tools v1.0 — Apple Ecosystem Automation

**Objetivo:** Automação nativa do ecossistema Apple: Shortcuts, AppleScript, iCloud Drive, Continuity (Handoff, AirDrop, Universal Clipboard).

---

## 🎯 FERRAMENTAS INCLUÍDAS

| Ferramenta | Função |
|------------|--------|
| **Shortcuts** | Gerenciar e executar atalhos do iOS/macOS |
| **AppleScript** | Executar AppleScript para automação de apps |
| **iCloud Sync** | Sincronizar arquivos no iCloud Drive |
| **Continuity** | Handoff, AirDrop, Universal Clipboard |

---

## ⚙️ CONFIGURAÇÃO (config.yaml)

```yaml
apple_tools:
  shortcuts:
    shortcuts_dir: "~/Library/Shortcuts"
  applescript:
    timeout: 30
  icloud:
    icloud_dir: "~/Library/Mobile Documents/com~apple~CloudDocs"
  continuity:
    enable_handoff: true
    enable_airdrop: true
    universal_clipboard: true
```

---

## 🔧 API UNIFICADA

```python
from apple_tools import create_apple_tools

tools = create_apple_tools(config)

# === SHORTCUTS ===
shortcuts = tools["shortcuts"]
shortcuts.list_shortcuts()
result = shortcuts.run_shortcut("Meu Atalho", {"input": "dados"})
new_shortcut = shortcuts.create_shortcut("Novo Atalho", [
    {"action": "get_text", "text": "Olá"},
    {"action": "show_result"}
])

# === APPLESCRIPT ===
applescript = tools["applescript"]
result = applescript.run_script('tell app "Finder" to get name of startup disk')
applescript.tell_app("Safari", 'open location "https://example.com"')
applescript.activate_app("Terminal")
applescript.get_app_property("Finder", "version")

# === ICLOUD ===
icloud = tools["icloud"]
files = icloud.list_files("Projetos")
icloud.download_file("Projetos/arquivo.pdf")
icloud.upload_file(Path("local.txt"), "Backup/local.txt")
storage = icloud.get_storage_info()

# === CONTINUITY ===
continuity = tools["continuity"]
devices = continuity.list_devices()
continuity.send_airdrop([Path("arquivo.pdf")])
continuity.set_clipboard("Texto universal", universal=True)
clipboard = continuity.get_clipboard()
```

---

## 📁 ESTRUTURA DE ARQUIVOS

```
apple-tools/
├── SKILL.md
├── __init__.py
├── config.yaml
├── apple_tools/
│   ├── __init__.py
│   ├── shortcuts.py
│   ├── applescript.py
│   ├── icloud.py
│   └── continuity.py
└── test_apple_tools.py
```

---

*apple-tools v1.0 — Automação Nativa do Ecossistema Apple*