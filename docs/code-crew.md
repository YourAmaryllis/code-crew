# code-crew — Design Document

**Status:** Current
**Last updated:** 2026-06-19
**Related:** [ADR-031](../designs/ADR/ADR-031-Virtual-AI-Development-Team-CrewAI-Bedrock.md) · [ADD-044](../designs/ADD/ADD-044-Virtual-AI-Development-Team.md)

---

## What it is

code-crew is a virtual AI development team for YourAmaryllis. It takes a Jira ticket and runs it through a full SDLC pipeline — sprint planning gate, architecture review, code scaffolding, BDD authoring, backend and frontend implementation, code review, security review, and Definition of Done check — using a crew of purpose-built AI agents backed by Amazon Bedrock.

The crew is not a chat assistant and not a single-agent coding tool. It is a structured pipeline where each agent has a specific role, reads the organisation's own SOPs and ADRs as its operating procedures, and hands off a typed output to the next agent. The human initiates the run and reviews the output; agents never push code, apply Terraform, or promote to production.

---

## Core concepts

### Multi-agent crew, not a single LLM

Each agent is an independent LLM call with its own role, goal, backstory, tool set, and model tier. Agents do not share a conversation — they share only the typed output of upstream tasks via a structured context pass. This means the security reviewer's reasoning is not contaminated by the backend developer's implementation details; it reads only the implementation summary.

### Prompts as documents, not strings

Every agent instruction and task description lives in an OKF markdown file under `*/knowledge/`. Python code never contains a prompt. This means:

- A domain expert can read and update agent behaviour without touching Python.
- Prompt changes appear as normal git diffs — reviewable, attributed, rolled back like code.
- The knowledge base (SOPs, ADRs, ADDs) is loaded at runtime from a separate designs repo, not embedded in the tool.

### Organisation's own knowledge base

Agents read the organisation's actual ADRs, ADDs, and SDLC function guides — not generic best-practice instructions baked into the tool. When the tech lead does an architecture review, it reads the ADD for the relevant domain and the ADR that governs the design pattern. When the security reviewer checks a file upload, it reads ADD-035 (Secure Input and File Upload Standards). The tool has no opinion on these standards; the organisation's documents do.

### Human review gate

The crew produces a complete implementation package — feature files, stub code, review reports, DoD compliance — for human review. No merge, no deploy, no Terraform apply happens without a human. This is enforced in the tool design, not just as a policy: agents have no write access to git remote, no AWS deploy credentials, and no Jira transition rights.

### Model tiers per agent

Not every agent needs the same model. Lightweight tasks (sprint planning, DoD check) run on a fast/cheap model. Implementation agents run on the standard model. Reviewer agents that must catch subtle bugs run on the most capable model. This is configured per-agent in the OKF file (`model: fast | standard | powerful`) and resolved to Bedrock model IDs at startup.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  code-crew CLI  (code_crew/repl.py)                             │
│                                                                 │
│  /jira LOOPLAT-123  →  fetches Jira ticket                     │
│                     →  TicketFlow (code_crew/flow.py)           │
│                        runs tasks one at a time, streams status │
└───────────────────────────┬─────────────────────────────────────┘
                            │
          ┌─────────────────▼──────────────────┐
          │  build_single_task_crew()           │
          │  (code_crew/crew.py)                │
          │                                     │
          │  Crew  ──  Task  ──  Agent  ──  LLM │
          │                          │           │
          │                        Tools         │
          └─────────────────────────────────────┘
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
    knowledge_reader  workspace_reader  platform_shell
    (designs repo)    (platform codebase)  (git, go build,
                                            grep)
```

### Key components

| Component | Path | Purpose |
|-----------|------|---------|
| REPL | `code_crew/repl.py` | Interactive terminal UI (prompt_toolkit + Rich). Handles `/jira`, `/memory`, profile loading, Langfuse init. |
| Flow | `code_crew/flow.py` | `TicketFlow` — iterates through the 10 tasks, calls `build_single_task_crew()` per task, streams status to REPL. |
| Crew builder | `code_crew/crew.py` | Builds agents and tasks from OKF files. `build_single_task_crew()` creates a minimal crew for one task. |
| OKF loader | `shared/okf_loader.py` | Parses OKF markdown into `AgentConcept` / `TaskConcept` structs. |
| Bedrock factory | `shared/bedrock.py` | Creates `crewai.LLM` instances for each model tier. IAM auth only — no API keys. |
| Telemetry | `shared/telemetry.py` | Installs OTLP TracerProvider pointing at Langfuse. Must run before any crewai import. |
| Profile system | `shared/config.py` | Loads `~/.code-crew/profiles/{name}.yaml`. Profiles hold all env vars — Bedrock IDs, Jira config, Langfuse keys. |
| Knowledge | `code_crew/knowledge/` | OKF markdown — one file per agent, one per task, one per standalone prompt. |

---

## The 10-task pipeline (code-crew)

Tasks run sequentially. Each task receives the typed outputs of its upstream dependencies as context — it does not see the full conversation of prior agents, only the structured result.

```
sprint_planning_check     scrum_master     DoR gate — checks ACs are testable, story is sized
        │
architecture_review       tech_lead        Reads ADRs/ADDs, proposes design, identifies gaps
        │
scaffold_code             backend_dev      Checks for existing code; creates stubs only if new
        │                                  Runs go build after writing any Go files
scaffold_test             qa_engineer      Creates test file stubs matching the scaffold
        │
bdd_test_authoring        qa_engineer      Writes Gherkin .feature files from acceptance criteria
        │
backend_implementation    backend_dev      Implements against BDD scenarios; unit tests inline
        │
frontend_implementation   frontend_dev     React components, follows Figma/HTML design refs
        │
code_review               tech_lead        Reviews backend + frontend output, flags issues
        │
security_review           security_rev     OWASP Top 10, ADD-035 file upload standards, STRIDE
        │
dod_check                 scrum_master     Loads DoD from designs repo, produces PASS/FAIL report
```

Each task in `crew.py` is a `Task(name=..., description=ctx+okf_description, expected_output=..., agent=..., context=[upstream_tasks])`. The `name=` field is critical — it prevents CrewAI from falling back to the full description as the display name in the REPL.

---

## Agents

### Code crew

| Agent key | Role | Model tier | Tools |
|-----------|------|-----------|-------|
| `scrum_master` | Scrum Master | fast | knowledge_reader, dod_checker, jira_view, memory_tool |
| `tech_lead` | Tech Lead / Architect | standard | knowledge_reader, workspace_reader, jira_view, platform_shell |
| `backend_developer` | Senior Backend Developer | standard | knowledge_reader, workspace_reader, jira_view, platform_shell, python_repl |
| `frontend_developer` | Senior Frontend Developer | standard | knowledge_reader, workspace_reader, jira_view, platform_shell, python_repl |
| `qa_engineer` | QA Engineer | standard | knowledge_reader, workspace_reader, jira_view, platform_shell, bdd_runner, python_repl |
| `security_reviewer` | Security Reviewer | powerful | knowledge_reader, workspace_reader, platform_shell, python_repl |

All agents: `max_iter=15`, `verbose=True` (suppressed at display layer — see Verbosity below).

### Ops crew

| Agent key | Role | Tools |
|-----------|------|-------|
| `ops_lead` | Ops Lead | knowledge_reader, workspace_reader, platform_shell |
| `terraform_engineer` | Terraform Engineer | knowledge_reader, workspace_reader, platform_shell |
| `cicd_engineer` | CI/CD Engineer | knowledge_reader, workspace_reader, platform_shell |
| `monitoring_engineer` | Monitoring Engineer | knowledge_reader, workspace_reader, platform_shell |
| `release_manager` | Release Manager | knowledge_reader, workspace_reader, platform_shell |

---

## Tools

| Tool | Class | What it does |
|------|-------|-------------|
| `knowledge_reader` | `KnowledgeReaderTool` | Reads OKF docs from the designs repo (ADR, ADD, SDLC roles/functions/stacks). Pre-loads all docs at startup from `DESIGNS_PATH`. Falls back gracefully if repo unavailable. |
| `workspace_reader` | `WorkspaceReaderTool` | Read/list/search the platform codebase. File cap: 200 lines. Search cap: 50 matches. Paths relative to cwd. No writes. |
| `dod_checker` | `DoDCheckerTool` | Loads and parses the DoD document from the designs repo. Returns structured checklist for Scrum Master to reason over. |
| `jira_view` | `JiraViewTool` | Fetches a Jira ticket by key (summary, description, ACs, comments, linked issues). |
| `jira_list` | `JiraSprintListTool` | Lists tickets in the current sprint for context. |
| `platform_shell` | `PlatformShellTool` | Sandboxed shell in the platform repo. Runs git, go, npm commands. No network access, no writes outside cwd. |
| `python_repl` | `PythonREPLTool` | In-process Python REPL for data inspection and scripting. |
| `bdd_runner` | `BDDTestRunnerTool` | Runs BDD feature files in the integration test suite. Returns pass/fail with output. |
| `memory_tool` | `MemoryTool` | Read/write crew memory (`code-crew memory add/list`). Persists context across runs. |

---

## Knowledge system

### OKF format

All knowledge files use OKF (Open Knowledge Format): YAML frontmatter for structured fields, markdown body for content.

Agent files (`knowledge/agents/<name>.md`) supply `role`, `goal`, `model` (tier), and the body becomes the agent's backstory. Task files (`knowledge/tasks/<name>.md`) supply `description` (loaded as the task instruction) and `expected_output`.

No prompt text lives in Python. Changing agent behaviour is a markdown edit.

### Designs repo

The crew loads the organisation's knowledge at startup from `DESIGNS_PATH`:

```
$DESIGNS_PATH/ADR/     Architecture Decision Records
$DESIGNS_PATH/ADD/     Architecture Design Documents
$DESIGNS_PATH/SDLC/    Role definitions, function guides, stack conventions
```

Two modes:
- **Local checkout** — `DESIGNS_PATH=/path/to/designs`
- **Auto-clone** — set `DESIGNS_REPO=git@...` and `DESIGNS_PATH=./designs`; cloned on first run

If the designs repo is unavailable, agents continue with a warning and no loaded knowledge.

---

## Configuration

### Profile system

All environment configuration lives in `~/.code-crew/profiles/{name}.yaml`. The profile is selected at CLI startup via `--profile` flag or `.code-crew.yaml` in the project directory.

```yaml
# ~/.code-crew/profiles/youramaryllis.yaml
env:
  BEDROCK_MODEL_ID: us.anthropic.claude-sonnet-4-6
  BEDROCK_FAST_MODEL_ID: us.anthropic.claude-haiku-4-5-20251001-v1:0
  BEDROCK_POWERFUL_MODEL_ID: us.anthropic.claude-opus-4-8-20260101-v1:0
  BEDROCK_REGION: us-west-2
  AWS_PROFILE: youramaryllis
  JIRA_URL: https://your-org.atlassian.net
  JIRA_USER: you@example.com
  DESIGNS_REPO: git@github.com:your-org/designs.git
  LANGFUSE_PUBLIC_KEY: pk-lf-...
  LANGFUSE_SECRET_KEY: sk-lf-...
```

### Project-level config

`.code-crew.yaml` in any platform directory selects a profile and declares tech stacks:

```yaml
profile: youramaryllis
stacks:
  - terraform-aws
  - go-backend
  - typescript-react
```

Stacks control which `SDLC/stacks/*.md` documents are pre-loaded and which stack agents are wired to.

### Environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `BEDROCK_MODEL_ID` | Yes | Standard model (cross-region inference profile ID) |
| `BEDROCK_FAST_MODEL_ID` | No | Fast/cheap tier — falls back to standard |
| `BEDROCK_POWERFUL_MODEL_ID` | No | Powerful tier for reviewers — falls back to standard |
| `BEDROCK_REGION` | Yes | AWS region |
| `AWS_PROFILE` | No | AWS profile name for IAM auth |
| `BEDROCK_GUARDRAIL_ID` | No | Bedrock Guardrails ID for content policy |
| `DESIGNS_PATH` | Yes | Path to knowledge repo checkout |
| `DESIGNS_REPO` | No | Git URL — auto-cloned if DESIGNS_PATH missing |
| `DESIGNS_BRANCH` | No | Branch to clone (default: main) |
| `PLATFORM_PATH` | Yes | Path to codebase agents work on |
| `JIRA_PROJECT` | Yes | Jira project key (e.g. LOOPLAT) |
| `JIRA_URL` | Yes | Jira base URL |
| `JIRA_USER` | Yes | Jira user email |
| `JIRA_TOKEN` | Yes | Jira API token |
| `LANGFUSE_PUBLIC_KEY` | No | Langfuse tracing (OTLP) |
| `LANGFUSE_SECRET_KEY` | No | Langfuse tracing (OTLP) |

---

## Observability

Traces are sent to Langfuse via OpenTelemetry OTLP. CrewAI instruments all crew/task/agent/LLM lifecycle events via the global `TracerProvider`. Because CrewAI installs its own provider at import time, `setup_langfuse()` in `shared/telemetry.py` must run before any crewai import — this is enforced in `repl.py`'s `main()` by ordering the import after profile load.

The REPL banner shows `langfuse ✓` or `langfuse ✗` at startup.

---

## Console verbosity

CrewAI's default console output is extremely verbose: full task descriptions, agent reasoning, tool inputs and outputs. The REPL suppresses this to show only:

- Current task name and assigned agent
- Tool call one-liners (tool name + key arg, no output)
- Task completion tick or failure
- Critical errors

This is achieved by replacing CrewAI's `EventListener.formatter` with a minimal `_QuietFormatter` (plain class, no inheritance, `__getattr__` catch-all) and monkey-patching `crewai_core.printer.Printer.print` to a no-op (ContextVar suppression doesn't propagate to ThreadPoolExecutor workers).

---

## Planned crews

The tools repo will grow to cover the full product lifecycle with three purpose-built crews:

### code-crew (current)
Development. Takes a Jira story, delivers a reviewed, DoD-gated implementation package.

### requirements-crew (planned)
Product intake and requirements. Takes a raw idea, problem statement, or customer feedback and produces a structured Jira story with acceptance criteria, ADR/ADD references, and scope boundaries. This is the "office hours" layer — challenging scope, surfacing assumptions, producing a story the code-crew can execute. Agents: product analyst, requirements engineer, architect (for ADD selection).

### post-launch-crew (planned)
Post-launch monitoring and retrospective. Takes a deployed release, reads monitoring data, synthesises feedback, produces a retrospective report and follow-up tickets. Agents: release analyst, monitoring reviewer, feedback synthesiser.

---

## Security constraints

These are architectural constraints, not just policy:

- **No API keys in code** — Bedrock auth is IAM only. Keys never appear in OKF files, Python, or `.env`.
- **No autonomous deploys** — agents have no AWS deploy credentials, no git push rights, no Jira transition rights.
- **No prompt injection via knowledge docs** — Bedrock Guardrails (`BEDROCK_GUARDRAIL_ID`) can be applied to all completions; the knowledge reader tool returns document content but agents cannot execute it.
- **Workspace sandbox** — `platform_shell` and `workspace_reader` are scoped to the platform codebase. Path traversal outside the root is rejected.
- **Scaffold gate** — `scaffold_code` checks for existing files before writing; runs `go build` after writing Go files to catch syntax errors before they propagate.
