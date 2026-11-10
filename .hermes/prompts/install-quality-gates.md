# Install Quality Gates

> Set up quality gates for a project

## Purpose
Set up quality gates for a project

## Usage
This prompt is invoked by skills/agents when they need a structured approach for this task.

## Context Required
- Project configuration (project.yaml)
- Active contracts (.hermes/contracts/)
- Current session state (.hermes/memory/active.md)

## Steps
1. Load required context
2. Execute structured workflow
3. Produce artifacts in appropriate locations
4. Update session checkpoint

## Output
- Artifacts written to disk per sector contracts
- Updated .hermes/memory/active.md

## Example Invocation
```
Use the install-quality-gates.md prompt to...
```
