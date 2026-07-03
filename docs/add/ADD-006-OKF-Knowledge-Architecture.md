# ADD-006: OKF Knowledge Architecture — Agents, Tasks, and Functions

**Status:** Accepted
**Date:** 2026-07-03
**Related:**
- [ADR-007: Python flow orchestration](../adr/ADR-007-Python-Flow-Orchestration.md)
- [SAD-001: code-crew system architecture](../sad/SAD-001-code-crew.md)

---

## Purpose

The most common failure mode in multi-agent systems is **context overload**: every agent gets the full knowledge base, which wastes tokens, dilutes focus, and increases hallucination risk. The second most common failure mode is **hardcoded prompts**: agent instructions embedded in Python that can't be reviewed by domain experts, can't be diffed in git, and require a code deploy to change.

The OKF (Open Knowledge Format) system solves both problems:
1. Agent instructions are **documents** (markdown files), not strings in Python
2. Each agent receives **only the knowledge relevant to its current task** — nothing more

---

## File Structure

```
code_crew/knowledge/
  agents/          One .md per agent — what the agent IS
  tasks/           One .md per task — what the task REQUIRES
  functions/       Process guides — HOW to do specific things
  stacks/          Stack-specific context — injected when stack is active
  skills/          Style modifiers — injected when skill is activated
  prompts/         Standalone LLM prompts (extraction, classification)
  index.md         Human-readable index for navigation
```

---

## OKF Format

All knowledge files use YAML frontmatter + markdown body:

```markdown
---
name: engineer
role: Full-stack Software Engineer
goal: Implement features from BDD scenarios following the codebase's architecture and conventions
model: standard
tools: [knowledge_reader, workspace_reader, code_index, api_spec, platform_shell, python_repl, ask_human]
---

You are an experienced full-stack software engineer embedded in a team's SDLC...
[body becomes the agent backstory]
```

For tasks:
```markdown
---
name: implementation
description: |
  Implement the feature defined by the BDD scenarios. Read the acceptance criteria,
  read the scaffold code, write implementation code, run unit tests. ...
expected_output: |
  IMPLEMENTATION COMPLETE
  FILES CHANGED:
  - path/to/file1.py
  - path/to/file2.py
  ...
---
```

No prompt text appears in Python code. Python reads OKF files and passes structured fields to CrewAI constructors.

---

## Agents vs Tasks vs Functions

| Layer | File | What it defines | When loaded |
|-------|------|----------------|------------|
| Agent | `agents/<name>.md` | Role, goal, backstory (who), model tier, tool list (metadata) | Once at `build_agents()` call |
| Task | `tasks/<name>.md` | Description (what to do), expected output (what to return) | Once at `build_tasks()` call |
| Function | `functions/<name>.md` | Process guide (HOW to do a class of work) | On demand — agent calls `KnowledgeReaderTool` |

**The key separation**: agents know their role but not the process details. Tasks know what is required but not how to execute. Functions contain the how — and are loaded only when an agent needs them for a specific task.

Example: the engineer agent's backstory says "read the coding standards function guide before implementing". The coding standards themselves are in `functions/coding-standards.md`. The engineer reads them via `knowledge_reader` during `implementation` — not during `scaffold_code` or `bdd_test_authoring` where they're irrelevant.

---

## Context Assembly

Every task description starts with a context block built by Python (via `_format_context()`), then the task's OKF `description` field is appended.

```
[Active skills content — if CODE_CREW_SKILLS is set]

## Sprint context
**Issue key**: PROJ-123
**Story**: <summary>
**Acceptance criteria**: ...
**Designs directory**: ./designs
**Architecture pattern**: clean — load stacks/arch-clean.md via knowledge_reader

## Project structure
<.code-crew/structure.md content>

[upstream task outputs — via Task.context= parameter]

## [Task OKF description]
```

What the agent does NOT receive:
- Other agents' system prompts or goals
- Task descriptions for tasks it is not running
- Function documents it has not explicitly requested
- Stack knowledge for inactive stacks
- Skills it has not activated

---

## Functions — On-Demand Process Knowledge

Functions are SDLC process guides. They are NOT pre-loaded. The agent decides whether to read them:

| File | Contents |
|------|---------|
| `functions/bdd-authoring.md` | Gherkin scenario structure, Given/When/Then conventions, tagging |
| `functions/coding-standards.md` | Language-specific coding conventions, naming, error handling |
| `functions/definition-of-done.md` | DoD checklist template |
| `functions/db-schema.md` | Migration naming, no-edit-applied rule, schema review |
| `functions/api-standards.md` | OpenAPI 3.1 structure, versioning, error schema |
| `functions/security-privacy.md` | OWASP ASVS controls, threat modelling basics |
| `functions/compliance-evidence.md` | Evidence requirements per compliance standard |
| `functions/threat-dragon.md` | OTM format, IriusRisk import, PLOT4ai requirements |
| `functions/domain-methodologies/` | DDD, event-storming, C4 process guides |
| ... | (30+ function docs covering all SDLC phases) |

`KnowledgeReaderTool` resolves relative paths against `DESIGNS_PATH` — the organisation's `designs/` repo. This means agents read the *organisation's own* process documents (their actual DoD, their actual ADRs), not generic bundled guidance.

If `designs/` is unavailable, `KnowledgeReaderTool` returns an empty result — the agent continues with its backstory knowledge alone (graceful degradation).

---

## Stacks — Automatic Context Injection

Stack OKF files (`stacks/<name>.md`) are automatically prepended to every task context when a stack is active. Unlike functions (agent-requested), stack content is injected by Python before the task runs.

Active stacks: `CODE_CREW_STACKS` env var → project config → auto-detected from file signals.

| Stack | What it adds to every task |
|-------|---------------------------|
| `go-backend` | Go coding standards, module layout, error handling patterns, linting rules |
| `typescript-react` | React component patterns, TypeScript strict mode, A11y requirements |
| `python` | Python conventions, type hints, ruff/mypy config |
| `terraform` / `terraform-aws` | Terraform style, AWS naming, module patterns |
| `bdd-testing` | Gherkin conventions, scenario structure, tagging requirements |
| `hipaa` / `gdpr` / `soc2` | Regulatory requirements injected into compliance and security tasks |
| `owasp` | OWASP ASVS L2 controls checklist |
| `ai-ml` | OWASP LLM Top 10 + PLOT4ai mandatory coverage |
| `arch-clean` / `arch-hexagonal` / `arch-onion` | Architecture layer rules (auto-detected by `/explore`) |

Stacks keep per-task context focused: a security review on a Python + HIPAA project gets Python coding standards and HIPAA requirements automatically; it does not get Go conventions or Terraform module patterns.

---

## Skills — Output Style Modifiers

Skills (`skills/<name>.md`) modify how agents express their output, not what they check. They are injected at the top of every task context when active (before the sprint context block).

| Skill | Effect |
|-------|--------|
| `terse` | Verdict first, bullet findings, no filler prose |
| `strict` | OWASP ASVS L3, explicit evidence per gate item |
| `explain` | Every decision includes WHY + alternatives considered |
| `dry-run` | `WOULD RUN` / `WOULD WRITE` preview mode — no file writes |

Skills are session-scoped. `/skill <name>` activates; `/skill off` deactivates. Skills compose — multiple skills can be active simultaneously.

Search path (priority order): `.code-crew/skills/` (project) → `~/.code-crew/skills/` (user) → `knowledge/skills/` (bundled).

---

## Per-Agent Tool Assignment

Agents receive only the tools relevant to their role. No agent has access to tools it does not need.

| Agent | Tools |
|-------|-------|
| `scrum_master` | knowledge_reader, dod_checker, issue_view, memory_tool |
| `architect` | knowledge_reader, workspace_reader, code_index, issue_view, platform_shell, ask_human |
| `engineer` | knowledge_reader, workspace_reader, code_index, api_spec, issue_view, platform_shell, python_repl, ask_human |
| `qa_lead` | knowledge_reader, workspace_reader, issue_view, platform_shell, bdd_runner, python_repl, ask_human, async_job |
| `security_lead` | knowledge_reader, workspace_reader, platform_shell, python_repl |
| `compliance_officer` | knowledge_reader, workspace_reader, issue_view |
| `product_owner` | knowledge_reader, issue_view |
| `devops_lead` | knowledge_reader, workspace_reader, issue_view, platform_shell, python_repl, async_job |
| `release_engineer` | knowledge_reader, workspace_reader, issue_view, platform_shell |
| `ux_lead` | figma_reader, knowledge_reader, workspace_reader, ask_human |

MCP server tools are added on top of the base tool list for any agent listed in the MCP server's `agents:` config.

---

## OKF Loader

`shared/okf_loader.py` parses OKF markdown into `AgentConcept` / `TaskConcept` structs:

```python
@dataclass
class AgentConcept:
    name: str
    role: str
    goal: str
    backstory: str    # markdown body, stripped of frontmatter
    model: str        # tier name: "fast", "standard", "powerful"

@dataclass
class TaskConcept:
    name: str
    description: str
    expected_output: str
```

`load_bundle_agents(dir)` and `load_bundle_tasks(dir)` return dicts keyed by file stem. Python passes the fields directly to CrewAI `Agent()` and `Task()` constructors.

---

## Key Files

| File | Purpose |
|------|---------|
| `shared/okf_loader.py` | Parses OKF markdown into AgentConcept / TaskConcept |
| `code_crew/crew.py` | `build_agents()`, `build_tasks()`, `_format_context()` — assembles crews from OKF |
| `code_crew/knowledge/agents/` | One .md per agent |
| `code_crew/knowledge/tasks/` | One .md per task |
| `code_crew/knowledge/functions/` | 30+ process guide docs |
| `code_crew/knowledge/stacks/` | Stack-specific context |
| `code_crew/knowledge/skills/` | Style modifier skills |
| `shared/tools/workspace_reader.py` | `WorkspaceReaderTool` — bounded file access |
| `shared/tools/knowledge_reader.py` | `KnowledgeReaderTool` — resolves against DESIGNS_PATH |
