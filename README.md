# code-crew — Virtual AI Development Team

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)
[![Commercial license](https://img.shields.io/badge/License-Commercial-green.svg)](COMMERCIAL.md)

CrewAI-based multi-agent crew for the full software development lifecycle. Agents cover sprint planning, architecture, BDD, backend/frontend engineering, code review, security (OWASP + OTM threat modeling), compliance, and Definition of Done — driven by Jira, Linear, or GitHub Issues tickets and your own knowledge base (ADRs, ADDs, SOPs in OKF format).

## Commands

All commands work two ways — as a direct CLI invocation or as a slash command inside the interactive REPL:

```bash
code-crew issue PROJ-123      # direct
# or start the REPL and type:
/issue PROJ-123
```

| Command | What it does |
|---------|-------------|
| `init` / `/init` | Scaffold `.code-crew/config.yaml` and auto-detect project settings |
| `explore [path]` / `/explore [path]` | Scan project, detect stacks + build/test/lint commands, generate OTM threat model skeleton |
| `issue <KEY>` / `/issue <KEY>` | **Implementation**: full SDLC crew from sprint planning → DoD → staging |
| `sprint <name>` / `/sprint <name>` | Run all tickets in a sprint (parallel where safe) |
| `design <KEY>` / `/design <KEY>` | **Pre-implementation**: architect + security + compliance → creates ADD/ADR in designs/ |
| `audit` / `/audit` | Full codebase audit: arch · security · compliance · domain → `.code-crew/audit-YYYYMMDD-HHMMSS.md` |
| `ask <agent> <question>` / `/ask <agent> <question>` | Ask a specific agent directly (architect, security, engineer, qa, …) |
| `/ux <KEY>` | **UX**: Figma frame → component spec + tokens → engineer implements → UX Lead reviews (loop) |
| `/domain design <KEY>` | **Domain modeling**: event storming (3-phase async) → bounded contexts, aggregates, glossary, Mermaid diagram |
| `/domain extract [path]` | Reverse-engineer domain model from existing code |
| `/mcp list\|connect\|disconnect\|status` | Manage MCP server connections |
| `/skills` | List available and active skills |
| `/skill install <url\|user/repo>` | Install skill(s) from a GitHub repo or raw URL |
| `/skill <name>` | Activate a skill (`terse`, `strict`, `explain`, `dry-run`) |
| `/skill off [name]` | Deactivate one or all skills |
| `/status` | Show active runs |
| `/profile <name>` | Switch config profile live |
| `/session [new\|use\|list]` | Manage conversation sessions — history persists across restarts, resume any past session |
| `/fix` | Install missing tools |
| `/help <msg>` | Inject guidance into a stuck flow |
| `/context [KEY]` | Show agent Q&A log; export decisions |
| `/history` | List past runs this session |

## Quick start

```bash
# 1. Install
pip install -e .

# 2. Configure global settings (LLM, issue tracker)
cp .config.example.yaml ~/.code-crew/config.yaml
# Edit: bedrock.model_id, bedrock.region, issue_tracker

# 3. Add designs/ as a submodule in your platform repo (preferred)
cd /path/to/your-platform-repo
git submodule add git@github.com:your-org/designs.git designs

# 4. Initialise the project (run from your platform repo root)
code-crew init                # scaffolds .code-crew/config.yaml + auto-detects project settings

# 5. Run
code-crew explore             # scan project, detect stacks + build/test/lint commands
code-crew design PROJ-123     # create design docs first
code-crew issue PROJ-123      # then implement
```

## Key principles

- **No hardcoded prompts** — all agent/task instructions are OKF `.md` files in `*/knowledge/`
- **IAM auth only** — Bedrock uses instance profile / AWS_PROFILE, never hardcoded keys
- **Human review gate** — agents never push to main, apply Terraform, or promote to production
- **designs/ in your repo** — design doc changes are visible in your PR diff

## Structure

```
code_crew/
  knowledge/
    agents/         one .md per agent (role, goal, backstory)
    tasks/          one .md per task (description, expected_output)
    functions/      process docs loaded by agents at runtime
    stacks/         tech-stack-specific rules (go-backend, python, ai-ml, …)
    prompts/        standalone LLM prompts (ticket extraction, sprint planning)
shared/
  bedrock.py        LLM factory (model tier → Bedrock model ID)
  config.py         YAML config loader
  issue_tracker.py  Jira / Linear / GitHub Issues abstraction
  tools/            CrewAI tool implementations
ops/                Ops crew (infra, release, monitoring)
tests/
docs/
scripts/            OKF conversion utilities
```

## Documentation

| Doc | What it covers |
|-----|---------------|
| [docs/code-crew.md](docs/code-crew.md) | Full design: concepts, agents, tasks, flows, tools, configuration |
| [.config.example.yaml](.config.example.yaml) | Annotated config template |
| [CLAUDE.md](CLAUDE.md) | Codebase conventions and maintainer notes |

## License and contributing

code-crew is open source under **AGPL-3.0**. See [LICENSE](LICENSE).

For commercial use (proprietary products, hosted services) a separate license is
available — see [COMMERCIAL.md](COMMERCIAL.md).

Contributions are welcome. All contributors must sign the [CLA](CLA.md) before their
first PR is merged (automated via CLA Assistant). See [CONTRIBUTORS](CONTRIBUTORS).
