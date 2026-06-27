# code-crew — Design Document

**Status:** Current
**Last updated:** 2026-06-26
**Related:** [ADR-031](../designs/ADR/ADR-031-Virtual-AI-Development-Team-CrewAI-Bedrock.md) · [ADD-044](../designs/ADD/ADD-044-Virtual-AI-Development-Team.md)

---

## What it is

code-crew is a virtual AI development team. It takes a Jira, Linear, or GitHub Issues ticket and runs it through a full SDLC pipeline — sprint planning, architecture review, BDD authoring, implementation, code/security/compliance review, staging, and Definition of Done — using a crew of purpose-built AI agents backed by Amazon Bedrock (or any LiteLLM-compatible provider).

The crew is not a chat assistant. It is a structured pipeline where each agent has a specific role, reads the organisation's own SOPs and ADRs as its operating procedures, and hands off typed output to the next agent. The human initiates a run and reviews the output; agents never push code, apply Terraform, or promote to production.

Five distinct flows are supported:

**Setup commands** (pure Python, no LLM — run these first):

| Command | What it does |
|---------|-------------|
| `/init` | Scaffold `.code-crew/config.yaml`, prompt for issue tracker and project key, then auto-detect migration tool, test framework, API doc standard, and architecture style from file signals |
| `/explore [path]` | Walk the directory tree; detect stacks, architecture pattern, and DB migration tool; write `.code-crew/structure.md` (agents read this as project context); generate OTM threat model skeleton at `designs/TMD/` |

**Agent-backed flows** (LLM calls, managed by `flow.py` / `crew.py`):

| Flow | Command | What it does |
|------|---------|-------------|
| **Ticket** | `/issue <KEY>` or `/sprint <name>` | Full SDLC pipeline: sprint planning → DoD → staging → release decision |
| **Design** | `/design <KEY>` | Pre-implementation: ADD/ADR/TMD stub before any code is written |
| **UX** | `/ux <KEY>` | Figma → component spec → implementation → UX review loop |
| **Domain** | `/domain design <KEY>` | Async event storming (3-phase): flow discovery → per-flow storming → synthesis → `designs/DMD/` |
| **Verify** | `/verify` | Full codebase audit: arch · security · compliance · domain drift |

Typical first-run order: `/init` → `/explore` → `/design <KEY>` → `/issue <KEY>`.

---

## Core concepts

### Multi-agent crew, not a single LLM

Each agent is an independent LLM call with its own role, goal, backstory, tool set, and model tier. Agents share only the typed output of upstream tasks via structured context — the security reviewer reads the implementation summary, not the full agent conversation.

### Prompts as documents, not strings

Every agent instruction and task description lives in an OKF markdown file under `code_crew/knowledge/`. Python code never contains a prompt. Changing agent behaviour is a markdown edit — reviewable in git, readable by domain experts without touching Python.

### Organisation's own knowledge base

Agents load the organisation's ADRs, ADDs, SOPs, and function guides at runtime from the `designs/` repo. The tool has no embedded best practices — only pointers to the organisation's own standards.

### Human review gate

No merge, no deploy, no Terraform apply without a human. Agents have no git remote credentials, no AWS deploy access, and no Jira transition rights.

### Model tiers per agent

Lightweight tasks run on `fast`, implementation agents on `standard`, reviewers on `powerful`. Configured per-agent in the OKF file and resolved at startup from the `bedrock:` or `llm:` config section.

### Skills

Skills are OKF `.md` files that modify agent output style for the current session. Injected at the top of every task context. Examples: `terse` (verdict first), `strict` (OWASP ASVS L3 evidence per item), `dry-run` (preview only). Installed from GitHub with `/skill install <user/repo>`.

---

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│  code-crew CLI  (code_crew/repl.py)                            │
│                                                                │
│  /init    → pure Python setup   /explore → pure Python scan    │
│  /issue → TicketFlow      /design → DesignFlow                 │
│  /ux    → UxFlow          /domain → DomainFlow                 │
│                           /verify → build_verify_crew()        │
└───────────────────────────┬────────────────────────────────────┘
                            │
          ┌─────────────────▼─────────────────┐
          │  build_*_crew() / build_*_task()  │
          │  (code_crew/crew.py)              │
          │                                   │
          │  Crew ── Task ── Agent ── LLM     │
          │                      │            │
          │                    Tools          │
          └───────────────────────────────────┘
                            │
          ┌─────────────────┼──────────────────┐
          │                 │                  │
    knowledge_reader  workspace_reader   platform_shell
    (designs repo)    (platform codebase) (git, go, grep)
```

### Key components

| Component | Path | Purpose |
|-----------|------|---------|
| REPL | `code_crew/repl.py` | Interactive terminal UI (prompt_toolkit + Rich). Dispatches all slash commands, manages profile loading, streams flow status. |
| Flows | `code_crew/flow.py` | `TicketFlow`, `DesignFlow`, `UxFlow`, `DomainFlow` — manage multi-task loops with retry gates, human escalation, and checkpointing. |
| Crew builder | `code_crew/crew.py` | Builds agents and tasks from OKF files. `build_single_task_crew()`, `build_design_single_task()`, `build_domain_single_task()`, `build_verify_crew()`, `build_domain_extract_crew()`. |
| OKF loader | `shared/okf_loader.py` | Parses OKF markdown into `AgentConcept` / `TaskConcept` structs. |
| LLM factory | `shared/llm_factory.py` | Resolves agent → tier → model. Supports Bedrock, OpenAI, Anthropic, Groq, Ollama via LiteLLM prefix convention. |
| Bedrock shim | `shared/bedrock.py` | Re-exports `get_llm`, `get_fast_llm`, `get_powerful_llm` from `llm_factory.py` for backward compat. |
| Config | `shared/config.py` | Loads structured YAML profiles and project configs into `os.environ`. |
| Telemetry | `shared/telemetry.py` | Installs OTLP TracerProvider pointing at Langfuse. Must run before any crewai import. |
| AWS auth | `shared/aws_auth.py` | Detects expired credential errors and formats actionable `aws sso login` hints. |
| Knowledge | `code_crew/knowledge/` | OKF markdown: `agents/`, `tasks/`, `stacks/`, `functions/`, `skills/`, `prompts/`. |

---

## Flows

### Setup: `/init`

Pure Python — no agents. Run once per project before using any agent-backed flow.

1. `git init` if the directory isn't already a git repo
2. Prompt for project name, issue tracker (`jira` / `linear` / `github`), and project key → write `.code-crew/config.yaml`
3. Write a minimal `.gitignore`
4. Run `_detect_project()` — scans for 12 file signals and appends discovered config under a `# Auto-detected` block:

| Signal | Config key set |
|--------|---------------|
| `alembic.ini` | `db.migration_tool: alembic` |
| `-- +goose` in `.sql` files | `db.migration_tool: goose` |
| `atlas.hcl` / `atlas.sum` | `db.migration_tool: atlas` |
| `pytest.ini` / `conftest.py` | `testing.framework: pytest` |
| `jest.config.*` | `testing.framework: jest` |
| `*_test.go` files | `testing.framework: go-test` |
| `*.feature` files | `testing.bdd: <tool>` |
| `docs/swagger.json` / `openapi.yaml` | `api.doc_standard: openapi` |
| `ports/` + `driving/` or `driven/` dirs | `architecture.style: hexagonal` |
| `domain/model/` + `application/` dirs | `architecture.style: onion` |
| `usecases/` or `domain/` + `adapters/` | `architecture.style: clean` |

`/init` is idempotent — re-running appends the auto-detected block only once and never overwrites manual edits.

### Setup: `/explore [path]`

Pure Python — no agents. Run after `/init` and again after significant codebase changes.

1. **Directory tree** — walks up to 4 levels deep, skips `.git`, `vendor`, `node_modules`, etc.; renders tree to console
2. **Stack detection** — file-pattern heuristics → sets `CODE_CREW_STACKS` for the session:
   - `go.mod` → `go-backend`
   - `package.json` with React deps, or `*.tsx` → `typescript-react`
   - `requirements*.txt` or `pyproject.toml` → `python`
   - `*.tf` → `terraform`; contains `"aws"` → also `terraform-aws`
   - `*task-definition*.json` or `*ecs*.tf` → `ecs-deployment`
   - `*.ipynb` or AI/ML packages in requirements → `ai-ml`
   - `*.feature` files → `bdd-testing`
3. **Architecture pattern** — dir name sniffing → sets `ARCHITECTURE_STYLE` for the session
4. **DB migration tool** — file signal sniffing → sets `DB_MIGRATION_TOOL` for the session
5. **Writes `.code-crew/structure.md`** — tree + detected config in YAML; agents read this via `knowledge_reader` to understand project layout without running their own scan
6. **OTM skeleton** — if `designs/` exists, generates `designs/TMD/<project>.yaml` (OTM v0.2.0) with detected service directories as components; skips if the file already exists

### Ticket flow (`/issue <KEY>`, `/sprint <name>`)

Full SDLC for one ticket. Tasks run sequentially with retry gates on each review step.

```
sprint_planning       scrum_master     DoR gate — ACs testable, story sized
architecture_review   architect        Reads ADRs/ADDs, proposes design
scaffold_code         manager→engineer Creates stubs; runs go build
scaffold_test         manager→qa_lead  Creates test stubs matching scaffold
bdd_authoring         manager→qa_lead  Writes Gherkin .feature files
bdd_po_review         product_owner    Validates business language
bdd_arch_review       architect        Validates technical correctness
bdd_finalization      manager→qa_lead  Consolidates BDD feedback (loops until APPROVED)
implementation        manager→engineer Implements against BDD; unit tests inline
devops_coordination   manager→devops   Dockerfile, CI pipeline, migration config
code_review           architect        [gate] REJECTED → retry implementation
security_review       security_lead    [gate] REJECTED → retry implementation
compliance_review     compliance_officer [gate] REJECTED → retry implementation
dod_check             scrum_master     [gate] REJECTED → retry implementation
release_notes         manager→release  Changelog entry + GitHub Release draft
promote_staging       manager→devops   Push rc tag, ECS redeploy staging
staging_verification  manager→qa_lead  BDD smoke on staging (loops on failure)
launch_decision       release_engineer Go/no-go for production (human gate follows)
smoke_test            manager→qa_lead  Read-only smoke on production
```

Review gates retry up to `flow.max_retries` (default 3) before escalating to human via `REPL /help`.

### Design flow (`/design <KEY>`)

Pre-implementation. Produces ADD/ADR/TMD stub. Chief Architect approval loop.

```
design_requirements      architect   Extract requirements and constraints
design_add_draft         architect   Draft ADD (context, decisions, alternatives)
design_security_input    security_lead  Security analysis + TMD stub
design_compliance_input  compliance_officer  Compliance requirements
design_chief_review      architect   Chief Architect reviews via ask_human; loops on REVISION NEEDED
design_finalize          engineer    Commit files, push branch, open PR, update ticket
```

### UX flow (`/ux <KEY>`)

Figma frame → component implementation → UX review loop.

```
ux_spec           ux_lead    Fetch Figma frame + tokens, write spec.md + tokens.json
ux_implementation engineer   Generate component from spec
ux_review         ux_lead    Verify spec match + WCAG 2.1 AA (loops on REVISION NEEDED)
```

### Domain flow (`/domain design <KEY>`)

Async three-phase event storming facilitated by the Architect. Each phase blocks for SME input via `ask_human` (batched 3–5 questions per round, ending with `AWAITING SME RESPONSE`).

```
Phase 1 — domain_flow_discovery  (once)
  Identify 3–7 named business flows, classify as core/supporting/generic.

Phase 2 — domain_event_storming  (once per flow)
  For each flow: events → commands → actors → aggregates → policies → hot spots.
  Output: structured EVENT BOARD per flow.

Phase 3 — domain_synthesis  (once)
  Read all event boards → bounded contexts, aggregate definitions,
  ubiquitous language glossary, Mermaid class diagram.
  Writes: designs/DMD/<system>-domain.md + designs/DMD/<system>-diagram.mmd
```

`/domain extract [path]` runs `domain_extract` as a standalone task — scans existing code and produces the same DMD output format by reverse-engineering.

### Verify (`/verify`)

Six-task sequential audit. No retry loops — produces a report with FINDING / PASS / REQUIRED lines.

```
verify_arch_scan        architect             Architecture compliance vs ADRs/ADDs
verify_security_scan    security_lead         OWASP + STRIDE + compliance stacks
verify_compliance_scan  compliance_officer    Regulatory evidence gaps
verify_domain_scan      architect             DMD drift — code entities vs designs/DMD/
verify_chief_review     architect             Aggregates findings; marks REQUIRED / EXEMPT / PASS
verify_report           scrum_master          Writes .code-crew/verify-report-YYYYMMDD.md
```

REQUIRED findings are parsed from the chief review output. REPL prompts to open Jira issues for each.

---

## Agents

| Agent key | Role | Model tier | Primary tasks |
|-----------|------|-----------|---------------|
| `scrum_master` | Scrum Master | fast | sprint_planning, dod_check, verify_report |
| `architect` | Senior Architect | powerful | architecture_review, code_review, domain_*, verify_arch_scan, verify_chief_review |
| `chief_architect` | Chief Architect | N/A — human | design_chief_review (blocks via ask_human; no LLM call) |
| `engineer` | Full-stack Engineer | standard | scaffold_code, implementation, ux_implementation, domain_extract |
| `qa_lead` | QA Lead | standard | scaffold_test, bdd_authoring, bdd_finalization, staging_verification, smoke_test |
| `product_owner` | Product Owner | standard | bdd_po_review |
| `security_lead` | Security Lead | powerful | security_review, verify_security_scan |
| `compliance_officer` | Compliance Officer | standard | compliance_review, verify_compliance_scan |
| `devops_lead` | DevOps Lead | standard | devops_coordination, promote_staging |
| `release_engineer` | Release Engineer | standard | release_notes, launch_decision |
| `ux_lead` | UX Lead | standard | ux_spec, ux_review |

All agents: `max_iter=15`, `verbose=True` (suppressed at display layer).

**Manager–worker tasks** (`Process.hierarchical`): scaffold_code, scaffold_test, bdd_authoring, bdd_finalization, implementation, devops_coordination, release_notes, promote_staging, staging_verification, smoke_test, ux_implementation, domain_extract.

**Sequential tasks** (no manager): all review, planning, and evaluation tasks.

---

## Tools

| Tool | Class | What it does |
|------|-------|-------------|
| `knowledge_reader` | `KnowledgeReaderTool` | Reads OKF docs from the designs repo (ADR, ADD, SDLC functions, stacks) on demand at agent runtime — not pre-loaded. Agents call it with a relative path; it resolves against `DESIGNS_PATH`. |
| `workspace_reader` | `WorkspaceReaderTool` | Read/list/search the project codebase. 200-line file cap, 50-match search cap. No writes. |
| `platform_shell` | `PlatformShellTool` | Sandboxed shell in the project root. Runs git, go, npm, python. No network, no writes outside cwd. |
| `api_spec` | `ApiSpecTool` | Reads OpenAPI 3.1 spec, lists routes, checks drift between spec and source file route annotations. |
| `dod_checker` | `DoDCheckerTool` | Loads and parses the DoD document, returns structured checklist for Scrum Master to evaluate against. |
| `issue_view` | `IssueViewTool` | Fetches a ticket by key (summary, description, ACs, comments, linked issues). Backend determined by `ISSUE_TRACKER` env var — Jira, Linear, or GitHub Issues. |
| `issue_list` | `IssueListTool` | Lists tickets in the current sprint/iteration. Same backend abstraction. |
| `memory_tool` | `MemoryTool` | Read/write crew memory (`code-crew memory add/list`). Persists across runs. |
| `ask_human` / `HumanRelay` | `HumanInputTool` | Thread-safe bridge for async SME input. Used by domain modeling and design chief review. Questions batched 3–5 per round; ends with `AWAITING SME RESPONSE`. |

**Issue tracker backends** (`ISSUE_TRACKER` env var or `issue_tracker.type` in config):

| Backend | Value | Auth |
|---------|-------|------|
| Jira | `jira` | `JIRA_URL`, `JIRA_USER`, `JIRA_TOKEN` |
| Linear | `linear` | `LINEAR_API_KEY` |
| GitHub Issues | `github` | `gh auth login` (GitHub CLI) |

All three backends implement the same `IssueViewTool` / `IssueListTool` interface — agent task files reference `issue_view` / `issue_list` and are unaware of which backend is active.

---

## Knowledge system

### OKF format

All knowledge files use OKF (Open Knowledge Format): YAML frontmatter for structured fields, markdown body for content.

- `agents/<name>.md` — `role`, `goal`, `model` (tier); body → backstory
- `tasks/<name>.md` — `description`, `expected_output`
- `stacks/<name>.md` — activated via `CODE_CREW_STACKS` or `stacks:` in config; injected as context when active
- `functions/<name>.md` — SDLC process guides (BDD, DB schema, API standards, deployment, etc.) loaded via `knowledge_reader`
- `skills/<name>.md` — style modifiers injected at the top of every task context when active

No prompt text lives in Python. Changing agent behaviour is a markdown edit.

### Designs repo (`designs/`)

Agents load documents on demand via `knowledge_reader` at runtime — nothing is pre-loaded into context at startup. `DESIGNS_PATH` tells the tool where to resolve relative paths. If the repo is unavailable, agents continue with a warning and no loaded knowledge.

```
designs/ADR/   Architecture Decision Records
designs/ADD/   Architecture Design Documents
designs/SOP/   Standard Operating Procedures (incl. DoD)
designs/TMD/   OTM threat model files (auto-generated by /explore)
designs/DMD/   Domain model files (generated by /domain design)
```

Preferred setup: `git submodule add <designs-repo> designs` in your platform repo.

### Stacks

Stacks are activated via `stacks:` in project config or `CODE_CREW_STACKS=a,b` env var. Each active stack's `.md` file is prepended to every task context.

Available stacks:

| Stack | What it adds |
|-------|-------------|
| `go-backend` | Go-specific coding standards, module layout, linting rules |
| `typescript-react` | React component patterns, TypeScript strict mode |
| `python` | Python conventions, type hints, ruff/mypy |
| `terraform` / `terraform-aws` | Terraform style, AWS-specific naming |
| `ecs-deployment` | ECS task def format, health check conventions |
| `ai-ml` | OWASP LLM Top 10 + PLOT4ai mandatory coverage; activates PLOT4ai diagrams |
| `bdd-testing` | Gherkin conventions, scenario structure |
| `hipaa` / `gdpr` / `ccpa` | Regulatory compliance requirements |
| `owasp` | OWASP ASVS L2 controls checklist |
| `fips-140-3` | FIPS crypto constraints |
| `soc2` / `nist` | SOC 2 / NIST SP 800-53 controls |
| `arch-clean` / `arch-hexagonal` / `arch-onion` | Architecture layer rules (auto-injected by `/explore`) |

---

## Configuration

All config uses structured YAML. The `env:` flat dict section is deprecated.

### Profile (`~/.code-crew/profiles/<name>.yaml`)

```yaml
bedrock:
  model_id: us.anthropic.claude-sonnet-4-6
  fast_model_id: us.anthropic.claude-haiku-4-5-20251001-v1:0
  powerful_model_id: us.anthropic.claude-opus-4-8-20260101-v1:0
  region: us-west-2
  temperature: "0.2"
  # guardrail_id: abc123
  # guardrail_version: "1"

aws:
  profile: my-aws-profile

issue_tracker:
  type: jira
  project_key: PROJ
  jira:
    url: https://your-org.atlassian.net
    user: you@your-org.com
    # token: <token>  # or set JIRA_TOKEN in env

designs:
  repo: git@github.com:your-org/designs.git
  branch: main

telemetry:
  langfuse_public_key: pk-lf-...
  langfuse_secret_key: sk-lf-...
  langfuse_host: https://us.cloud.langfuse.com
```

### Project config (`.code-crew/config.yaml` in your platform repo)

```yaml
stacks:
  - go-backend
  - typescript-react
  - terraform-aws

architecture:
  style: hexagonal   # clean | hexagonal | onion — overrides /explore detection

db:
  migration_tool: goose   # alembic | goose | atlas
  schema_path: db/migrations

testing:
  framework: pytest   # pytest | jest | go-test
  bdd: behave         # behave | cucumber | godog

api:
  doc_standard: openapi

domain:
  methodology: event-storming   # event-storming | ddd | c4
  diagram_format: mermaid

flow:
  max_retries: 3
```

### Named profiles

Switch at runtime: `/profile <name>` in the REPL. Profiles live in `~/.code-crew/profiles/<name>.yaml`. Switch cleans up the previous profile's env vars before loading the new one.

### Multi-LLM backends

The `llm:` config section (or `LLM_CONFIG` env var) overrides the default Bedrock resolution. Supports:

| Provider key | Endpoint | Auth env var | Install extra |
|---|---|---|---|
| `bedrock` | AWS Bedrock | AWS credentials (IAM) | *(included)* |
| `nvidia` | `https://integrate.api.nvidia.com/v1` | `NVIDIA_API_KEY` | `[openai]` |
| `anthropic` | Anthropic API | `ANTHROPIC_API_KEY` | `[anthropic]` |
| `openai` | OpenAI API | `OPENAI_API_KEY` | `[openai]` |
| `groq` | Groq API | `GROQ_API_KEY` | `[groq]` |
| `ollama` | `localhost:11434` | none | `[ollama]` |

**NVIDIA Build** provides 80+ free models (no credit card) via an OpenAI-compatible API. Sign up at [build.nvidia.com](https://build.nvidia.com) and generate an `nvapi-…` key.

```yaml
# Full NVIDIA free-tier setup
nvidia:
  api_key: nvapi-xxxxxxxxxxxxxxxxxxxx

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

Free NVIDIA models: `meta/llama-3.3-70b-instruct` · `meta/llama-3.1-8b-instruct` · `nvidia/llama-3.1-nemotron-70b-instruct` · `microsoft/phi-3.5-mini-instruct` · `mistralai/mistral-7b-instruct-v0.3` · `moonshotai/kimi-k2.6`

**Mixed-provider example:**

```yaml
llm:
  default:
    provider: bedrock
    model: us.anthropic.claude-sonnet-4-6
  tiers:
    fast:
      provider: nvidia                         # free fast tier
      model: meta/llama-3.1-8b-instruct
    powerful:
      provider: anthropic
      model: claude-opus-4-8-20260101
  agents:
    security_lead:
      provider: nvidia
      model: nvidia/llama-3.1-nemotron-70b-instruct
```

Resolution order: **agent override → tier override → default → legacy `bedrock:` env vars**.

### Environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `BEDROCK_MODEL_ID` | Yes (default) | Standard model (cross-region inference profile ID) |
| `BEDROCK_FAST_MODEL_ID` | No | Fast tier — falls back to standard |
| `BEDROCK_POWERFUL_MODEL_ID` | No | Powerful tier — falls back to standard |
| `BEDROCK_REGION` | Yes (Bedrock) | AWS region |
| `AWS_PROFILE` | No | AWS profile for IAM auth |
| `BEDROCK_GUARDRAIL_ID` | No | Bedrock Guardrails ID |
| `BEDROCK_GUARDRAIL_VERSION` | No | Guardrails version (default: `1`) |
| `LLM_CONFIG` | No | JSON-serialised `llm:` section — set automatically from config |
| `NVIDIA_API_KEY` | No | NVIDIA Build API key (`nvapi-…`) — required when `provider: nvidia` |
| `ISSUE_TRACKER` | No | `jira` (default) \| `linear` \| `github` |
| `PROJECT_KEY` | Yes | Issue tracker project key |
| `JIRA_URL` | Yes | Jira base URL |
| `JIRA_USER` | Yes | Jira user email |
| `JIRA_TOKEN` | Yes | Jira API token |
| `DESIGNS_PATH` | No | Path to designs repo checkout (auto-detected from `./designs/`) |
| `DESIGNS_REPO` | No | Git URL — auto-cloned if `DESIGNS_PATH` missing |
| `DESIGNS_BRANCH` | No | Branch to clone (default: `main`) |
| `DOD_PATH` | No | Override path to DoD document |
| `CODE_CREW_STACKS` | No | Comma-separated active stacks |
| `CODE_CREW_SKILLS` | No | Comma-separated active skills |
| `ARCHITECTURE_STYLE` | No | `clean` \| `hexagonal` \| `onion` |
| `DB_MIGRATION_TOOL` | No | `alembic` \| `goose` \| `atlas` |
| `DB_SCHEMA_PATH` | No | Relative path to migration directory |
| `TESTING_FRAMEWORK` | No | `pytest` \| `jest` \| `go-test` |
| `TESTING_BDD` | No | `behave` \| `cucumber` \| `godog` |
| `API_DOC_STANDARD` | No | `openapi` |
| `DOMAIN_METHODOLOGY` | No | `event-storming` (default) \| `ddd` \| `c4` |
| `DOMAIN_DIAGRAM_FORMAT` | No | `mermaid` (default) |
| `MAX_RETRIES` | No | Review gate retry limit (default: 3) |
| `FIGMA_TOKEN` | No | Figma API token for UX flow |
| `LANGFUSE_PUBLIC_KEY` | No | Langfuse tracing (OTLP) |
| `LANGFUSE_SECRET_KEY` | No | Langfuse tracing (OTLP) |
| `LANGFUSE_HOST` | No | Langfuse host (default: `https://cloud.langfuse.com`) |

---

## Skills

Skills are OKF `.md` files that modify agent output style and rigor. They are injected at the top of every task context when active.

**Search path** (priority order):
1. `.code-crew/skills/` — project-level
2. `~/.code-crew/skills/` — user-level
3. `code_crew/knowledge/skills/` — bundled

**Install from GitHub:**
```
/skill install juliusbrussee/caveman   # installs from github.com/juliusbrussee/caveman
/skill install https://github.com/...  # full URL also works
```

Skills can also activate via `CODE_CREW_SKILLS=name1,name2`.

---

## Architecture patterns

`/explore` detects the project's architecture pattern and injects it as context so agents follow the correct layer rules.

| Pattern | Config value | Detection signal |
|---------|-------------|-----------------|
| Clean Architecture | `clean` | `usecases/` or `domain/` + `adapters/` dirs |
| Hexagonal | `hexagonal` | `ports/` with `driving/` or `driven/` |
| Onion | `onion` | `domain/model/` + `application/` |

When active, the architect and engineer agents are instructed to load the matching `stacks/arch-<style>.md` knowledge doc which details layer rules, allowed dependency directions, and anti-patterns.

---

## Domain modeling

Three-phase async event storming facilitated by the Architect agent. SME input is batched (3–5 questions per round, ending with `AWAITING SME RESPONSE`).

| Phase | Task | Output |
|-------|------|--------|
| 1 — Flow Discovery | `domain_flow_discovery` | Ordered list of named business flows with core/supporting/generic classification |
| 2 — Event Storming | `domain_event_storming` (×N) | EVENT BOARD per flow: events, commands, actors, aggregates, policies, hot spots |
| 3 — Synthesis | `domain_synthesis` | Bounded context map, aggregate definitions, ubiquitous language glossary, Mermaid class diagram |

Output files in `designs/DMD/`:
- `<system>-domain.md` — structured domain model document
- `<system>-diagram.mmd` — raw Mermaid classDiagram (importable into any Mermaid renderer)

`/domain extract [path]` runs `domain_extract` as a standalone task — reverse-engineers the model from existing code.

`/verify` includes `verify_domain_scan` — compares `designs/DMD/` against actual code entities and flags `FINDING [DOMAIN]` for drift.

Methodology is configurable (`domain.methodology` in config or `DOMAIN_METHODOLOGY` env var):
- `event-storming` — three-phase collaborative; best for complex or poorly-understood domains
- `ddd` — single top-down architect session; best for well-understood greenfield domains
- `c4` — system context + container diagrams; best for documenting boundaries and integrations

---

## DB schema management

Agents generate migration files; they never apply them. Applying is a human + CI step.

`/explore` auto-detects the tool from repo signals and writes it to `.code-crew/structure.md`.

| Tool | Detection signal | Stack |
|------|-----------------|-------|
| alembic | `alembic.ini` | python |
| goose | `-- +goose` header in `.sql` files | go-backend |
| atlas | `atlas.hcl` or `atlas.sum` | any |

See `functions/db-schema.md` for naming conventions, the no-edit-applied-migrations rule, and the schema review checklist.

---

## API standards

All stacks maintain an OpenAPI 3.1 spec committed alongside code. The `api_spec` tool (`ApiSpecTool`) is wired to the engineer agent and used during implementation to:
- Read the current spec (`read_spec`)
- List routes defined in the spec (`list_routes`)
- Check for drift between spec routes and source file route annotations (`check_drift`)

`/explore` sets `API_DOC_STANDARD=openapi` when a spec file is detected.

See `functions/api-standards.md` for URL conventions, error schema, pagination, auth headers, and versioning policy.

---

## Observability

Traces are sent to Langfuse via OpenTelemetry OTLP. `setup_langfuse()` in `shared/telemetry.py` must run before any crewai import — enforced by import ordering in `repl.py`'s `main()`.

The REPL banner shows `langfuse ✓` or `langfuse ✗` at startup.

---

## Console verbosity

The REPL suppresses CrewAI's default verbose output (full task descriptions, agent reasoning, tool I/O) to show only:

- Current task name and assigned agent
- Tool call one-liners (name + key arg, no output)
- Task completion tick or failure

Achieved via a `_QuietFormatter` replacing CrewAI's `EventListener.formatter` and monkey-patching `crewai_core.printer.Printer.print` to a no-op.

---

## Checkpointing and resume

`TicketFlow` writes task outputs to `.code-crew/checkpoints/<KEY>.json` after each task. On re-run with the same key, completed tasks are replayed from cache (displayed as `[checkpoint]`) — only incomplete or failed tasks re-run the LLM call.

### How resume works

When `/issue <KEY>` is run and a checkpoint exists, the REPL shows:

```
Checkpoint found for LOOPLAT-92 (5 task(s) complete: sprint_planning, architecture_review, scaffold_code, scaffold_test, bdd_authoring).
Resume? [Y/n]
```

- **Y** (default): replays the 5 completed tasks instantly as `[checkpoint]`, then picks up from the first incomplete task.
- **N**: discards the checkpoint and starts from scratch.

### When checkpoints are cleared

- On normal completion (all tasks pass through to `release_notes`).
- Manually: delete `.code-crew/checkpoints/<KEY>.json`.

### Checkpoint file location

`.code-crew/checkpoints/<KEY>.json` in the platform repo root. The file is gitignored (created by `/explore` / `/init`). Contains a map of `task_name → output_string` for every completed task.

### Resuming after a crash or partial failure

If a task returns `INCOMPLETE` (model error, tool failure, network drop), the checkpoint still holds all previously completed tasks. On next `/issue <KEY>`, the flow resumes from the failed task — you don't lose earlier work. For `bdd_arch_review` or `code_review` gate failures the flow retries automatically up to `max_retries` times; for hard errors (AWS auth expired, NoProgressError) the REPL prints the reason and you re-run after fixing the root cause.

---

## Security constraints

Architectural constraints, not just policy:

- **No API keys in code** — Bedrock auth is IAM only. Keys never appear in OKF files, Python, or env files committed to git.
- **No autonomous deploys** — agents have no AWS deploy credentials, no git push rights, no Jira transition rights.
- **Human gate on production** — `launch_decision` produces a go/no-go, then the flow pauses for a human to trigger `workflow_dispatch` (GHA) or a GitLab manual job. The flow resumes only after `/feedback` in the REPL.
- **Workspace sandbox** — `platform_shell` and `workspace_reader` are scoped to the platform codebase root. Path traversal outside root is rejected.
- **Scaffold gate** — `scaffold_code` checks for existing files before writing; runs `go build` after writing Go files to catch syntax errors.
- **No prompt injection via knowledge docs** — Bedrock Guardrails (`BEDROCK_GUARDRAIL_ID`) can be applied to all completions.
- **`TEST_RESET_ENABLED` must be false/unset in staging and production** — this env var is only for local developer teardown.
