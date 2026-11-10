# /hermes-setup-engine — Section 12: Output Summary

> Part of `/hermes-setup-engine`. `SKILL.md` names when to read this file; the settings it
> resolved and the rules under its later headings still apply here.

## 12. Output Summary

After setup is complete, output:

```
Engine Setup Complete
=====================
Engine:          [name] [version]
Language:        [GDScript | C# | GDScript + C# | C# | C++ + Blueprint | Blueprint + C++]
Knowledge Risk:  [LOW/MEDIUM/HIGH]
Reference Docs:  [created/skipped]
CLAUDE.md:       [updated]
Tech Prefs:      [created/updated]
project.yaml:    [created/updated]
Agent Config:    [verified]

Next Steps:
1. Review docs/engine-reference/<engine>/VERSION.md
```

Then print **one** Next-Steps list, matching the resolved `workflow` tier:

**`minimal` — the lean 4-step floor (you are on step 1):**
```
2. Run /hermes-brainstorm to produce your one-page design/game-brief.md (the lean-tier design artifact)
3. Run /hermes-create-stories to turn the brief's MVP list into stories
4. Run /hermes-dev-story — first line of game code
```
(No `/hermes-map-systems`, `/hermes-design-system`, `/prototype`, or `/hermes-sprint-plan` at
`minimal` — the brief replaces the GDDs and its build order is the plan.)

**`standard` / `full` — the full pipeline:**
```
2. [If from /hermes-brainstorm] Run /hermes-map-systems to decompose your concept into individual systems
3. [If from /hermes-brainstorm] Run /hermes-design-system to author per-system GDDs (guided, section-by-section)
4. [If from /hermes-brainstorm] Run /prototype [core-mechanic] to validate the core idea before writing GDDs
5. [If fresh start] Run /hermes-brainstorm to discover your game concept
6. Create your first milestone: /hermes-sprint-plan new
```

---

Verdict: **COMPLETE** — engine configured and reference docs populated.
