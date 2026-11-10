# Systematic Debugging

> Structured debugging approach

## Purpose
Structured debugging approach

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
Use the systematic-debugging.md prompt to...
```
