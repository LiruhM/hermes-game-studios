# Contributing to Hermes Game Studios

Thank you for your interest in contributing! This template is a native Hermes (Nous Research) adaptation of the Claude Code Game Studios framework, designed for local, free, multi-provider game development.

## Ways to Contribute

### 🐛 Bug Reports
- Use the GitHub issue template
- Include Hermes version, OS, engine (Godot/Unity/Unreal)
- Provide minimal reproduction steps

### ✨ Feature Requests
- Open a discussion first for major changes
- Explain the use case and expected behavior
- Consider if it fits the "free-only, local-first" philosophy

### 📝 Documentation
- Fix typos, clarify unclear sections
- Add examples for skills/agents/hooks
- Translate to other languages

### 🔧 Code Contributions
- Skills: Add to `.hermes/skills/` following existing patterns
- Agents: Define in `.hermes/agents/` with DNA block + dispatch contracts
- Hooks: Python scripts in `.hermes/hooks/`
- Scripts: Deterministic helpers in `.hermes/scripts/`
- Rules: Lint configs in `.hermes/rules/`

## Development Setup

```bash
# Clone
git clone https://github.com/hermes-game-studios/hermes-game-studios.git
cd hermes-game-studios

# Install quality gates
npm install
pip install ruff
rustup component add clippy

# Run validation
npm run lint
ruff check .
cargo clippy

# Test template
/hermes:start
/hermes:project-stage-detect
/hermes:setup-engine
/hermes:gate-check
```

## Code Style

- **Python**: Ruff (line-length 120, complexity 10)
- **JavaScript/TypeScript**: ESLint flat config (max-lines 350, no-direct-console)
- **Rust**: Clippy (workspace lints)
- **Commits**: Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`)

## Skill/Agent Guidelines

- Follow the **Collaborative Design Principle**: User = Creative Director, Agent = Expert Consultant
- Every skill must have: `---` frontmatter, `# Purpose`, `## Steps`, references to `.hermes/docs/`
- Every agent must have: DNA block, boundaries, dispatch contract (JSON schema), gate mapping
- Free-only providers only — no paid API dependencies

## Pull Request Process

1. Fork and create a feature branch
2. Make changes with clear, atomic commits
3. Run all quality gates (`npm run lint && ruff check . && cargo clippy`)
4. Update documentation if needed
5. Open PR with description of changes and testing done
6. Address review feedback
7. Squash and merge (maintainers)

## Community

- GitHub Issues: Bug reports, feature requests
- GitHub Discussions: Questions, ideas, showcase projects
- Hermes Discord/Telegram: Real-time chat (links in repo)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.