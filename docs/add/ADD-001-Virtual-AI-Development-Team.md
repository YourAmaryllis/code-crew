# ADD-001: Virtual AI Development Team

**Status:** Accepted
**Date:** 2026-06-16
**Related:**
- [ADR-001: CrewAI Multi-Agent Architecture](../adr/ADR-001-CrewAI-Multi-Agent-Architecture.md)
- [SAD-001: code-crew system architecture](../sad/SAD-001-code-crew.md)

---

## Purpose

Design a virtual AI development team — a set of CrewAI agents organised into flows — that follows an organisation's SDLC SOPs and development workflow to accelerate feature delivery. This is a **development tool**; it is not a feature of any product and is not deployed as part of a platform.

The virtual team:
- **Reads** issue tracker tickets, the platform codebase, and the organisation's design documents (`designs/`)
- **Produces** BDD scenarios, code implementations, review comments, release notes, staging validations, and design document stubs (ADRs, ADDs, threat model skeletons)
- **Posts** results as issue tracker comments
- **Hands off** to humans at every SOP-mandated approval gate

---

## Goals

| # | Goal |
|---|------|
| G1 | Reduce time-to-first-draft for upstream SDLC phases by generating artifacts automatically from issue tracker content |
| G2 | Maintain issue-tracker-first traceability — the issue tracker remains the product source of truth |
| G3 | Preserve all human oversight gates defined in the organisation's SOP — no crew auto-advances past a human approval point |
| G4 | Support multiple LLM backends (Bedrock, Anthropic, OpenAI, Groq, Ollama) without changing agent definitions |
| G5 | Keep the tool repo entirely separate from the platform repo to avoid conflating the tool with the product |
| G6 | Support any issue tracker (Jira, Linear, GitHub Issues) via a common interface |

---

## Scope

### In scope

- Standalone Python CLI (`code-crew`) and interactive REPL
- Agent definitions for all SDLC roles (OKF markdown files)
- Flow configurations per SDLC phase group (ticket, design, audit, UX, domain)
- Tool library (issue tracker, GitHub, codebase read/write, test runner, knowledge reader)
- Human checkpoint gate definitions
- Multi-LLM backend support via LiteLLM (Bedrock, Anthropic, OpenAI, Groq, Ollama, NVIDIA)
- Open-core licensing (Community / Pro tiers)
- Stack-specific context injection (language, compliance, architecture style)
- Skills — session-scoped output style modifiers

### Out of scope

- Platform product features (this tool is never shipped in the platform)
- UX / Figma design generation (design remains human; AI can critique but not author frames)
- Full replacement of human judgment at gates (compliance sign-off, security risk acceptance, production deploys)
- Automatic production deployment (always manual)

---

## Agent Roster

### Active agents

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

All agents: `max_iter=15`. A single full-stack `engineer` handles both backend and frontend — see [ADR-002](../adr/ADR-002-Fullstack-Engineer-Agent.md) for rationale.

### Roles kept fully human

| Role | Why |
|------|-----|
| UX Designer | Figma authorship requires visual judgment and user empathy; AI reviews but does not author frames |
| Compliance Final Approver | Legal accountability for regulatory sign-off must remain with a named human |
| Security Lead Final Approver | Risk acceptance carries personal accountability |
| Product Owner (issue tracker authority) | Scope, priority, and done-ness are product decisions; AI never sets them |

---

## Flow Configurations

### Ticket flow (`/issue <KEY>`, `/sprint <name>`)

Full SDLC for one ticket. Tasks run sequentially with retry gates on each review step.

```
sprint_planning       scrum_master     DoR gate — ACs testable, story sized
architecture_review   architect        Reads ADRs/ADDs, proposes design
scaffold_code         manager→engineer Creates stubs; runs build verification
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
promote_staging       manager→devops   Push rc tag, redeploy staging environment
staging_verification  manager→qa_lead  BDD smoke on staging (loops on failure)
launch_decision       release_engineer Go/no-go for production (human gate follows)
smoke_test            manager→qa_lead  Read-only smoke on production
```

Review gates retry up to `flow.max_retries` (default 3) before escalating to human.

**Manager–worker tasks** (`Process.hierarchical`): scaffold_code, scaffold_test, bdd_authoring, bdd_finalization, implementation, devops_coordination, release_notes, promote_staging, staging_verification, smoke_test, ux_implementation, domain_extract.

**Sequential tasks** (no manager): all review, planning, and evaluation tasks.

### Design flow (`/design <KEY>`)

Pre-implementation. Produces ADD/ADR/TMD stub before any code is written. Chief Architect approval loop.

```
design_requirements      architect            Extract requirements and constraints
design_add_draft         architect            Draft ADD (context, decisions, alternatives)
design_security_input    security_lead        Security analysis + TMD stub
design_compliance_input  compliance_officer   Compliance requirements
design_chief_review      architect            Chief Architect reviews via ask_human; loops on REVISION NEEDED
design_finalize          engineer             Commit files, push branch, open PR, update ticket
```

### UX flow (`/ux <KEY>`)

Figma frame → component specification → implementation → review loop.

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

### Audit (`/audit`)

Six-task sequential audit. No retry loops — produces a report with FINDING / PASS / REQUIRED lines.

```
verify_arch_scan        architect             Architecture compliance vs ADRs/ADDs
verify_security_scan    security_lead         OWASP + STRIDE + compliance stacks
verify_compliance_scan  compliance_officer    Regulatory evidence gaps
verify_domain_scan      architect             DMD drift — code entities vs designs/DMD/
verify_chief_review     architect             Aggregates findings; marks REQUIRED / EXEMPT / PASS
verify_report           scrum_master          Writes .code-crew/audit-YYYYMMDD-HHMMSS.md
```

REQUIRED findings prompt the REPL to open issue tracker tickets for each.

---

## Tool Library

| Tool | Class | What it does |
|------|-------|-------------|
| `knowledge_reader` | `KnowledgeReaderTool` | Reads OKF docs from the designs repo (ADR, ADD, SDLC functions, stacks) on demand at agent runtime — not pre-loaded. |
| `workspace_reader` | `WorkspaceReaderTool` | Read/list/search the platform codebase. 200-line file cap, 50-match search cap. No writes. |
| `platform_shell` | `PlatformShellTool` | Sandboxed shell in the project root. Runs build tools, test runners, git. No network, no writes outside cwd. |
| `api_spec` | `ApiSpecTool` | Reads OpenAPI 3.1 spec, lists routes, checks drift between spec and source file route annotations. |
| `dod_checker` | `DoDCheckerTool` | Loads and parses the DoD document, returns structured checklist for Scrum Master to evaluate against. |
| `issue_view` | `IssueViewTool` | Fetches a ticket by key (summary, description, ACs, comments, linked issues). Backend determined by `ISSUE_TRACKER` env var. |
| `issue_list` | `IssueListTool` | Lists tickets in the current sprint/iteration. Same backend abstraction. |
| `memory_tool` | `MemoryTool` | Read/write crew memory (`code-crew memory add/list`). Persists across runs. |
| `ask_human` / `HumanRelay` | `HumanInputTool` | Thread-safe bridge for async SME input. Questions batched 3–5 per round; ends with `AWAITING SME RESPONSE`. |

**Issue tracker backends** (`ISSUE_TRACKER` env var or `issue_tracker.type` in config):

| Backend | Value | Auth |
|---------|-------|------|
| Jira | `jira` | `JIRA_URL`, `JIRA_USER`, `JIRA_TOKEN` |
| Linear | `linear` | `LINEAR_API_KEY` |
| GitHub Issues | `github` | `gh auth login` (GitHub CLI) |

---

## Human Checkpoint Gates

### Non-negotiable human gates

No crew can auto-advance past these. They require a deliberate human action (issue tracker transition, PR approval, CLI command).

| Gate | SDLC Phase | What Humans Do | Why |
|------|-----------|----------------|-----|
| BDD scenario approval | Test authoring | QA + Product Owner review test coverage and business logic accuracy | Business accuracy cannot be derived from acceptance criteria text alone |
| PR merge (2 approvals) | Implementation | 2 human reviewers formally approve the PR | DoD requirement; catches AI hallucinations in code |
| Production deploy | Release | Ops Lead + stakeholders trigger `workflow_dispatch` or equivalent | Live data risk; mistakes are costly and hard to reverse |
| Compliance verification | Review | Compliance officer reviews compliance evidence and signs off | Regulatory accountability requires a named human |
| Security risk acceptance | Review | Security Lead reviews threat model and accepts/rejects residual risks | Risk decisions carry personal accountability |
| Chief Architect review | Design | Chief Architect reviews design docs; marks APPROVED or REVISION NEEDED | Long-term architectural commitment with accountability |

### Where crew reduces human effort (but not oversight)

| Previously manual task | Crew output | Human effort reduced to |
|-----------------------|-------------|------------------------|
| Writing BDD scenarios from scratch | QA agent generates Gherkin `.feature` file from acceptance criteria | Review business logic accuracy, add edge cases (~30 min vs 2–4 hrs) |
| Architecture review document | Architect agent drafts ADD with options and tradeoffs | Select decision, add nuance (~20 min vs 1–2 hrs from scratch) |
| First-pass code review | Architect + Security agents post inline review comments | Validate comments, add judgment, formally approve |
| E2E test failure triage | QA agent analyses CI logs and suggests root cause | Confirm and apply fix |
| Release notes / CHANGELOG | Release engineer generates from git log | Quick edit and publish |
| Security threat entry authoring | Security agent drafts threat model entries | Review severity, accept/reject |
| Sprint planning decomposition | Scrum master + engineer decompose and estimate | Adjust priorities (30 min vs 2 hr meeting) |

---

## User Interaction Model

### CLI (primary interface)

The `code-crew` CLI is the primary interface. It requires no always-on infrastructure — a developer runs a command, a crew executes, results appear in the terminal and are posted to the issue tracker.

```bash
# Bootstrap a project
code-crew init
code-crew explore

# Design phase — produce ADD/ADR/TMD stub before coding
code-crew design PROJ-85

# Full SDLC for a ticket
code-crew issue PROJ-90

# Audit the codebase
code-crew audit

# Domain modeling from requirements
code-crew domain design PROJ-110

# Domain model extraction from existing code
code-crew domain extract ./src
```

All commands can also be run as slash commands inside the interactive REPL:
```
/design PROJ-85
/issue PROJ-90
/audit
```

### Day-in-the-life: Developer

**Without code-crew:**
1. Pick up story — sparse issue description, no BDD scenarios written yet
2. Write BDD scenarios (2–4 hrs)
3. Implement code with AI coding assistant
4. Open PR manually, write description
5. Wait for review, address comments

**With code-crew:**
1. Pick up story — BDD scenarios already generated (QA flow ran earlier), design doc linked
2. Run `code-crew issue PROJ-XX` or wait for the REPL to continue
3. PR opens within the hour for well-scoped stories
4. Review the diff, refine logic where crew missed context or platform-specific nuance
5. Architect agent has already posted inline review comments
6. Address comments; 2 human reviewers approve; merge

### Day-in-the-life: Architect

1. New feature request arrives
2. Run `code-crew design PROJ-XX` — ADD draft appears with options and tradeoffs; security and compliance input appended
3. Chief Architect reviews draft (20 min vs 2 hrs from scratch), selects decision, adds nuance via `/feedback`
4. Design finalize task commits files and opens PR
5. For the ticket flow: `architecture_review` task reads the committed ADD and proposes implementation approach before any code is written

### Day-in-the-life: QA Engineer

1. Story reaches test-authoring status
2. `bdd_authoring` task in the ticket flow generates `.feature` file from acceptance criteria
3. QA Lead reviews scenarios — checks business logic accuracy, adds edge cases not derivable from the ticket text
4. `bdd_po_review` and `bdd_arch_review` tasks validate from the Product Owner and Architect perspectives
5. After PR merge: `staging_verification` task runs the BDD suite against staging and posts a triage report

---

## Repository Structure

```
code-crew/
├── code_crew/
│   ├── knowledge/
│   │   ├── agents/          # OKF .md files — one per agent role
│   │   ├── tasks/           # OKF .md files — one per task
│   │   ├── stacks/          # Stack-specific context (go-backend, typescript-react, gdpr, …)
│   │   ├── functions/       # SDLC process guides (BDD, DB schema, API standards, …)
│   │   └── skills/          # Output style modifiers (terse, strict, explain, dry-run)
│   ├── crew.py              # Builds agents and tasks from OKF files
│   ├── flow.py              # TicketFlow, DesignFlow, UxFlow, DomainFlow
│   ├── main.py              # CLI entry point
│   └── repl.py              # Interactive REPL (prompt_toolkit + Rich)
├── shared/
│   ├── okf_loader.py        # Parses OKF markdown into AgentConcept / TaskConcept structs
│   ├── llm_factory.py       # Resolves agent → tier → model; multi-provider
│   ├── bedrock.py           # Backward-compat shim re-exporting from llm_factory
│   ├── config.py            # Loads structured YAML profiles into os.environ
│   ├── telemetry.py         # OTLP → Langfuse tracing
│   ├── aws_auth.py          # Expired credential detection + actionable error hints
│   └── tools/               # KnowledgeReaderTool, WorkspaceReaderTool, PlatformShellTool, …
├── tests/
├── docs/                    # This documentation
├── pyproject.toml
└── .config.example.yaml
```

---

## LLM Cost Analysis

Approximate per-sprint token usage (5–10 stories, 2-week sprint) using Claude models on Bedrock or Anthropic API.

> Costs depend on provider and model. Claude Sonnet 4.6 ≈ $3/$15 per M tokens (input/output); Opus 4.8 ≈ $15/$75; Haiku 4.5 ≈ $0.25/$1.25. Check provider pricing pages for current rates.

| Flow / Crew | Model tier | Est. Input Tokens | Est. Output Tokens | Approx. Cost/Sprint |
|-------------|-----------|------------------|-------------------|---------------------|
| Sprint planning + DoD (scrum_master) | fast | 100K | 30K | $0.06 |
| Architecture review + design (architect) | powerful | 200K | 100K | $10.50 |
| BDD authoring (qa_lead) | standard | 200K | 100K | $2.10 |
| Implementation × 5–10 stories (engineer) | standard | 900K | 600K | $11.70 |
| Code + security review (architect, security_lead) | powerful | 300K | 100K | $12.00 |
| Compliance review (compliance_officer) | standard | 100K | 50K | $1.05 |
| DevOps + staging (devops_lead, qa_lead) | standard | 150K | 50K | $1.95 |
| **Total per sprint** | | **~2M** | **~1M** | **~$39** |

### Cost controls

- **Model tiering** — fast (Haiku) for routing/planning tasks, standard (Sonnet) for most work, powerful (Opus) only for architect and security (high-reasoning tasks)
- **Token caps per crew** — `max_tokens` set per agent; fail loudly on budget overrun
- **Dry run mode** (`/skill dry-run`) — shows what crew would do without executing LLM calls
- **Checkpoint resume** — completed tasks are not re-run on retry; only failed tasks consume tokens

---

## Relationship to Existing Tooling

| Tool type | Relationship to code-crew |
|-----------|--------------------------|
| **AI coding assistants** (Claude Code, Cursor, etc.) | Complementary — assistant for interactive refinement; code-crew for autonomous pipeline runs. Both can work on the same branch. |
| **Issue tracker** (Jira, Linear, GitHub Issues) | code-crew reads tickets and posts results as comments; ticket remains the canonical work item |
| **CI/CD** (GitHub Actions, GitLab CI) | code-crew kicks off CI runs via the `async_job` tool; polls for completion; never replaces CI |
| **Designs repo** (`designs/`) | code-crew reads ADRs/ADDs for context; design tasks produce ADR/ADD drafts committed by a human |
| **MCP servers** | code-crew agents can call MCP tools (Figma, Linear MCP, etc.) via `~/.code-crew/mcp.yaml` |

---

## Delivery Phases

### Phase 1 — Scaffold + Ticket flow (core SDLC)

Rationale: The ticket flow delivers the highest ROI — it covers the full cycle from sprint planning to staging verification and produces immediately useful output.

Deliverables:
- Repo scaffold (`knowledge/`, `shared/`, `code_crew/`)
- OKF loader and LLM factory
- Issue tracker tool (Jira / Linear / GitHub Issues)
- Workspace reader, knowledge reader, platform shell tools
- All core agents and task definitions
- `TicketFlow` with retry gates and checkpointing
- `code-crew issue <KEY>` and REPL
- Unit tests for all tool functions

### Phase 2 — Design flow

Deliverables:
- `DesignFlow` (design_requirements → design_chief_review → design_finalize)
- Chief Architect human relay (ask_human integration)
- `code-crew design <KEY>` command

### Phase 3 — Audit + Domain flows

Deliverables:
- Six-task audit crew (`/audit`)
- Domain modeling flow (three-phase event storming + extract)
- `DomainFlow` with per-flow iteration
- `code-crew audit`, `code-crew domain design <KEY>`, `code-crew domain extract`

### Phase 4 — UX flow + Pro knowledge tier

Deliverables:
- `UxFlow` (ux_spec → ux_implementation → ux_review)
- Figma MCP integration via `mcp.yaml`
- Pro knowledge tier served via Supabase license server (see [ADD-003](ADD-003-Monetization-Licensing.md))
- `code-crew license status` command
