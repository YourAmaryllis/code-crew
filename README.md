# code-crew — Virtual AI Development Team

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)
[![Commercial license](https://img.shields.io/badge/License-Commercial-green.svg)](COMMERCIAL.md)

CrewAI-based multi-agent crew for the full software development lifecycle. Agents cover sprint planning, architecture, BDD, backend/frontend engineering, code review, security (OWASP + OTM threat modeling), compliance, and Definition of Done — driven by Jira, Linear, or GitHub Issues tickets and your own knowledge base (ADRs, ADDs, SOPs in OKF format).

## Slash commands (REPL)

| Command | What it does |
|---------|-------------|
| `/design <KEY>` | **Pre-implementation**: architect + security + compliance → creates ADD/ADR in designs/ |
| `/ux <KEY>` | **UX**: Figma frame → component spec + tokens → engineer implements → UX Lead reviews (loop) |
| `/issue <KEY>` | **Implementation**: full SDLC crew from sprint planning → DoD → staging |
| `/sprint <name>` | Run all tickets in a sprint (parallel where safe) |
| `/explore [path]` | Scan project, detect stacks, generate OTM threat model skeleton |
| `/verify` | Full codebase audit: arch · security · compliance · domain → `.code-crew/verify-report-YYYYMMDD.md` + optional Jira issue creation |
| `/domain design <KEY>` | **Domain modeling**: event storming (3-phase async) → bounded contexts, aggregates, glossary, Mermaid diagram → `designs/DMD/` |
| `/domain extract [path]` | Reverse-engineer domain model from existing code → `designs/DMD/` |
| `/mcp list\|connect\|disconnect\|status` | Manage MCP server connections (Figma, Linear, GitHub, …) |
| `/skills` | List available and active skills |
| `/skill install <url\|user/repo>` | Install skill(s) from a GitHub repo or raw URL |
| `/skill <name>` | Activate a skill (`terse`, `strict`, `explain`, `dry-run`) |
| `/skill off [name]` | Deactivate one or all skills |
| `/init` | Scaffold `.code-crew/config.yaml`, then auto-detect migration tool, test framework, API doc standard, and architecture style |
| `/status` | Show active runs |
| `/profile <name>` | Switch config profile live |
| `/fix` | Install missing tools |
| `/help <msg>` | Inject guidance into a stuck flow |
| `/context [KEY]` | Show agent Q&A log; export decisions |
| `/history` | List past runs this session |

## Quick start

```bash
# 1. Install
pip install -e .

# 2. Configure global settings (LLM, issue tracker, designs repo)
cp .config.example.yaml ~/.code-crew/config.yaml
# Edit: bedrock.model_id, bedrock.region, issue_tracker, designs.repo

# 3. Add designs/ as a submodule in your platform repo (preferred)
cd /path/to/your-platform-repo
git submodule add git@github.com:your-org/designs.git designs
# code-crew auto-detects ./designs/ when run from the platform repo root

# 4. Initialise the project (run from your platform repo root)
code-crew     # start the REPL
/init         # scaffolds .code-crew/config.yaml + auto-detects project settings

# 5. Run
/explore      # scan project, detect stacks, generate OTM skeleton
/design PROJ-123     # create design docs first
/issue PROJ-123      # then implement
```

## `/init` — project scaffolding

Run `/init` once per project (from the platform repo root). It:

1. Runs `git init` if the directory is not already a git repo
2. Prompts for project name, issue tracker (`jira`/`linear`/`github`), and project key
3. Writes `.code-crew/config.yaml` with those answers
4. Scans the project and appends `# Auto-detected by /init` values:

| Signal | Config key written |
|--------|-------------------|
| `alembic.ini` | `db.migration_tool: alembic` |
| `-- +goose` header in `.sql` files | `db.migration_tool: goose` |
| `atlas.hcl` or `atlas.sum` | `db.migration_tool: atlas` |
| `migrations/` directory | `db.schema_path: migrations/` |
| `pytest.ini` or `[tool.pytest]` in `pyproject.toml` | `testing.framework: pytest` |
| `jest.config.*` | `testing.framework: jest` |
| `go.mod` (no other test framework found) | `testing.framework: go-test` |
| `*.feature` files | `testing.bdd: true` |
| `docs/swagger.json` or `openapi.yaml` | `api.doc_standard: openapi` |
| `ports/` + `driving/` or `driven/` dirs | `architecture.style: hexagonal` |
| `domain/model/` + `application/` dirs | `architecture.style: onion` |
| `usecases/` or `domain/` + `adapters/` dirs | `architecture.style: clean` |

5. Creates a minimal `.gitignore` (if absent) including `.code-crew/structure.md`

**Resulting `.code-crew/config.yaml` example** (Go project with goose + go-test):

```yaml
project: my-platform
issue_tracker:
  type: jira
  project_key: PROJ

# Auto-detected by /init
db:
  migration_tool: goose
  schema_path: migrations/
testing:
  framework: go-test
architecture:
  style: clean
```

Re-running `/init` is safe — it skips existing files and only appends the auto-detected block once.

## Agents

| Agent | Phases | Model tier |
|-------|--------|-----------|
| Scrum Master | Sprint planning, DoD gate | standard |
| Architect | Architecture review, code review, design | powerful |
| Engineer | BDD scaffold, implementation | standard |
| QA Lead | BDD authoring, staging verification | standard |
| Security Lead | OWASP, threat modeling (OTM), SBOM | powerful |
| Compliance Officer | HIPAA, SOC2, GDPR, CCPA review | powerful |
| Product Owner | BDD sign-off | standard |
| DevOps Lead | CI/CD, infra coordination | standard |
| Release Engineer | Release notes, launch go/no-go | standard |
| UX Lead | Figma spec extraction, component review, WCAG 2.1 AA | standard |

## Issue tracker support

Configured via `issue_tracker.type` in `~/.code-crew/config.yaml`:

| Tracker | Auth | CLI |
|---------|------|-----|
| `jira` | API token | `brew install jira-cli` |
| `linear` | CLI auth | `npm i -g @linear/linear` |
| `github` | gh auth | `brew install gh` |

## Designs repo

The crew loads SOPs, ADDs, and ADRs from `designs/`. Threat models go in `designs/TMD/` as OTM YAML files (OpenThreatModel v0.2.0).

**Preferred:** `designs/` as a git submodule in your platform repo — design doc changes appear in `git diff` alongside code.

**Alternative:** set `designs.repo` in config — auto-cloned to `~/.code-crew/repos/designs/`.

Run `/explore` to auto-detect stacks and generate a starter OTM threat model at `designs/TMD/<project>.yaml`.

## Configuration

Config lives at `~/.code-crew/config.yaml` (see `.config.example.yaml`):

```yaml
bedrock:
  model_id: us.anthropic.claude-sonnet-4-6-...
  region: us-east-1

designs:
  repo: git@github.com:your-org/designs.git

issue_tracker:
  type: jira
  project_key: PROJ
  jira:
    url: https://yourorg.atlassian.net
    token: your-token
```

Named profiles: `~/.code-crew/profiles/<name>.yaml` — switch with `/profile <name>`.

## MCP servers

Agents can use tools from any MCP-compatible server. Config: `~/.code-crew/mcp.yaml` (see `.mcp.example.yaml`).

```yaml
servers:
  figma:
    command: npx @figma/mcp-server
    env:
      FIGMA_TOKEN: ${FIGMA_TOKEN}
    agents: [ux_lead]          # omit to make available to all agents
  linear:
    command: npx @linear/linear-mcp-server
    agents: [architect, scrum_master]
```

```
/mcp list                 — show configured servers
/mcp connect figma        — start server, inject its tools into agents
/mcp disconnect figma     — stop server
/mcp status               — show active connections
```

Tools from connected servers are automatically injected into the agents listed under `agents:` (or all agents if omitted) for any crew run started after `/mcp connect`.

## Skills

Skills modify agent output style and rigor for the current session. Activate before running a flow.

| Skill | Effect |
|-------|--------|
| `terse` | Verdict first, bullet findings, no filler, no compliments |
| `strict` | OWASP ASVS L3, explicit evidence per gate item, no rubber-stamping |
| `explain` | Every decision includes WHY + alternatives considered |
| `dry-run` | `WOULD RUN`/`WOULD WRITE` preview — no side effects |

```
/skill install juliusbrussee/caveman   — install from GitHub
/skill install https://github.com/...  — full URL also works
/skills                                — list available + active
/skill terse                           — activate
/skill off terse                       — deactivate one
/skill off                             — clear all
```

Multiple skills can be active simultaneously. Skills are injected at the top of every task context.

## Tech stack auto-detection

`/explore` detects: `go-backend`, `typescript-react`, `python`, `terraform`, `terraform-aws`, `ecs-deployment`, `ai-ml`, `bdd-testing`.

Override with `stacks:` in config or `CODE_CREW_STACKS` env var.

## Architecture patterns

`/explore` detects the project's architecture pattern from directory structure and injects it into every task context so engineer and architect agents follow the right layer rules.

| Pattern | Config value | Detection signal | Knowledge doc |
|---------|-------------|-----------------|---------------|
| Clean Architecture | `clean` | `usecases/` or `domain/` + `adapters/` dirs | `stacks/arch-clean.md` |
| Hexagonal (Ports & Adapters) | `hexagonal` | `ports/` with `driving/` or `driven/` subdirs | `stacks/arch-hexagonal.md` |
| Onion | `onion` | `domain/model/` + `application/` dirs | `stacks/arch-onion.md` |

Set explicitly if not auto-detected:

```yaml
# ~/.code-crew/config.yaml
architecture:
  style: hexagonal   # clean | hexagonal | onion
```

Or per-session: `ARCHITECTURE_STYLE=clean code-crew`

## DB schema management

Agents generate migration files; they never apply them. Applying is a human + CI step.

| Stack | Tool | Detection signal |
|-------|------|-----------------|
| `python` | alembic | `alembic.ini` at repo root |
| `go-backend` | goose | `-- +goose` header in `.sql` files |
| any | atlas | `atlas.hcl` or `atlas.sum` |

`/explore` auto-detects the tool and writes it to `.code-crew/structure.md`. Override with `db.migration_tool` in config.

See `functions/db-schema.md` for naming conventions, the no-edit-applied-migrations rule, and the schema review checklist.

## API standards

All stacks produce and maintain an OpenAPI 3.1 spec committed alongside code. The `api_spec` tool lets the engineer verify no drift before declaring implementation complete.

| Stack | Generation | Spec file |
|-------|-----------|-----------|
| Go | `swag init -g cmd/server/main.go -o docs/` | `docs/swagger.json` |
| Python (FastAPI) | `python -m scripts.export_openapi` | `docs/openapi.json` |
| TypeScript client | `npm run gen:api` (openapi-typescript) | `src/api/schema.d.ts` |

See `functions/api-standards.md` for URL conventions, error schema, pagination, auth headers, and versioning policy.

## Domain modeling

`/domain design <KEY>` runs an async, three-phase domain modeling session facilitated by the Architect agent.

**Phases:**
1. **Flow Discovery** — the architect asks the SME (you) 3–5 questions per round to identify distinct business flows and classify them (core/supporting/generic)
2. **Per-flow Event Storming** — for each flow: events → commands → actors → aggregates → policies → hot spots
3. **Synthesis** — reads all event boards, identifies bounded contexts, defines aggregates and invariants, builds ubiquitous language glossary, outputs Mermaid class diagram

**Output files** in `designs/DMD/`:
- `<system>-domain.md` — bounded context map, aggregate definitions, ubiquitous language table
- `<system>-diagram.mmd` — Mermaid class diagram (raw syntax, import into any Mermaid renderer)

**SME batching:** questions arrive in rounds of 3–5, each ending with `AWAITING SME RESPONSE`. You reply in the REPL prompt.

**Methodology** (default: `event-storming`; set in config or `DOMAIN_METHODOLOGY` env var):
- `event-storming` — three-phase collaborative, async; best for complex or poorly-understood domains
- `ddd` — single top-down architect-led session; best for well-understood greenfield domains
- `c4` — system context + container diagrams; best for documenting boundaries and integrations

**Drift check:** `/verify` includes a domain scan — compares `designs/DMD/` against code entities and flags `FINDING [DOMAIN]` for aggregates or events that exist in the model but not in code (or vice-versa).

**Extract from existing code:**
```
/domain extract              — scan cwd
/domain extract ./services/orders   — scan a specific path
```

```yaml
# ~/.code-crew/config.yaml
domain:
  methodology: event-storming   # event-storming | ddd | c4
  diagram_format: mermaid       # mermaid (only supported value)
```

## LLM backends

By default code-crew uses Amazon Bedrock (IAM auth, no API keys). Add an `llm:` section to your config to mix providers across tiers or per agent.

| Provider | Model string prefix | Install extra | Auth |
|----------|-------------------|---------------|------|
| Amazon Bedrock | `bedrock/` | *(included)* | AWS credentials |
| **NVIDIA Build** | `nvidia/` | `pip install -e ".[openai]"` | `NVIDIA_API_KEY` (`nvapi-…`) |
| Anthropic direct | `anthropic/` | `pip install -e ".[anthropic]"` | `ANTHROPIC_API_KEY` |
| OpenAI | `openai/` | `pip install -e ".[openai]"` | `OPENAI_API_KEY` |
| Groq | `groq/` | `pip install -e ".[groq]"` | `GROQ_API_KEY` |
| Ollama (local) | `ollama/` | `pip install -e ".[ollama]"` | none (`ollama serve`) |

**NVIDIA Build — 80+ free models, no credit card required.** Sign up at [build.nvidia.com](https://build.nvidia.com), generate an API key, then:

```yaml
# ~/.code-crew/config.yaml
nvidia:
  api_key: nvapi-xxxxxxxxxxxxxxxxxxxx   # or set NVIDIA_API_KEY env var

llm:
  default:
    provider: nvidia
    model: meta/llama-3.3-70b-instruct
  tiers:
    fast:
      provider: nvidia
      model: meta/llama-3.1-8b-instruct
    powerful:
      provider: nvidia
      model: nvidia/llama-3.1-nemotron-70b-instruct
```

Free models to try: `meta/llama-3.3-70b-instruct` · `meta/llama-3.1-8b-instruct` · `nvidia/llama-3.1-nemotron-70b-instruct` · `microsoft/phi-3.5-mini-instruct` · `moonshotai/kimi-k2.6`

**Config example — mixed providers:**

```yaml
llm:
  default:
    provider: bedrock
    model: us.anthropic.claude-sonnet-4-6-20251001-v1:0
  tiers:
    fast:
      provider: groq
      model: llama-3.1-8b-instant
    powerful:
      provider: anthropic
      model: claude-opus-4-8-20260101
  agents:
    security_lead:
      provider: openai
      model: gpt-4o
```

Resolution order: **agent override → tier override → default → legacy `bedrock:` env vars**. Existing `bedrock:` configs continue to work with no changes.

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
| [CLAUDE.md](CLAUDE.md) | Setup, config format, key principles, task sequence |
| [docs/code-crew.md](docs/code-crew.md) | Full design: concepts, agents, tasks, tools |
| [.config.example.yaml](.config.example.yaml) | Annotated config template |

## License and contributing

code-crew is open source under **AGPL-3.0**. See [LICENSE](LICENSE).

For commercial use (proprietary products, hosted services) a separate license is
available — see [COMMERCIAL.md](COMMERCIAL.md).

Contributions are welcome. All contributors must sign the [CLA](CLA.md) before their
first PR is merged (automated via CLA Assistant). See [CONTRIBUTORS](CONTRIBUTORS).
