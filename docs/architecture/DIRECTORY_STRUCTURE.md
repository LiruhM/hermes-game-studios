# Directory Structure — Hermes Game Studios

> Complete directory tree with purpose for each path.

---

## Root Level

```
Hermes-Game-Studios/
├── HERMES.md                    # Project memory (auto-loads in Hermes sessions)
├── AGENTS.md                    # Agent registry (49 agents, 1:1 from CCGS)
├── project.yaml                 # Machine-readable config (engine, specialists, modes)
├── LICENSE                      # MIT License
├── CONTRIBUTING.md              # Contribution guidelines
├── SECURITY.md                  # Security policy & vulnerability reporting
├── CHANGELOG.md                 # Keep a Changelog format
├── RELEASE_READINESS.md         # Release checklist & criteria
├── CLAUDE.md                    # Legacy CCGS reference (for migration context)
├── README.md                    # This repo's entry point
├── package.json                 # Node.js scripts (ESLint) + devDependencies
├── Cargo.toml                   # Rust workspace (Clippy)
├── .gitignore                   # Comprehensive ignore patterns
├── .gitattributes               # Git LFS / line endings
├── .github/                     # GitHub workflows, issue templates, CODEOWNERS
├── .hermes/                     # HERMES NATIVE CONFIG (replaces .claude/)
├── src/                         # Code root (Godot default)
├── assets/                      # Game assets (gitignored heavy files)
├── design/                      # Game design documents
├── docs/                        # Technical documentation
├── tests/                       # Test suites (unit, integration)
├── prototypes/                  # Throwaway prototypes (gitignored)
├── production/                  # Production management
├── studio-tests/                # QA for skills/agents themselves
├── scripts/                     # Build/pipeline scripts (bash, Python)
├── tools/                       # Custom tools (Rust, Python)
└── .ruff_cache/                 # Ruff cache (gitignored)
```

---

## `.hermes/` — Hermes Native Configuration

```
.hermes/
├── settings.json                # Project settings (model tiers, review modes, ntfy)
├── settings.local.json          # Local overrides (gitignored)
├── skills/                      # 74 native skills (hermes-*)
│   ├── hermes-adopt/            # Brownfield template adoption
│   ├── hermes-architecture-decision/
│   ├── hermes-architecture-review/
│   ├── hermes-art-bible/
│   ├── hermes-asset-audit/
│   ├── hermes-asset-spec/
│   ├── hermes-balance-check/
│   ├── hermes-brainstorm/
│   ├── hermes-bug-report/
│   ├── hermes-bug-triage/
│   ├── hermes-changelog/
│   ├── hermes-code-review/
│   ├── hermes-consistency-check/
│   ├── hermes-create-architecture/
│   ├── hermes-create-control-manifest/
│   ├── hermes-create-epics/
│   ├── hermes-create-stories/
│   ├── hermes-dev-story/
│   ├── hermes-design-review/
│   ├── hermes-design-system/
│   ├── hermes-estimate/
│   ├── hermes-gate-check/
│   ├── hermes-help/
│   ├── hermes-hotfix/
│   ├── hermes-localize/
│   ├── hermes-map-systems/
│   ├── hermes-milestone-review/
│   ├── hermes-onboard/
│   ├── hermes-perf-profile/
│   ├── hermes-playtest-report/
│   ├── hermes-prototype/
│   ├── hermes-qa-plan/
│   ├── hermes-quick-design/
│   ├── hermes-release-checklist/
│   ├── hermes-regression-suite/
│   ├── hermes-reverse-document/
│   ├── hermes-security-audit/
│   ├── hermes-smoke-check/
│   ├── hermes-soak-test/
│   ├── hermes-skill-improve/
│   ├── hermes-skill-test/
│   ├── hermes-sprint-plan/
│   ├── hermes-sprint-status/
│   ├── hermes-start/
│   ├── hermes-test-helpers/
│   ├── hermes-test-setup/
│   ├── hermes-ux-design/
│   ├── hermes-ux-review/
│   ├── hermes-vertical-slice/
│   ├── apple-tools/
│   ├── creative-tools/
│   ├── cross-skill-workflows/
│   └── devops-tools/
├── agents/                      # 49 delegate_task agent definitions
│   ├── accessibility-specialist.md
│   ├── ai-programmer.md
│   ├── analytics-engineer.md
│   ├── art-director.md
│   ├── audio-director.md
│   ├── community-manager.md
│   ├── creative-director.md
│   ├── devops-engineer.md
│   ├── economy-designer.md
│   ├── engine-programmer.md
│   ├── game-designer.md
│   ├── gameplay-programmer.md
│   ├── godot-csharp-specialist.md
│   ├── godot-gdextension-specialist.md
│   ├── godot-gdscript-specialist.md
│   ├── godot-shader-specialist.md
│   ├── godot-specialist.md
│   ├── lead-programmer.md
│   ├── level-designer.md
│   ├── live-ops-designer.md
│   ├── localization-lead.md
│   ├── narrative-director.md
│   ├── network-programmer.md
│   ├── performance-analyst.md
│   ├── producer.md
│   ├── prototyper.md
│   ├── qa-lead.md
│   ├── qa-tester.md
│   ├── security-engineer.md
│   ├── sound-designer.md
│   ├── systems-designer.md
│   ├── technical-artist.md
│   ├── technical-director.md
│   ├── tools-programmer.md
│   ├── ui-programmer.md
│   ├── unity-addressables-specialist.md
│   ├── unity-dots-specialist.md
│   ├── unity-shader-specialist.md
│   ├── unity-specialist.md
│   ├── unity-ui-specialist.md
│   ├── unreal-specialist.md
│   ├── ue-blueprint-specialist.md
│   ├── ue-gas-specialist.md
│   ├── ue-replication-specialist.md
│   ├── ue-umg-specialist.md
│   └── writer.md
├── hooks/                       # 19 Python session hooks
│   ├── hermes_yaml_helper.py
│   ├── session_start.py
│   ├── session_end.py
│   ├── gate_validator.py
│   ├── contract_checker.py
│   ├── quality_enforcer.py
│   ├── memory_sync.py
│   ├── ntfy_notifier.py
│   ├── provider_health.py
│   ├── session_checkpoint.py
│   ├── skill_state_persist.py
│   ├── agent_dispatch_logger.py
│   ├── cross_boundary_guard.py
│   ├── context_ceiling_monitor.py
│   ├── fallback_monitor.py
│   ├── unstable_provider_pause.py
│   ├── max_continuations_guard.py
│   ├── write_incremental_guard.py
│   └── read_back_verification.py
├── scripts/                     # 39 deterministic helpers
│   ├── hermes-gdd-structure-check.sh
│   ├── hermes-migrate-v1-config.sh
│   ├── hermes-adr-template.sh
│   ├── hermes-sprint-template.sh
│   ├── hermes-release-checklist.sh
│   ├── hermes-blueprint-validate.sh
│   ├── hermes-contract-validate.sh
│   ├── hermes-test-runner.sh
│   ├── hermes-lint-runner.sh
│   ├── hermes-build.sh
│   ├── hermes-deploy.sh
│   ├── hermes-asset-pipeline.sh
│   ├── hermes-localization-extract.sh
│   ├── hermes-changelog-generate.sh
│   ├── hermes-version-bump.sh
│   ├── hermes-git-hooks-install.sh
│   ├── hermes-health-check.sh
│   ├── hermes-clean.sh
│   ├── hermes-backup.sh
│   ├── hermes-restore.sh
│   └── ... (more bash/awk/Python)
├── rules/                       # 5 lint rule configs
│   ├── eslint-index.cjs         # Main ESLint 9 flat config
│   ├── eslint-core-rules.cjs    # Core JS/TS rules
│   ├── eslint-utils.cjs         # Utility functions for rules
│   ├── ruff-rules.toml          # Python Ruff config
│   └── clippy-rules.toml        # Rust Clippy config
├── prompts/                     # 7 structured prompts
│   ├── hermes-architect-prompt.md
│   ├── hermes-implementer-prompt.md
│   ├── hermes-qa-prompt.md
│   ├── hermes-curator-prompt.md
│   ├── hermes-operator-prompt.md
│   ├── hermes-director-panel-prompt.md
│   └── hermes-collaborative-design-prompt.md
├── contracts/                   # 5 frozen sector contracts (YAML)
│   ├── arch-to-impl.yaml        # Nephy → Morgana
│   ├── impl-to-qa.yaml          # Morgana → Debora
│   ├── qa-report.yaml           # Debora → Nephy/Morgana
│   ├── curator-services.yaml    # Alice → All
│   └── ops-services.yaml        # Liruh → All
├── memory/                      # Local persistent state
│   ├── active.md                # Active session state (symlinked to production/session-state/active.md)
│   ├── session-logs/            # Session logs (symlinked to production/session-logs/)
│   └── skill-state/             # Skill state persistence
└── ai-gateway/                  # AI Gateway config (3-tier fallback)
    ├── config.yaml              # Providers: NVIDIA → OpenRouter → Ollama
    ├── fallback-chain.yaml
    └── health-check.yaml
```

---

## `src/` — Code Root (Godot 4 Default)

```
src/
├── autoloads/                   # Global singletons (injected services)
│   ├── logger.gd
│   ├── event_bus.gd
│   ├── config_manager.gd
│   └── service_locator.gd
├── core/                        # Engine-agnostic game logic
│   ├── entities/
│   ├── systems/
│   ├── components/
│   └── resources/
├── gameplay/                    # Game-specific systems
│   ├── player/
│   ├── enemies/
│   ├── combat/
│   ├── inventory/
│   └── progression/
├── ui/                          # User interface
│   ├── hud/
│   ├── menus/
│   └── screens/
├── levels/                      # Level scenes & data
│   ├── level_01/
│   ├── level_02/
│   └── shared/
└── main.gd                      # Entry point
```

### Unity / Unreal Variants (via `project.yaml` engine config)

| Engine | Code Root | Test Root | Assets Root |
|--------|-----------|-----------|-------------|
| Godot 4 | `src/` | `tests/unit/`, `tests/integration/` | `assets/` |
| Unity | `Assets/` (symlink) | `Assets/Tests/EditMode/`, `Assets/Tests/PlayMode/` | `Assets/` |
| Unreal 5 | `Source/<Module>/` (symlink) | `Source/<Module>/Private/Tests/` | `Content/` |

---

## `assets/` — Game Assets

```
assets/
├── art/
│   ├── characters/
│   ├── environments/
│   ├── props/
│   ├── ui/
│   └── effects/
├── audio/
│   ├── music/
│   ├── sfx/
│   └── voice/
├── fonts/
├── shaders/
└── data/
    ├── items.json
    ├── enemies.json
    └── levels.json
```

---

## `design/` — Game Design Documents

```
design/
├── gdd/                         # Game Design Documents
│   ├── core-loop.md
│   ├── mechanics/
│   ├── progression/
│   └── economy/
├── narrative/                   # Story, lore, characters
│   ├── world-bible.md
│   ├── characters/
│   └── dialogue/
├── levels/                      # Level design docs
│   ├── level_01.md
│   └── pacing-curves.md
├── balance/                     # Balance sheets, curves
│   ├── combat-balance.xlsx
│   └── progression-curves.csv
└── registry/                    # Registry files (referenced by contracts)
    ├── design-pillars.md
    ├── mechanic-registry.yaml
    └── asset-registry.yaml
```

---

## `docs/` — Technical Documentation

```
docs/
├── architecture/
│   ├── SECTOR_CONTRACTS.md      # Inter-sector contracts (generated)
│   ├── directory-structure.md   # This file
│   ├── adr-registry.yaml        # Architecture Decision Records
│   ├── system-boundaries.yaml   # Sector ownership map
│   └── engine-architecture.md
├── api/                         # API documentation (empty - generated)
├── engine-reference/            # Engine-specific references
│   ├── godot/
│   │   ├── breaking-changes.md
│   │   ├── current-best-practices.md
│   │   ├── deprecated-apis.md
│   │   ├── modules/
│   │   └── VERSION.md
│   ├── unity/
│   │   ├── breaking-changes.md
│   │   ├── current-best-practices.md
│   │   ├── deprecated-apis.md
│   │   └── modules/
│   └── unreal/
│       ├── breaking-changes.md
│       ├── current-best-practices.md
│       ├── deprecated-apis.md
│       └── modules/
├── postmortems/                 # Incident postmortems (empty - populated per project)
└── registry/                    # Registry documentation
```

---

## `tests/` — Test Suites

```
tests/
├── unit/                        # Unit tests (target: 80% coverage)
│   ├── core/
│   ├── gameplay/
│   ├── systems/
│   └── utils/
├── integration/                 # Integration tests (target: 60% coverage)
│   ├── multiplayer/
│   ├── save-load/
│   └── scene-transitions/
├── contract/                    # Contract compliance tests
│   ├── arch-to-impl.test.yaml
│   ├── impl-to-qa.test.yaml
│   └── qa-report.test.yaml
└── performance/                 # Performance budget tests
    ├── frame-budget.test.ts
    └── memory-budget.test.ts
```

---

## `prototypes/` — Throwaway Prototypes (Gitignored)

```
prototypes/
├── combat-v1/
├── inventory-v2/
├── multiplayer-test/
└── procedural-generation/
```

---

## `production/` — Production Management

```
production/
├── session-state/
│   └── active.md                # Symlinked to .hermes/memory/active.md
├── session-logs/                # Symlinked to .hermes/memory/session-logs/
│   ├── 2026-11-09-session-1.md
│   └── ...
├── sprints/
│   ├── sprint-01-plan.md
│   ├── sprint-01-status.md
│   └── sprint-01-retrospective.md
├── milestones/
│   ├── milestone-alpha.md
│   ├── milestone-beta.md
│   └── milestone-1.0.md
├── releases/
│   ├── release-checklist.md
│   ├── v0.1.0-changelog.md
│   └── deploy-log.md
└── risks/
    ├── risk-register.md
    └── mitigation-plans.md
```

---

## `studio-tests/` — QA for Skills/Agents (Template Infrastructure)

```
studio-tests/
├── README.md                    # How to use /skill-test & /skill-improve
├── CLAUDE.md                    # Instructions for Claude (legacy)
├── catalog.yaml                 # Master registry: 74 skills + 49 agents
├── quality-rubric.md            # Category-specific pass/fail metrics
├── skills/                      # Behavioral specs for 74 skills
│   ├── gate/
│   ├── review/
│   ├── authoring/
│   ├── readiness/
│   ├── pipeline/
│   ├── analysis/
│   ├── team/
│   ├── sprint/
│   └── utility/
├── agents/                      # Behavioral specs for 49 agents
│   ├── directors/
│   ├── leads/
│   ├── specialists/
│   ├── engine/
│   │   ├── godot/
│   │   ├── unity/
│   │   └── unreal/
│   ├── operations/
│   └── qa/
├── templates/
│   ├── skill-test-spec.md
│   └── agent-test-spec.md
└── results/                     # Test run outputs (gitignored)
```

---

## `scripts/` — Build/Pipeline Scripts

```
scripts/
├── hermes-gdd-structure-check.sh
├── hermes-migrate-v1-config.sh
├── hermes-adr-template.sh
├── hermes-sprint-template.sh
├── hermes-release-checklist.sh
├── hermes-blueprint-validate.sh
├── hermes-contract-validate.sh
├── hermes-test-runner.sh
├── hermes-lint-runner.sh
├── hermes-build.sh
├── hermes-deploy.sh
├── hermes-asset-pipeline.sh
├── hermes-localization-extract.sh
├── hermes-changelog-generate.sh
├── hermes-version-bump.sh
├── hermes-git-hooks-install.sh
├── hermes-health-check.sh
├── hermes-clean.sh
├── hermes-backup.sh
├── hermes-restore.sh
└── ...
```

---

## `tools/` — Custom Tools

```
tools/
├── hermes-yaml-helper/          # Rust CLI for YAML operations
├── hermes-graph-viz/            # Python visualization
├── hermes-asset-processor/      # Asset pipeline
└── hermes-localization-tool/    # i18n extraction
```

---

## `.github/` — GitHub Infrastructure

```
.github/
├── CODEOWNERS
├── ISSUE_TEMPLATE/
│   ├── bug_report.md
│   └── feature_request.md
└── workflows/
    └── ci.yml                   # Quality gates + template validation + ntfy
```

---

## Key Principles

1. **Disk artifacts = communication** — contracts, reports, vault files
2. **Sector ownership enforced** — ESLint/Clippy/Ruff rules + boundary checks
3. **Frozen contracts** — only Nephy/Liruh modify; version bump required
4. **Gitignore comprehensive** — local state, engine artifacts, prototypes excluded
5. **Template ≠ Project** — this is the template; user projects inherit `.hermes/` + create their own `src/`, `design/`, `tests/`, etc.