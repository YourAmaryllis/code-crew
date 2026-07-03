# ADR-001: Virtual AI Development Team — CrewAI Multi-Agent Architecture

**Status:** Accepted
**Date:** 2026-06-16
**Related:**
- [ADD-001: Virtual AI Development Team Design](../add/ADD-001-Virtual-AI-Development-Team.md)
- [ADR-002: Full-stack engineer agent](ADR-002-Fullstack-Engineer-Agent.md)
- [SAD-001: code-crew system architecture](../sad/SAD-001-code-crew.md)

---

## Context

The engineering team builds a complex platform that spans multiple languages, frameworks, and infrastructure. The existing workflow uses AI coding assistants (paired programming sessions) to assist individual developers — a single developer prompts a coding agent, which pair-programs on their branch.

This model has a gap: **AI coding assistants operate session-by-session at the individual level**. They do not:

- Continuously generate upstream artifacts (BRD, ADR, BDD scenarios) on a per-ticket basis without manual invocation
- Simulate distinct professional roles (Architect vs. QA vs. Security) with specialised context, tools, and decision authority
- Coordinate work across multiple SDLC phases automatically as issue tracker tickets progress
- Produce a first-pass code implementation, open a PR, and post a review comment — all without a human initiating each step

The organisation's multi-phase SDLC SOP defines what each role produces and when. Upstream phases (requirements through test development) are heavily document-intensive and are currently bottlenecks: they require experienced staff to author design documents, compliance requirements, ADRs, and BDD scenarios before implementation can begin.

**The opportunity:** treat the SOP roles as AI agent personas, give each persona a bounded toolset (issue tracker, GitHub, the platform codebase), and orchestrate them with **CrewAI** using **AWS Bedrock** (or any LiteLLM-compatible LLM backend). This is an **internal development tool** — it helps the team build the platform faster. It is not a platform feature and is not deployed as part of the product.

### Why a separate repository

The virtual team tooling is distinct in purpose, language runtime (Python), dependency surface (CrewAI, boto3), and lifecycle from the platform repository. Bundling it into the platform would pollute the language module boundary, add Python CI paths to every platform PR, and conflate the tool that builds the platform with the platform itself. A separate repository clarifies ownership, allows independent versioning, and lets the team iterate on agent prompts without touching platform CI.

### Why CrewAI

CrewAI provides:
- **Role-based agents** with explicit backstory, goal, and bounded toolset — maps directly to the SOP role hierarchy
- **Sequential and hierarchical crews** matching the phase structure (some phases gate on the output of the previous)
- **Task dependencies** within a crew — e.g., the Security Analyst must read the Architect's ADR draft before writing threat entries
- A proven LiteLLM integration supporting Bedrock, Anthropic, OpenAI, Groq, Ollama, and NVIDIA

### Why AWS Bedrock (as default)

- Bedrock provides Claude models (Sonnet, Opus, Haiku) with IAM auth — no API key sprawl, consolidated billing, private VPC endpoint available
- The IAM patterns for Bedrock (`bedrock:Converse`, `bedrock:InvokeModel`) are well-established and auditable
- No data leaves AWS infrastructure when using Bedrock

The LLM backend is configurable — any LiteLLM-compatible provider works (see [SAD-001 Configuration](../sad/SAD-001-code-crew.md)).

---

## Decision

1. **Build a standalone virtual AI development team** in a dedicated repository using **CrewAI** as the agent orchestration framework and **AWS Bedrock** (or any LiteLLM-compatible backend) as the LLM provider.

2. **The virtual team is a development tool, not a platform component.** It reads and writes to the platform repository (via git and GitHub CLI), posts to the issue tracker, and opens PRs — but it is never deployed as part of the product.

3. **Agent roles map to SOP phases.** Each agent has a named role (engineer, QA lead, architect, security lead, DevOps lead, release engineer, compliance officer, scrum master, product owner, UX lead), a model tier appropriate to task complexity, and a bounded toolset. Full roster: [ADD-001](../add/ADD-001-Virtual-AI-Development-Team.md).

4. **Flows map to phase groups.** Agents are assembled into flows that correspond to SOP phase groups (ticket, design, audit, UX, domain). Each flow produces concrete artifacts (code, PRs, design documents, issue tracker comments).

5. **Human checkpoint gates are preserved.** No flow auto-advances past a gate-protected status without a human action. The SOP-mandated approval points (ADR sign-off, PR merge, production deploy, compliance verification, security risk acceptance) remain human-only. See [ADD-001 §Human Checkpoint Gates](../add/ADD-001-Virtual-AI-Development-Team.md).

6. **Interactive AI coding assistants remain the interactive override.** code-crew runs autonomously (CLI or REPL). When a developer wants to take over or refine crew output, they use their preferred AI coding assistant in the same branch. Crew output and interactive sessions are compatible.

7. **Bedrock model tiering (default):**
   - **Claude Opus** — Architect, Security Lead (complex reasoning, architectural decisions)
   - **Claude Sonnet** — Engineer, QA Lead, DevOps Lead, Release Engineer, Compliance Officer, Product Owner, UX Lead
   - **Claude Haiku** — Scrum Master (routing, tracking, sprint summaries)

8. **Start with CLI mode.** The first delivery is `code-crew issue <KEY>` — human-invoked. Fully automated trigger modes (e.g., Jira webhooks) may be added in a later phase after baseline quality is established.

---

## Considered options

### Option 1: Extend existing AI coding assistant sessions with additional personas

Add more slash commands or skills to the existing AI coding assistant setup (e.g., `/security-review`, `/write-bdd`), keeping everything within the platform repository's configuration directory.

- *Pros:* No new repository; builds on familiar tooling; developers already know the workflow.
- *Cons:* AI coding assistant sessions are human-initiated and human-scoped; they do not run autonomously or coordinate across multiple role agents within a phase; cannot simulate a full crew handoff (Architect output → Security Analyst input). Personas would be prompts, not agents with real tool access.

### Option 2: Use a third-party AI team tool (Devin, GitHub Copilot Workspace, SWE-agent)

- *Pros:* Managed service; no infrastructure to build.
- *Cons:* Cannot follow the organisation's specific SDLC SOP, Jira-traceability rules, or DoD checklist; LLM calls may leave the organisation's cloud (data-residency risk); limited ability to inject organisation-specific tools (issue tracker integration, internal ADR templates, platform codebase conventions).

### Option 3: Extend an existing AI agent within the platform product

Extend an existing AI feature in the platform into a general-purpose agent framework.

- *Pros:* Reuses proven code; no new repository.
- *Cons:* Conflates a platform product feature with a development toolchain; would require shipping agent prompts and issue tracker / GitHub credentials as part of the platform container; increases platform attack surface unnecessarily.

### Option 4: Standalone CrewAI repository (chosen)

- *Pros:* Clean separation of concerns; matches CrewAI's designed use pattern; proven LLM integration; full control over SOP-phase-to-flow mapping; human gates preserved; compatible with existing interactive AI coding workflows; independent versioning and CI.
- *Cons:* New repository to maintain; Python runtime alongside platform languages; initial setup cost.

---

## Consequences

**Positive:**
- Upstream SDLC phases (design, architecture, test authoring) become dramatically faster — AI drafts, humans review and approve
- Sprint planning, standup prep, and backlog decomposition are automated
- Consistent artifact quality (ADR/ADD format, BDD scenario structure, commit message format) enforced by agent prompts
- Issue tracker traceability enforced programmatically — agent always includes issue key in commit messages and PR titles
- LLM backend is swappable without changing agent definitions

**Negative / Risks:**
- AI-generated code requires human review (mitigated by preserving PR approval gate)
- Agent prompts need maintenance as SOP evolves
- Risk of over-reliance: team may skip reviewing AI-generated artifacts — mitigated by explicit gate workflow and DoD checklist enforcement
- Initial prompt engineering investment to align agent output with the organisation's conventions

**Operational:**
- A dedicated IAM role with minimum-privilege Bedrock access is created for local developer use; no platform data access
- Secrets (issue tracker API token, GitHub PAT for `gh` CLI) stored in the developer's local environment; never committed
- Platform CI is unaffected — the virtual team has its own CI
