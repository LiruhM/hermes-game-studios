# Hermes Game Studios

> **Native Hermes (Nous Research) Game Development Studio Template**
> 
> A complete migration from Claude Code Game Studios (CCGS) to Hermes-native tooling with sector-based orchestration, contract-driven workflows, and free-only AI providers.

## Overview

Hermes Game Studios is a game development studio template built on **Hermes** (Nous Research's AI agent framework). It provides:

- **49 Specialized Agents** — Directors, Leads, Specialists across 5 sectors
- **74 Skills** — Structured workflows for game design, architecture, QA, release, and team orchestration
- **19 Python Hooks** — Session lifecycle, validation, and automation
- **39 Deterministic Scripts** — Build, analysis, and utility helpers
- **5 Frozen Contracts** — Inter-sector agreements with binary validation
- **Multi-Engine Ready** — Godot 4, Unity, Unreal 5 support

## Architecture

### Five Sectors (The Hermes Company)

| Sector | Chief | Domain |
|--------|-------|--------|
| **Nephy** | Arquiteta-Chefe | Architecture & Design |
| **Morgana** | Implementadora-Chefe | Implementation & Code |
| **Debora** | Qualidade-Chefe | QA, Tests, Validation |
| **Alice** | Curadora-Chefe | Knowledge, Research, Docs |
| **Liruh** | Operadora-Chefe | Production, Ops, Release |

### Communication Protocol

- **All cross-sector communication via disk artifacts** (contracts, reports, vault)
- **Liruh is the ONLY dispatcher** — sectors never self-dispatch
- **Contracts are LAW** — frozen YAML files in `.hermes/contracts/`
- **Validation is BINARY** — PASS / CONCERNS / FAIL

## Quick Start

```bash
# Clone and enter
git clone <repo> Hermes-Game-Studios
cd Hermes-Game-Studios

# Start Hermes session
/hermes:start

# Detect project stage
/hermes:project-stage-detect

# Configure engine (Godot/Unity/Unreal)
/hermes:setup-engine

# Run quality gates
/hermes:gate-check
```

## Project Structure

```
Hermes-Game-Studios/
├── HERMES.md              # Project memory (auto-loads in Hermes)
├── AGENTS.md              # Agent registry (49 agents)
├── project.yaml           # Machine-readable config
├── .hermes/               # Hermes native config
│   ├── settings.json
│   ├── skills/            # 74 skills
│   ├── agents/            # 49 agent definitions
│   ├── hooks/             # 19 Python hooks
│   ├── scripts/           # 39 scripts
│   ├── rules/             # Lint rules (ESLint, Ruff, Clippy)
│   ├── prompts/           # 7 structured prompts
│   ├── contracts/         # 5 frozen contracts
│   └── memory/            # Session state
├── src/                   # Code root (Godot default)
├── assets/                # Game assets
├── design/                # Game design documents
├── docs/                  # Technical documentation
├── tests/                 # Test suites
├── prototypes/            # Throwaway prototypes
├── production/            # Production management
├── studio-tests/          # QA for skills/agents
└── .github/               # CI/CD workflows
```

## Model Tiers

| Tier | Hermes Equivalent | Used By |
|------|-------------------|---------|
| `architecture` | opus-equivalent | Directors (6) |
| `implementation` | sonnet-equivalent | Specialists (23) |
| `inherit` | Session parent | All others (20) |

**Default Provider:** `nvidia/nemotron-3-ultra` (free tier)
**Fallback Chain:** NVIDIA → OpenRouter → Ollama

## Quality Gates (Non-Negotiable)

1. **Interface Conformance** — Binary test against frozen contract
2. **Max Lines/File** — 350 lines
3. **No Direct Console** — `print()`, `console.log()`, `GD.print()` banned
4. **No Direct Data Access** — `get_node()`, `$NodeName` → inject services
5. **Test Coverage** — 80% minimum per module
6. **Performance Budgets** — Per-system frame/memory limits
7. **Cross-Boundary Check** — Morgana never touches Nephy files

## Review Modes

| Mode | Phase Gates | Director Gates |
|------|-------------|----------------|
| `solo` | SKIP all | SKIP all |
| `lean` | Phase gates only | PR minimal, TD+PR standard, all 4 full |
| `full` | All phase gates | All 4 directors at every phase gate |

## Documentation

- [HERMES.md](HERMES.md) — Project memory (single source of truth)
- [AGENTS.md](AGENTS.md) — Complete agent registry
- [project.yaml](project.yaml) — Machine-readable configuration
- [SECTOR_CONTRACTS.md](docs/architecture/sector-contracts.md) — Inter-sector contracts
- [DIRECTORY_STRUCTURE.md](docs/architecture/directory-structure.md) — Full directory tree

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

## License

See [LICENSE](LICENSE) for license information.

## Security

See [SECURITY.md](SECURITY.md) for security policy.

---

**Built with Hermes (Nous Research)** — AI-native game development workflows.# Test
