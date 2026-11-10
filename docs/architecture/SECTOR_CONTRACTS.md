# Sector Contracts — Hermes Game Studios

> Frozen inter-sector contracts (YAML) — **Contracts are LAW**. Binary validation: PASS / CONCERNS / FAIL.

---

## Contract Files (`.hermes/contracts/`)

| Contract | From → To | Purpose |
|----------|-----------|---------|
| `arch-to-impl.yaml` | Nephy → Morgana | Frozen interfaces, ADRs, system boundaries, engine decisions |
| `impl-to-qa.yaml` | Morgana → Debora | Deliverables, validation requests, test specifications |
| `qa-report.yaml` | Debora → Nephy/Morgana | Verdict, concerns, regression findings |
| `curator-services.yaml` | Alice → All | Vault PARA, MemPalace, Memory-Substrate, Research, Onboarding |
| `ops-services.yaml` | Liruh → All | Sprints, Milestones, Releases, Risk, Cross-dept Coordination |

---

## arch-to-impl.yaml (Nephy → Morgana)

```yaml
contract: arch-to-impl
version: "1.0"
from: nephy
to: morgana
status: frozen
review_mode: lean  # solo | lean | full

interfaces:
  # Engine configuration
  - name: engine.config
    type: yaml
    path: project.yaml
    fields:
      - engine.name
      - engine.version
      - specialists
    validation: required

  # Architecture Decision Records
  - name: adr.registry
    type: yaml
    path: .hermes/architecture/adr-registry.yaml
    fields:
      - id
      - title
      - status
      - decision
      - consequences
    validation: required

  # System boundaries
  - name: system.boundaries
    type: yaml
    path: .hermes/architecture/system-boundaries.yaml
    fields:
      - sector
      - owned_paths
      - forbidden_paths
      - shared_paths
    validation: required

  # Pillars & Design Principles
  - name: design.pillars
    type: markdown
    path: design/registry/design-pillars.md
    validation: required

deliverables:
  - blueprint.yaml
  - architecture-decision.md
  - system-contracts.yaml

gates:
  - name: architecture-review
    required: true
    reviewer: technical-director
  - name: design-review
    required: true
    reviewer: creative-director
```

---

## impl-to-qa.yaml (Morgana → Debora)

```yaml
contract: impl-to-qa
version: "1.0"
from: morgana
to: debora
status: frozen
review_mode: lean

deliverables:
  - name: source-code
    path: src/
    validation:
      - max_lines_per_file: 350
      - no_direct_console: true
      - no_direct_data_access: warn
      - test_coverage: ">=80%"

  - name: unit-tests
    path: tests/unit/
    validation:
      - coverage_minimum: 80
      - naming_convention: "test_*.py / *.test.ts"

  - name: integration-tests
    path: tests/integration/
    validation:
      - coverage_minimum: 60

  - name: build-artifacts
    path: build/
    validation:
      - checksum_verified: true

validation_requests:
  - type: boundary-check
    description: "Morgana never touches Nephy files"
  - type: contract-compliance
    description: "Interfaces match arch-to-impl.yaml"
  - type: performance-budget
    description: "Per-system frame/memory limits"

gates:
  - name: code-review
    required: true
    reviewer: lead-programmer
  - name: qa-gate
    required: true
    reviewer: qa-lead
```

---

## qa-report.yaml (Debora → Nephy/Morgana)

```yaml
contract: qa-report
version: "1.0"
from: debora
to: [nephy, morgana]
status: frozen
review_mode: full

verdicts:
  - PASS        # All gates green, zero concerns
  - CONCERNS    # Functional but concerns documented
  - FAIL        # Blocking issues, must fix before proceed

report_structure:
  - gate_results:
      - gate_name
      - verdict
      - evidence_paths
  - concerns:
      - severity: critical | major | minor
        description
        file_path
        suggested_fix
  - regressions:
      - test_name
      - baseline
      - current
      - delta

gates:
  - name: validation-gate
    required: true
    reviewer: debora
```

---

## curator-services.yaml (Alice → All)

```yaml
contract: curator-services
version: "1.0"
from: alice
to: [nephy, morgana, debora, liruh]
status: frozen
review_mode: lean

services:
  - name: vault-para
    operations:
      - index_project
      - search
      - archive
      - retrieve_context
    sla: "index < 5min, search < 2s"

  - name: mempalace
    operations:
      - store
      - recall
      - traverse
    sla: "recall < 1s"

  - name: memory-substrate
    operations:
      - hybrid_search
      - synthesize
      - traverse_graph
    sla: "query < 2s"

  - name: research
    operations:
      - deep_dive
      - competitor_analysis
      - literature_review
    sla: "report < 30min"

  - name: onboarding
    operations:
      - new_agent_bootstrap
      - skill_library_intro
      - vault_tour
    sla: "ready < 10min"

gates:
  - name: curation-audit
    required: false
    reviewer: alice
```

---

## ops-services.yaml (Liruh → All)

```yaml
contract: ops-services
version: "1.0"
from: liruh
to: [nephy, morgana, debora, alice]
status: frozen
review_mode: lean

services:
  - name: sprint-management
    operations:
      - sprint-plan
      - sprint-status
      - sprint-retrospective
    cadence: "2 weeks"

  - name: milestone-tracking
    operations:
      - create-milestone
      - update-progress
      - risk-assessment
    cadence: "per milestone"

  - name: release-management
    operations:
      - release-checklist
      - version-bump
      - changelog
      - deploy-coordination
    cadence: "per release"

  - name: risk-coordination
    operations:
      - identify-risks
      - mitigation-plan
      - escalation-path
    cadence: "continuous"

  - name: cross-dept-coordination
    operations:
      - dependency-tracking
      - blocker-resolution
      - schedule-alignment
    cadence: "daily standup"

gates:
  - name: milestone-review
    required: true
    reviewer: producer
  - name: release-gate
    required: true
    reviewer: release-manager
```

---

## Validation Rules

1. **Only Nephy or Liruh** may modify contract files (ESLint rule: `hermes/contract-compliance`)
2. **Morgana never touches Nephy files** (boundary enforcement)
3. **All cross-sector communication** via these disk artifacts — no direct calls
4. **Contracts are frozen** — changes require director review + version bump
5. **Binary validation** — PASS / CONCERNS / FAIL only, no "almost ready"