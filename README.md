# tools — Virtual AI Development Team

CrewAI-based multi-agent crew for YourAmaryllis's SDLC. Agents cover the full development lifecycle — sprint planning, architecture, BDD, backend, frontend, code review, security, and Definition of Done gate — all driven by Jira tickets and the organisation's own knowledge base (ADRs, ADDs, SDLC docs).

## Documentation

| Doc | What it covers |
|-----|---------------|
| [docs/code-crew.md](docs/code-crew.md) | Full design: concepts, architecture, agents, tasks, tools, config, planned crews |
| [docs/comparison-gstack.md](docs/comparison-gstack.md) | How code-crew compares to gstack (Garry Tan's AI dev toolchain) |
| [docs/decision-openclaude.md](docs/decision-openclaude.md) | Why openclaude was evaluated and not adopted |
| [designs/ADR/ADR-031](designs/ADR/ADR-031-Virtual-AI-Development-Team-CrewAI-Bedrock.md) | Decision record: CrewAI + Bedrock + OKF |
| [designs/ADD/ADD-044](designs/ADD/ADD-044-Virtual-AI-Development-Team.md) | Architecture design document |

## Quick start

```bash
# 1. Install
pip install -e .

# 2. Configure
cp .env.example .env
# or use a profile: ~/.code-crew/profiles/<name>.yaml

# 3. Run from the platform directory
cd /path/to/platform
code-crew /jira YOUR-123
```

## Structure

```
code_crew/      # Code crew: feature delivery (sprint planning → DoD)
  knowledge/    #   OKF agent + task definitions — edit to change behaviour
    agents/     #   One .md per agent
    tasks/      #   One .md per task
    prompts/    #   Standalone prompts (Jira extraction, sprint planning)
ops/            # Ops crew: infrastructure, release, monitoring
  knowledge/    #   OKF agent + task definitions
shared/         # OKF loader, Bedrock LLM factory, tools, profile system
tests/          # pytest suite
docs/           # Design docs and decision records
designs/        # Knowledge repo (ADR, ADD, SDLC, SOP) — see DESIGNS_PATH
scripts/        # Utility scripts (OKF conversion, etc.)
```

## Key principles

- **No hardcoded prompts** — all agent and task instructions are OKF markdown files
- **Bring your own knowledge** — SOPs, ADRs, ADDs from your designs repo, loaded at runtime
- **IAM auth only** — Bedrock uses instance profile or AWS_PROFILE, never hardcoded keys
- **Human review gate** — agents never push to main, apply Terraform, or promote to production
