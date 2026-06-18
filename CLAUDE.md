# tools — Virtual AI Development Team

CrewAI-based multi-agent crew for software engineering workflows.
Agents cover the full SDLC: sprint planning, architecture, BDD, backend, frontend, code review, security, and DoD gate.

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
designs/        # YOUR knowledge repo — not tracked here (see DESIGNS_PATH below)
```

## Key principles

- **No hardcoded prompts** — all agent/task instructions are OKF `.md` files in `*/knowledge/`
- **Bring your own knowledge repo** — SOPs, ADRs, ADDs live in your own git repo, loaded at runtime via `DESIGNS_PATH`
- **IAM auth only** — Bedrock uses instance profile / AWS_PROFILE, never hardcoded keys
- **Human review gate** — crew output is for human review; agents never push to main, apply Terraform, or promote to production autonomously

## Quick start

```bash
# 1. Install
pip install -e .

# 2. Configure
cp .env.example .env
# Edit .env: set BEDROCK_*, DESIGNS_PATH (or DESIGNS_REPO), PLATFORM_PATH, JIRA_PROJECT

# 3. Run
code-crew run --jira YOUR-123
ops-crew --jira YOUR-55 --description "..." --service portal --env staging

# Memory
code-crew memory add "staging DB migrated to RDS" --category env
code-crew memory list
```

## Knowledge repo (DESIGNS_PATH)

The crew loads your project's SOPs, ADDs, and ADRs at startup from:
```
$DESIGNS_PATH/SOP/*.md
$DESIGNS_PATH/ADR/*.md
$DESIGNS_PATH/ADD/*.md
```

All files must be in **OKF format** (YAML frontmatter + markdown body). To add frontmatter to existing docs:
```bash
python scripts/convert_designs_to_okf.py --dry-run   # preview
python scripts/convert_designs_to_okf.py              # apply
```

**Option A — local checkout** (already have the repo):
```
DESIGNS_PATH=/path/to/your/designs
```

**Option B — auto-clone** (first run clones it):
```
DESIGNS_PATH=./designs
DESIGNS_REPO=git@github.com:your-org/designs.git
DESIGNS_BRANCH=main
```

**Definition of Done** defaults to `$DESIGNS_PATH/SOP/SOP-DoD-Definition-of-Done.md`.
Override with `DOD_PATH` (absolute or relative to `DESIGNS_PATH`).

## Environment variables

Required:
- `BEDROCK_MODEL_ID`, `BEDROCK_FAST_MODEL_ID`, `BEDROCK_REGION`
- `DESIGNS_PATH` — path to your knowledge repo
- `PLATFORM_PATH` — path to the codebase the crew works on
- `JIRA_PROJECT` — Jira project key

Optional:
- `DESIGNS_REPO` — git URL for auto-clone if `DESIGNS_PATH` doesn't exist
- `DESIGNS_BRANCH` — branch to clone (default: `main`)
- `DOD_PATH` — path to your DoD file (default: `SOP/SOP-DoD-Definition-of-Done.md`)
- `AWS_PROFILE` — AWS profile name
- `BEDROCK_GUARDRAIL_ID` — Bedrock Guardrails ID

## Customising agent behaviour

All agent instructions are in `code_crew/knowledge/agents/<name>.md`. Edit the `.md` — no Python changes needed.

OKF frontmatter fields used:
- `role`, `goal` — passed directly to CrewAI Agent
- `tools` — documentation only; actual tool wiring is in `crew.py`
- Body (markdown) → agent `backstory`

## Adding/editing tasks

Task definitions are in `code_crew/knowledge/tasks/<name>.md`. The task description and expected output are loaded at crew startup.

Task sequence: `sprint_planning_check → architecture_review → scaffold_code → scaffold_test → bdd_test_authoring → backend_implementation → frontend_implementation → code_review → security_review → dod_check`
