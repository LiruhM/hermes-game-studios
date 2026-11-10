# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial template release (v0.1.0)
- 74 native Hermes skills (ported from CCGS)
- 49 delegate_task agent roles with DNA blocks
- 19 Python hooks (session lifecycle, validation, utilities)
- 39+ deterministic scripts (bash, awk, Python)
- 5 lint rule configs (ESLint core/utils/index, Ruff, Clippy)
- 7 structured prompts
- 5 frozen sector contracts (YAML)
- Vault PARA integration (186+ files)
- Multi-engine support (Godot 4.3, Unity 2022.3, Unreal 5.4)
- Free-only AI provider stack (NVIDIA Nemotron-3-Ultra + fallbacks)
- Cron job scheduler (8 jobs)
- Hermes AI Gateway config (3-tier fallback chain)
- Health check endpoints (12 service checks)
- NTFy alert integration
- Session persistence & checkpointing
- Quality gates with pre-commit/pre-push hooks

### Changed
- N/A (initial release)

### Deprecated
- N/A (initial release)

### Removed
- N/A (initial release)

### Fixed
- N/A (initial release)

### Security
- No secrets in template — all keys via `.env.example`

## [0.1.0] - 2026-11-09

### Added
- Initial open-source release of Hermes Game Studios template
- MIT License
- CONTRIBUTING.md, SECURITY.md
- GitHub issue templates and CI workflow