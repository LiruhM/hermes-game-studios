# CLAUDE.md — Legacy Compatibility Redirect

> **This project has migrated to Hermes (Nous Research) native tooling.**
> 
> **Please use `HERMES.md` as the project memory file.**
> 
> **Hermes-native configuration lives in `.hermes/` (replaces `.claude/`).**

---

## Quick Reference

| CCGS Path | Hermes Path |
|-----------|-------------|
| `CLAUDE.md` | `HERMES.md` |
| `.claude/settings.json` | `.hermes/settings.json` |
| `.claude/settings.local.json` | `.hermes/settings.local.json` |
| `.claude/agents/` | `.hermes/agents/` |
| `.claude/skills/` | `.hermes/skills/` |
| `.claude/hooks/` | `.hermes/hooks/` (Python, not bash) |
| `.claude/scripts/` | `.hermes/scripts/` |
| `.claude/docs/` | `Hermes_Brain/10-Projetos/.../docs/` + `.hermes/prompts/` |

---

## Hermes Commands

```bash
# Start a session
/hermes:start

# Show help
/hermes:help

# Detect project stage
/hermes:project-stage-detect

# Configure engine
/hermes:setup-engine

# Run quality gates
/hermes:gate-check

# Full skill list
/hermes:help --skills
```

---

## Agent Dispatch

All 49 agents are dispatched via `delegate_task` with `role: "leaf"`:

```json
{
  "tasks": [{
    "role": "leaf",
    "goal": "Implement GameSystemInterface",
    "context": {
      "agent_name": "gameplay-programmer",
      "sector": "morgana",
      "model_tier": "inherit",
      "contracts": [".hermes/contracts/arch-to-impl.yaml"]
    },
    "model_tier": "inherit"
  }]
}
```

---

## Key Differences from CCGS

1. **Python hooks** — `.hermes/hooks/*.py` (not bash)
2. **Structured skills** — `.hermes/skills/*/SKILL.md` with YAML frontmatter
3. **Contract-based** — Frozen YAML contracts in `.hermes/contracts/`
4. **Sector orchestration** — Nephy/Morgana/Debora/Alice/Liruh with explicit boundaries
5. **Free-only providers** — NVIDIA, OpenRouter, Ollama fallback chain
6. **Memory-Substrate** — Vault PARA + MemPalace + Graph index

---

*See `HERMES.md` for complete project memory and `AGENTS.md` for agent registry.*