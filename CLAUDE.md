# tools — Virtual AI Development Team

CrewAI-based multi-agent crew for software engineering workflows.
Agent definitions are in `code_crew/knowledge/agents/`: scrum master, architect, engineer (full-stack), QA lead, product owner, security lead, DevOps lead, and release engineer.

## Structure

```
code_crew/      # Code crew: feature delivery
  knowledge/    #   OKF agent + task definitions (edit these to customise behaviour)
    agents/     #   One .md per agent — role, goal, backstory
    tasks/      #   One .md per task — description, expected_output
    prompts/    #   Standalone LLM prompts (e.g. Jira extraction)
ops/            # Ops crew: infrastructure, release, monitoring
  knowledge/    #   OKF agent + task definitions
shared/         # Shared OKF loader, Bedrock LLM factory, CrewAI tools
scripts/        # Utility scripts (OKF conversion, etc.)
docs/
  add/          #   Architecture design documents for code-crew itself
  adr/          #   Architecture decision records for code-crew itself
  sad/          #   System architecture description
  plan/         #   Roadmap and planning docs
  eval/         #   Evaluation notes
```

## Key principles

- **No hardcoded prompts** — all agent/task instructions are OKF `.md` files in `*/knowledge/`
- **designs/ in your platform repo** — add as a git submodule so design doc changes appear in your PR diff
- **IAM auth only** — Bedrock uses instance profile / AWS_PROFILE, never hardcoded keys
- **Human review gate** — crew output is for human review; agents never push to main, apply Terraform, or promote to production autonomously

## Knowledge files — no project-specific content

**This rule is mandatory and has caused repeated bugs. Read it before editing any file under `*/knowledge/`.**

Knowledge files (`*/knowledge/agents/*.md`, `*/knowledge/tasks/*.md`, `*/knowledge/prompts/*.md`) are generic — they ship with the tool and apply to any user's project. They must never contain:

- **Company or product names** — no "LooporaData", "Panome", "portal", "attestation", "fhir_proxy", or any other project-specific service name
- **Hardcoded file paths** — no `designs/SAD/SAD-3-Decomposition-View.md`, `portal/backend/internal/api/`, or any path that only exists in one project
- **Hardcoded directory structures** — no example tables listing specific services; use `<service>`, `<dir>`, `<component>` placeholders
- **Project-specific compliance assumptions** — no "HIPAA confirmed in `designs/SOP/...`"

**When referring to design documents:** say "the system architecture doc (SAD)" or "the ADD docs" — never a specific path like `designs/SAD/` or `designs/ADD/`. The agent reads the filesystem and finds the actual files.

**When referring to infrastructure:** say "the infrastructure directory (Terraform, CDK, etc.)" — never `ops/` or any project-specific directory name.

**When referring to source files by name:** use stack-agnostic descriptions, not language-specific filenames:
- Wrong: "`go.mod`", "`main.go`", "`cmd/server/main.go`", "`index.ts`"
- Right: "the dependency manifest", "the service entry point"
- If you need a language example, list multiple: "`go.mod` / `package.json` / `requirements.txt`"

**Examples in task templates** must use generic placeholders: `<service>/internal/api/<handler>`, not `portal/backend/internal/api/register_validation.go`.

**The LooporaData platform repo (`fhir_proxy`, `portal`, `designs/`, `ops/`) is a test project — nothing from it belongs in knowledge files.** If you find yourself typing any of those names, stop and generalise.

## Knowledge architecture

Knowledge files form a hierarchy. Every layer must be generic — no project names,
no language-specific filenames, no tool-specific commands (those go in stacks).

```
knowledge/
  agents/     — WHO the agent is: role, philosophy, values, key constraints.
                Generic about the role. No workflow steps. No tool-calling sequences.
                The Security Lead's agent file describes their security mindset,
                not what they do in a code review vs. a threat model engagement.

  functions/  — WHAT the smallest unit of work is. Reusable by multiple agents.
                Generic principles: "check the dependency manifest for known CVEs" —
                not "run `npm audit`". The exact command lives in the tech stack.
                Functions are combined by tasks.

  tasks/      — HOW a complete workflow is executed. Uses multiple functions.
                Describes phase sequencing, delegation, and expected output.
                Can be used by multiple agents (e.g. architect + security lead
                both use threat-model tasks).

  stacks/     — TECHNOLOGY-SPECIFIC details. Functions and tasks reference stacks
                for exact commands, file names, and tool-specific behaviour.
                Examples: go-backend.md → `go.mod`, `go test ./...`
                          jira.md → `jira_view` tool, key format <PROJECT>-NNN
                          linear.md → Linear API, issue ID format

  prompts/    — Standalone LLM prompts. Not tied to an agent or task.
```

### Rules for each layer

**Agents** — Describe who they are. Do NOT embed workflow steps (those belong in tasks).
If an agent's backstory tells it to "read the Jira ticket first", that step leaks into
every task that agent performs — including threat modeling where there is no Jira ticket.

**Functions** — The smallest reusable unit. Say what to do conceptually; reference a
tech stack for the exact command. A `db-schema` function says "run the migration tool
on startup"; the `goose` stack says the exact `goose up` command.

**Tasks** — Chain functions for a specific workflow. The `threat_model` task uses
threat-model functions. The `security_review` task uses security-code-review functions.
Tasks load only the functions and stacks they actually need.

**Stacks** — One file per technology or external tool. `jira.md` describes Jira-specific
behaviour; `linear.md` describes Linear. Tasks and functions refer to "the issue tracker
stack" generically; the loaded stack provides the actual commands.

### Issue tracker support

Issue tracking (Jira, Linear, GitHub Issues) is a **tech stack**, not an agent concern.
Configure `issue_tracker.type` in `~/.code-crew/config.yaml` (`jira` | `linear` | `github`).
Agent and function files must say "issue tracker" — never name a specific tool.
Jira-specific commands (`jira_view`, key format) live in `stacks/jira.md` only.

### What NOT to do

- Do NOT put `go.mod`, `main.go`, or any language-specific filename in an agent file
- Do NOT name a specific issue tracker (`Jira`, `Linear`) in agents or functions
- Do NOT embed step-by-step workflow instructions in an agent's backstory
- Do NOT put tech-stack commands in function files — reference the stack instead

## Quick start

```bash
# 1. Install
pip install -e .

# 2. Configure
cp .config.example.yaml ~/.code-crew/config.yaml
# Edit: set bedrock.model_id, bedrock.region, issue_tracker

# 3. Add designs/ as a submodule in your platform repo (preferred)
cd /path/to/your-platform-repo
git submodule add git@github.com:your-org/designs.git designs
code-crew run --jira YOUR-123     # auto-detects ./designs/

# Or run /init to create a blank designs directory for a new project

# Memory
code-crew memory add "staging DB migrated to RDS" --category env
code-crew memory list
```

## Knowledge repo (designs/)

The crew loads your project's SOPs, ADDs, and ADRs from `designs/`:

```
designs/SOP/*.md
designs/ADR/*.md
designs/ADD/*.md
designs/TMD/    ← OTM threat model files (auto-generated by /explore)
```

**Preferred setup — submodule in your platform repo:**
```bash
cd /path/to/your-platform-repo
git submodule add git@github.com:your-org/designs.git designs
```
Run `code-crew` from the platform repo root — it finds `./designs/` automatically.
Design doc changes appear in `git diff` alongside code changes for unified review.

**Override path** (explicit): set `designs.path` in `~/.code-crew/config.yaml`.

All files must be in **OKF format** (YAML frontmatter + markdown body). To add frontmatter:
```bash
python scripts/convert_designs_to_okf.py --dry-run   # preview
python scripts/convert_designs_to_okf.py              # apply
```

**Definition of Done** defaults to `designs/SOP/SOP-DoD-Definition-of-Done.md`.
Override with `designs.dod_path` in config.

## Configuration

Config is structured YAML at `~/.code-crew/config.yaml` (see `.config.example.yaml`).

Key settings:

| Section | Key | Purpose |
|---------|-----|---------|
| `bedrock` | `model_id`, `region` | Bedrock model and region |
| `aws` | `profile` | AWS profile (if not using instance profile or ECS role) |
| `designs` | `path`, `dod_path` | Designs directory — auto-detected from `./designs/` if absent |
| `issue_tracker` | `type`, `project_key` | Issue tracker: `jira`, `linear`, or `github` |
| `flow` | `max_retries`, `max_run_minutes` | Gate retry limit; max crew run time (default 30 min) |

Named profiles: `~/.code-crew/profiles/<name>.yaml` — switch with `/profile <name>` in REPL.

## Customising agent behaviour

All agent instructions are in `code_crew/knowledge/agents/<name>.md`. Edit the `.md` — no Python changes needed.

OKF frontmatter fields used:
- `role`, `goal` — passed directly to CrewAI Agent
- `tools` — documentation only; actual tool wiring is in `crew.py`
- Body (markdown) → agent `backstory`

## Adding/editing tasks

Task definitions are in `code_crew/knowledge/tasks/<name>.md`. The task description and expected output are loaded at crew startup.

Task sequence:
```
sprint_planning_check → architecture_review → scaffold_code → scaffold_test
→ [BDD cycle] bdd_test_authoring → bdd_po_review + bdd_arch_review → bdd_finalization
  (repeats until PO + Architect both approve)
→ implementation → devops_coordination → cleanup
→ [review gates] code_review → security_review → compliance_review → dod_check
  (each gate failure retries implementation + devops_coordination + cleanup)
→ release_notes
→ [staging loop] promote_staging → staging_verification
  (agents use async_job tool: type=gh_actions for workflows, type=ecs for direct updates,
   type=shell for BDD suites — returns RUN_HANDLE: line, flow suspends)
  (REPL polls via /loop or /resume; resumes when job completes)
→ launch_decision   (Release Engineer go/no-go; LAUNCH BLOCKED retries or escalates)
→ [human gate: workflow_dispatch / GitLab manual job → production]
→ smoke_test   (same async_job pattern)
```

Threat model task sequence (`/threat`):
```
threat_discover  (Architect: reads codebase + infra, outputs trustZones + components)
→ [per-component, parallel] threat_component_threats × N  (Security Lead per component)
→ [per-component, parallel] threat_mitigations × N        (Security Lead per component)
→ [Python assembly: renumber IDs, write initial OTM YAML to disk]
→ [refinement passes × max_refine_passes (default 2)]
    threat_refine  (Security Lead: reads full OTM, outputs additional_threats + additional_mitigations)
    → Python merges additions, renumbers, overwrites OTM
    → stops early on NO NEW THREATS signal
→ threat_gate    (Manager: completeness check — zone semantics, framework coverage, mitigation state)
    NEEDS REVISION → threat_patch → threat_gate  (retries gate only, not prior phases)
    THREAT MODEL APPROVED → write final OTM + export Threat Dragon JSON

/threat refine [N]  — manual: runs N additional refinement passes on the existing OTM on disk
```

## Execution model: manager-worker

Tasks that require writing to files or running commands use `Process.hierarchical` with a
fast manager LLM. The manager drives the worker until work is genuinely done — not just
planned. Review and evaluation tasks run sequentially (no manager needed).

| Mode | Tasks | Model |
|------|-------|-------|
| `manager → worker` | scaffold_code, scaffold_test, bdd_authoring, bdd_finalization, implementation, devops_coordination, release_notes, promote_staging, staging_verification, smoke_test | fast manager + standard/powerful worker |
| sequential | sprint_planning, architecture_review, bdd_po_review, bdd_arch_review, cleanup, code_review, security_review, compliance_review, dod_check, launch_decision | worker only |

To move a task between modes, edit the `MANAGED_TASKS` frozenset in `crew.py`.

## Design decisions

Decision docs live in `docs/adr/` (why) and `docs/add/` (how) — these are about code-crew itself, not knowledge for agents.

Key ADDs:
- `docs/add/ADD-001-Virtual-AI-Development-Team.md` — overall system design
- `docs/add/ADD-006-OKF-Knowledge-Architecture.md` — agent/task/function/stack knowledge hierarchy
- `docs/add/ADD-007-Server-Mode-IM-Adapters.md` — Slack/Teams server mode
- `docs/add/ADD-008-Incremental-Per-Unit-LLM-Decomposition.md` — pattern for unbounded tasks (threat modeling, code review)
- `docs/add/ADD-009-Parallel-Crew-Execution.md` — parallel per-unit execution via asyncio + combined single-pass tasks
- `docs/add/ADD-010-Guardrails-Destructive-Operations.md` — guardrails on git push, terraform apply, rm -rf, and other irreversible ops
- `docs/add/ADD-011-Multi-Pass-Threat-Model-Refinement.md` — multi-pass refinement for cross-component and boundary-crossing threats

Key ADRs:
- `docs/adr/ADR-001-CrewAI-Multi-Agent-Architecture.md` — why CrewAI
- `docs/adr/ADR-003-Async-Wait-Points.md` — async wait points for deploy and BDD phases (`/loop` pattern)
- `docs/adr/ADR-007-Python-Flow-Orchestration.md` — Python as the outer loop controller
- `docs/adr/ADR-009-Parallel-Per-Unit-Agent-Execution.md` — why parallel + combined threats/mitigations

## Git push

This repo belongs to the `arthurtsang` GitHub account. The default active `gh` account is `arthur-loopora`, which does not have push access. To push commits:

```bash
gh auth switch --user arthurtsang
git push
gh auth switch --user arthur-loopora   # always switch back afterwards
```

## README maintenance rule

**Keep `README.md` current.** After every feature addition, command rename, config change, or new agent/flow:

1. Update the slash commands table if a command was added, renamed, or removed
2. Update the agents table if a new agent was added or model tier changed
3. Update the config example if new YAML sections or keys were added
4. Update the structure block if new top-level dirs or knowledge subdirs were created
5. Update the quick start if the setup steps changed

The README is the single source of truth for what `code-crew` can do. If a feature exists and the README doesn't mention it, it doesn't exist for users.
