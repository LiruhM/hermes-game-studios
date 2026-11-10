# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

**Do not open public issues for security vulnerabilities.**

Please report security vulnerabilities privately via:

- **Email**: security@hermes-game-studios.example.com (placeholder)
- **GitHub Security Advisories**: Use the "Report a vulnerability" tab

We will acknowledge receipt within 48 hours and provide a timeline for fix.

## Scope

This template includes:
- Skills, agents, hooks, scripts for game development
- Quality gate configurations (ESLint, Ruff, Clippy)
- AI gateway configuration with fallback chain
- Cron job definitions and health check scripts

**Out of scope:**
- User's game project code (separate repository)
- External AI provider APIs (NVIDIA, Groq, Pollinations, etc.)
- Hermes Agent core (upstream: Nous Research)

## Known Considerations

- **No secrets in template**: All API keys use `.env.example` placeholders
- **Free-only providers**: No paid API keys required or stored
- **Local-first**: All processing runs on user's machine
- **Obsidian Vault**: User's PARA vault is local, not synced by template

## Disclosure Timeline

- Day 0: Vulnerability reported
- Day 1-2: Acknowledgment and initial assessment
- Day 7: Preliminary fix or mitigation plan
- Day 30: Target for patch release (if applicable)
- Coordinated disclosure with affected parties

## Contact

For questions about this policy: security@hermes-game-studios.example.com