# AGENTS.md — Hermes Game Studios Agent Registry

**Auto-generated from HERMES.md** — Single source of truth for cross-tool agent definitions.
**Total Agents:** 49 (1:1 mapping from CCGS)

---

## Director Tier 1 (Architecture Model / opus-equivalent)

| Agent | Role | Sector | Model Tier | Description |
|-------|------|--------|------------|-------------|
| `creative-director` | Creative Director | Nephy (Arquitetura) | architecture | Vision, pillars, GDD alignment, narrative coherence, phase gates |
| `technical-director` | Technical Director | Nephy (Arquitetura) | architecture | Architecture, ADRs, system boundaries, feasibility, engine risk |
| `producer` | Producer | Liruh (Operação) | architecture | Scope, sprints, milestones, release, cross-dept coordination, risk |
| `art-director` | Art Director | Nephy (Arquitetura) | architecture | Visual direction, art bible, concept approval, visual phase gates |
| `audio-director` | Audio Director | Nephy (Arquitetura) | architecture | Audio direction, music/sfx strategy, audio phase gates |
| `narrative-director` | Narrative Director | Nephy (Arquitetura) | architecture | Story, lore, characters, dialogue, narrative consistency |

---

## Lead Tier (Implementation or Inherit Model)

| Agent | Role | Sector | Model Tier | Description |
|-------|------|--------|------------|-------------|
| `game-designer` | Lead Game Designer | Nephy (Arquitetura) | inherit | Core mechanics, systems design, progression, economy |
| `lead-programmer` | Lead Programmer | Morgana (Implementação) | sonnet | Technical leadership, code review, architecture compliance |
| `qa-lead` | QA Lead | Debora (Qualidade) | inherit | Test strategy, story readiness, test coverage gates |
| `level-designer` | Level Designer | Nephy (Arquitetura) | inherit | Level design documents, pacing, encounter design |
| `systems-designer` | Systems Designer | Nephy (Arquitetura) | inherit | Game systems, mechanics interaction, balance frameworks |
| `economy-designer` | Economy Designer | Liruh (Operação) | inherit | Economy models, progression curves, live ops balance |
| `localization-lead` | Localization Lead | Liruh (Operação) | inherit | Localization strategy, i18n pipeline, cultural adaptation |
| `live-ops-designer` | Live Ops Designer | Liruh (Operação) | inherit | Live events, seasonal content, retention mechanics |

---

## Specialist Tier (Implementation Model / sonnet-equivalent or Inherit)

### Engine Specialists (Morgana - Implementação)

| Agent | Role | Engine | Model Tier |
|-------|------|--------|------------|
| `godot-specialist` | Godot Engine Lead | Godot | inherit |
| `godot-gdscript-specialist` | Godot GDScript Sub | Godot | sonnet |
| `godot-csharp-specialist` | Godot C# Sub | Godot | sonnet |
| `godot-shader-specialist` | Godot Shader Sub | Godot | sonnet |
| `godot-gdextension-specialist` | Godot GDExtension Sub | Godot | sonnet |
| `unity-specialist` | Unity Engine Lead | Unity | inherit |
| `unity-ui-specialist` | Unity UI Sub | Unity | sonnet |
| `unity-shader-specialist` | Unity Shader Sub | Unity | sonnet |
| `unity-dots-specialist` | Unity DOTS/ECS Sub | Unity | sonnet |
| `unity-addressables-specialist` | Unity Addressables Sub | Unity | sonnet |
| `unreal-specialist` | Unreal Engine Lead | Unreal | inherit |
| `ue-blueprint-specialist` | Unreal Blueprint Sub | Unreal | sonnet |
| `ue-gas-specialist` | Unreal GAS Sub | Unreal | sonnet |
| `ue-replication-specialist` | Unreal Replication Sub | Unreal | sonnet |
| `ue-umg-specialist` | Unreal UMG Sub | Unreal | sonnet |

### Gameplay & Systems Programmers (Morgana - Implementação)

| Agent | Role | Model Tier |
|-------|------|------------|
| `gameplay-programmer` | Gameplay Programmer | inherit |
| `engine-programmer` | Engine Programmer | inherit |
| `ai-programmer` | AI Programmer | sonnet |
| `network-programmer` | Network Programmer | inherit |
| `tools-programmer` | Tools Programmer | inherit |
| `ui-programmer` | UI Programmer | inherit |
| `technical-artist` | Technical Artist | inherit |
| `sound-designer` | Sound Designer | inherit |

### QA & Operations (Debora/Liruh)

| Agent | Role | Sector | Model Tier |
|-------|------|--------|------------|
| `qa-tester` | QA Tester | Debora (Qualidade) | inherit |
| `performance-analyst` | Performance Analyst | Debora (Qualidade) | inherit |
| `security-engineer` | Security Engineer | Debora (Qualidade) | inherit |
| `accessibility-specialist` | Accessibility Specialist | Debora (Qualidade) | inherit |
| `devops-engineer` | DevOps Engineer | Liruh (Operação) | sonnet |
| `analytics-engineer` | Analytics Engineer | Liruh (Operação) | inherit |
| `community-manager` | Community Manager | Liruh (Operação) | sonnet |

### Creative & Content (Nephy - Arquitetura)

| Agent | Role | Model Tier |
|-------|------|------------|
| `writer` | Writer | inherit |
| `world-builder` | World Builder | inherit |
| `ux-designer` | UX Designer | inherit |

### Specialized Roles

| Agent | Role | Sector | Model Tier |
|-------|------|--------|------------|
| `prototyper` | Prototyper | Morgana (Implementação) | sonnet |
| `release-manager` | Release Manager | Liruh (Operação) | inherit |

---

## Dispatch Protocol

**ALL agents are dispatched via `delegate_task` with `role: "leaf"`**

```json
{
  "tasks": [
    {
      "role": "leaf",
      "goal": "<specific goal for this agent>",
      "context": {
        "agent_name": "<agent-name>",
        "sector": "<nephy|morgana|debora|alice|liruh>",
        "model_tier": "<architecture|implementation|inherit>",
        "contracts": [".hermes/contracts/arch-to-impl.yaml"],
        "boundaries": {
          "owns": ["src/**/*.gd", "tests/**/*"],
          "readonly": ["docs/architecture/**", "design/gdd/**"],
          "forbidden": ["HERMES.md", "project.yaml", ".hermes/agents/**"]
        },
        "acceptance_criteria": [...],
        "dna": "Write incrementally. Read-back verify. Surgical context. Move never delete. Terminate own processes. Context ceiling 2. Unstable provider pause. Fallback model native."
      },
      "model_tier": "<architecture|implementation|inherit>"
    }
  ]
}
```

---

## Agent File Locations

Each agent has a definition file in `.hermes/agents/`:
- `.hermes/agents/creative-director.md`
- `.hermes/agents/technical-director.md`
- `.hermes/agents/producer.md`
- ... (all 49 agents)

Each file contains:
1. Agent identity (name, role, sector, model_tier)
2. DNA block (universal dispatch rules)
3. Sector contract references
4. Boundary definitions (owns/readonly/forbidden)
5. Acceptance criteria templates
6. Gate definitions (for directors)

---

## Model Tier Resolution

```yaml
# In project.yaml
model_tiers:
  architecture: "nvidia/nemotron-3-ultra"    # opus-equivalent
  implementation: "nvidia/nemotron-3-ultra"  # sonnet-equivalent  
  inherit: "nvidia/nemotron-3-ultra"         # session parent
```

---

## Cross-Tool Compatibility

This registry is the canonical source for:
- Hermes native (`delegate_task`)
- Claude Code (`--agent` flag)
- Any tool supporting agent definitions

**Keep in sync with HERMES.md** — both auto-generated from blueprint.