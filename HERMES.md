# Hermes Game Studios — Project Memory

**Project:** Hermes Game Studios
**Engine:** Godot 4.3 (default, configurable via project.yaml)
**Architecture:** Multi-engine ready (Godot, Unity, Unreal)
**Owner:** CEO Matheus
**Profile:** default
**Session Started:** 2026-11-09

---

## Project Identity

Hermes Game Studios is a native Hermes (Nous Research) game development studio template — a complete migration from Claude Code Game Studios (CCGS) to Hermes-native tooling. This project serves as both the studio's operational backbone and a reference implementation for Hermes-native game development.

**Mission:** Build games with AI-native workflows, rigorous quality gates, and sector-based orchestration (Nephy/Morgana/Debora/Alice/Liruh).

---

## Architecture Overview

### Five Sectors (The Hermes Company)

| Sector | Chief | Domain | Responsibility |
|--------|-------|--------|----------------|
| **Nephy** | Arquiteta-Chefe | Architecture & Design | Blueprint, ADRs, architectural decisions, cross-team contracts, pillars |
| **Morgana** | Implementadora-Chefe | Implementation & Code | Write code, implement stories, refactor, technical code review |
| **Debora** | Qualidade-Chefe | QA, Tests, Validation | Tests, boundary validation, gates, quality gates, regression |
| **Alice** | Curadora-Chefe | Knowledge, Research, Docs | Vault PARA, MemPalace, research, documentation, onboarding |
| **Liruh** | Operadora-Chefe | Production, Ops, Release | Sprint planning, milestones, release, cross-dept coordination, risk |

### Communication Protocol
- **All cross-sector communication via disk artifacts** (contracts, reports, vault)
- **Liruh is the ONLY dispatcher** — sectors never self-dispatch
- **Contracts are LAW** — frozen YAML files in `.hermes/contracts/`
- **Validation is BINARY** — PASS / CONCERNS / FAIL (no "almost ready")

---

## Engine Configuration

**Default:** Godot 4.3+
**Configurable via:** `project.yaml` → `engine.name`
**Code Root Resolution:** Skills read `engine.name` and resolve paths via `resolve_config`

| Engine | Code Root | Test Root | Assets Root |
|--------|-----------|-----------|-------------|
| Godot 4 | `src/` | `tests/unit/`, `tests/integration/` | `assets/` |
| Unity | `Assets/` (symlink) | `Assets/Tests/EditMode/`, `Assets/Tests/PlayMode/` | `Assets/` |
| Unreal 5 | `Source/<Module>/` (symlink) | `Source/<Module>/Private/Tests/` | `Content/` |

---

## Key Directories

```
Hermes-Game-Studios/
├── HERMES.md                    # This file (project memory, auto-loads in Hermes)
├── AGENTS.md                    # Cross-tool agent registry (mirrors HERMES.md agents)
├── project.yaml                 # Machine-readable config: engine, specialists, modes
├── .hermes/                     # HERMES NATIVE CONFIG (replaces .claude/)
│   ├── settings.json            # Project settings
│   ├── settings.local.json      # Local overrides (gitignored)
│   ├── skills/                  # 74 native skills (hermes-*)
│   ├── agents/                  # 49 delegate_task roles
│   ├── hooks/                   # Python session hooks
│   ├── scripts/                 # 39 deterministic helpers
│   ├── rules/                   # Lint/quality gate rules
│   ├── prompts/                 # Structured reusable prompts
│   ├── memory/                  # Local persistent state
│   └── contracts/               # Frozen inter-sector contracts
├── src/                         # Code root (Godot default)
├── assets/                      # Game assets
├── design/                      # Game design documents
├── docs/                        # Technical documentation
├── tests/                       # Test suites
├── prototypes/                  # Throwaway prototypes
├── tools/                       # Build/pipeline tools
├── production/                  # Production management
├── studio-tests/                # QA for skills/agents themselves
├── .github/                     # GitHub workflows & templates
└── Hermes_Brain/                # VAULT OBSIDIAN PARA (external, ~/Hermes_Brain/)
```

---

## Model Tiers

| Tier | Hermes Equivalent | Used By |
|------|-------------------|---------|
| `architecture` | opus-equivalent | Directors: creative-director, technical-director, producer, art-director, audio-director, narrative-director |
| `implementation` | sonnet-equivalent | Specialists: engine subs, programmers, designers |
| `inherit` | Session parent model (default: nvidia/nemotron-3-ultra) | All others |

---

## Quality Gates (Non-Negotiable)

1. **Interface Conformance** — Binary test against frozen contract
2. **Max Lines/File** — 350 lines (enforced by lint)
3. **No Direct Console** — `print()`, `console.log()`, `GD.print()` banned
4. **No Direct Data Access** — `get_node()`, `$NodeName` → inject services (warn initially)
5. **Test Coverage** — 80% minimum per module
6. **Performance Budgets** — Per-system frame/memory limits
7. **Cross-Boundary Check** — Morgana never touches Nephy files

---

## Review Modes (Per Project)

| Mode | Phase Gates | Director Gates |
|------|-------------|----------------|
| `solo` | SKIP all | SKIP all |
| `lean` | Phase gates only | PR minimal, TD+PR standard, all 4 full |
| `full` | All phase gates | All 4 directors at every phase gate |

---

## Dispatch DNA (Every Subagent Receives)

1. **Write Incrementally** — First write_file in first response (~80 lines), then patches
2. **Read-Back Verification** — Read own output from disk before finishing
3. **Surgical Context** — Only what sector needs; >300 lines → map + offset/limit reads
4. **Move, Never Delete** — Quarantine (40-Arquivo/quarentena-*) instead of delete
5. **Terminate Own Processes** — Zero zombies
6. **Context Ceiling** — Max 2 continuations; 3rd = task too large, split dispatch
7. **Unstable Provider** — Pause new dispatches until stable; disk work continues
8. **Fallback Model** — Native Hermes covers provider failure (429/529/503), NOT truncation

---

## Active Contracts (Disk Artifacts)

- `.hermes/contracts/arch-to-impl.yaml` — Nephy → Morgana (frozen interfaces)
- `.hermes/contracts/impl-to-qa.yaml` — Morgana → Debora (deliverables + validation requests)
- `.hermes/contracts/qa-report.yaml` — Debora → Nephy/Morgana (verdict + concerns)
- `.hermes/contracts/curator-services.yaml` — Alice → All (Vault, MemPalace, Memory-Substrate, Research)
- `.hermes/contracts/ops-services.yaml` — Liruh → All (Sprints, Milestones, Releases, Risk, Coordination)

---

## Ntfy Integration

**Topic:** `hermes-mathe-r8gemiyxxm`
**Priority Map:**
- `circuit_opened`, `degradation_escalated`, `provider_down`, `dispatch_failed`, `milestone_at_risk`, `sprint_blocked` → `high`
- `fallback_activated` → `default`
- `provider_restored`, `dispatch_completed` → `default`

---

## Session State

**Checkpoint:** `.hermes/memory/active.md` (symlinked to `production/session-state/active.md`)
**Audit Trail:** `.hermes/memory/session-logs/` (symlinked to `production/session-logs/`)
**Skill State:** `.hermes/memory/skill-state/`

---

## Gitignore Essentials

```gitignore
# Hermes local state
.hermes/memory/active.md
.hermes/memory/session-logs/
.hermes/memory/skill-state/
.hermes/settings.local.json

# Session state (legacy compat)
production/session-state/active.md
production/session-logs/

# Studio tests results
studio-tests/results/

# OS / IDE
.DS_Store
Thumbs.db
.vscode/
.idea/
*.swp
*.swo

# Engine specific (Godot)
*.import
*.translation
export_presets.cfg

# Engine specific (Unity)
Library/
Temp/
Obj/
Build/
Logs/
UserSettings/

# Engine specific (Unreal)
Binaries/
Intermediate/
DerivedDataCache/
Saved/
```

---

## Symlinks (Compatibility)

```bash
ln -s .hermes/memory/active.md production/session-state/active.md
ln -s .hermes/memory/session-logs production/session-logs
```

---

## Next Actions

1. ✅ Phase 1: Create `.hermes/` native structure (this deliverable)
2. ⏳ Phase 2: Populate 74 skills with full SKILL.md content
3. ⏳ Phase 3: Populate 49 agent definitions with DNA + contracts
4. ⏳ Phase 4: Implement 19 Python hooks
5. ⏳ Phase 5: Implement 39 deterministic scripts
6. ⏳ Phase 6: Create lint rules + prompts
7. ⏳ Phase 7: Validate end-to-end with `hermes:start` bootstrap

---

*This file is the single source of truth for project memory. It auto-loads in Hermes sessions. Keep it current.*