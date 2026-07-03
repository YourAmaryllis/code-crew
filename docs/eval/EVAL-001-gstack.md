# EVAL-001: code-crew vs gstack

**Status:** Accepted
**Date:** 2026-06-19
**Related:**
- [ADR-001: CrewAI Multi-Agent Architecture](../adr/ADR-001-CrewAI-Multi-Agent-Architecture.md)
- [SAD-001: code-crew system architecture](../sad/SAD-001-code-crew.md)

---

gstack (github.com/garrytan/gstack, 111k stars) is the most-starred open-source AI development toolchain as of mid-2026. It's worth understanding precisely because it solves an adjacent problem with a fundamentally different architecture.

---

## What gstack is

gstack is a collection of slash commands (Claude Code skills) installed at `~/.claude/skills/gstack`. Running `/plan-eng-review` or `/qa` gives Claude Code a structured role to play in that session. It has 23 specialist roles: CEO reviewer, engineering manager, designer, QA lead, security officer, release engineer. It installs in 30 seconds, requires no infrastructure, and ships as MIT-licensed markdown and TypeScript scripts.

It runs **on top of Claude Code** — there is no separate agent runtime. One Claude session plays each role sequentially when a slash command is invoked. The roles are prompt libraries, not independent agents.

## What code-crew is

code-crew is a standalone Python CLI that runs a **true multi-agent pipeline**: each of the 10 SDLC phases is a separate LLM call with its own agent, tool set, and model tier. Agents are wired together with typed context passing, not a shared conversation. It reads the organisation's own ADRs, ADDs, and SOPs as runtime knowledge, integrates with Jira as its work queue, and sends traces to Langfuse.

---

## Architecture comparison

| Dimension | gstack | code-crew |
|-----------|--------|-----------|
| Runtime | Claude Code session (slash commands) | Standalone Python CLI (CrewAI + Bedrock) |
| Agent model | One LLM plays sequential roles | Separate LLM call per agent, independent context |
| LLM provider | Anthropic API (Claude Code) | Amazon Bedrock (IAM auth, any Claude model) |
| Model tiers | Single model for all roles | fast / standard / powerful per agent |
| Instructions | Inline markdown prompts per role | External OKF docs (`knowledge/agents/`, `knowledge/tasks/`) |
| Domain knowledge | Generic best practices baked in | Organisation's own ADRs, ADDs, SDLC docs loaded at runtime |
| Work queue | None — human invokes per branch | Jira integration — `code-crew issue PROJ-NNN` fetches ticket + ACs |
| Observability | None | Langfuse OTLP traces (crew / task / agent / LLM spans) |
| Setup | 30 seconds, no infrastructure | AWS Bedrock + Jira + designs repo required |
| Parallel agents | No | Yes (TicketFlow runs tasks sequentially; CrewAI supports parallel process) |
| Browser QA | Yes — `/qa <url>` with real Chromium | No (planned post-launch-crew) |
| Scope | Individual developer shipping faster | Enterprise SDLC pipeline for a team |

---

## What gstack does better

**Zero-friction adoption.** One paste, one `git clone`, done. No AWS account, no Jira, no designs repo. A solo founder or new team member is running `/review` in under a minute.

**Browser QA.** `/qa <url>` opens a real Chromium session and drives the UI through acceptance scenarios. code-crew has no browser capability today.

**Product strategy layer.** `/office-hours` interrogates a feature idea with six forcing questions before any code is written — challenging scope, surfacing assumptions, recommending the narrowest wedge to ship. `/plan-ceo-review` challenges the plan from a business angle. code-crew starts at the Jira story; it has no pre-story intake layer.

**Community.** 111k stars means active contribution, fast bug fixes, community extensions, and many real-world examples. gstack's quality improves continuously from external contributors.

**Agent diversity.** 23+ roles including designer, devex reviewer, canary release manager, documentation generator — roles that don't exist in code-crew yet.

---

## What code-crew does better

**True multi-agent isolation.** The security reviewer doesn't see the backend developer's full reasoning — only its typed output. Context contamination between agents is eliminated by design. In gstack, all roles share a single Claude session and its accumulated context.

**Organisation's own knowledge.** When the tech lead does an architecture review, it reads *your* ADRs and ADDs, not generic guidance. The security reviewer reads ADD-035 (your file upload standards), not a built-in OWASP checklist. The DoD checker enforces *your* DoD document. gstack has no equivalent; its guidance is generic.

**Jira as the canonical work queue.** `code-crew issue PROJ-NNN` fetches the ticket, acceptance criteria, comments, and linked tickets. The sprint context is injected into every agent's task. There is no equivalent in gstack — the human copies and pastes context into the prompt.

**Bedrock + IAM auth.** No Anthropic API key required. AWS consolidated billing. Bedrock Guardrails for content policy. Private VPC endpoints available. gstack requires Claude Code and therefore an Anthropic subscription.

**Audit trail.** Every crew run produces Langfuse traces: which agent called which tool, what it returned, how many tokens were used, how long each task took. gstack produces no structured trace.

**Model tiers.** The security reviewer runs on Opus; the scrum master runs on Haiku. gstack uses whatever model Claude Code is configured with, uniformly.

---

## What code-crew will adopt from gstack

The `/office-hours` concept — product interrogation before the first Jira story is written — is genuinely valuable and has no equivalent today. This will become the **requirements-crew**: a separate crew that takes a raw idea or customer feedback and produces a structured Jira story with ACs, design doc references, and scope boundaries. (The name "office-hours" doesn't fit; the internal working name is "intake crew" or "requirements crew".)

Browser QA will be incorporated into a **post-launch-crew** or as a dedicated BDD integration test runner triggered after `dod_check`.

---

## Decision

code-crew and gstack are not substitutes. gstack is for a single developer who wants structured AI assistance in Claude Code. code-crew is an enterprise SDLC pipeline for a team using Jira, AWS, and an internal knowledge base. Using both simultaneously is coherent — gstack for ad-hoc exploration and interactive review within a Claude Code session; code-crew for the automated ticket-to-implementation pipeline. There is no adoption decision required: they target different moments in the workflow.

The one thing worth not doing: replacing code-crew's multi-agent architecture with gstack's single-session role prompts. The multi-agent isolation and organisation-specific knowledge loading are the core differentiators; collapsing them to a prompt library would lose both.
