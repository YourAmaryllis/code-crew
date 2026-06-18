# tools — YourAmaryllis Virtual AI Development Team

This repo contains CrewAI-based multi-agent crews for YourAmaryllis's engineering workflow.

## Structure

```
code/           # Code crew: feature delivery (SDLC phases 13-19)
  knowledge/    #   OKF agent + task definitions for the code crew
ops/            # Ops crew: infrastructure, release, monitoring
  knowledge/    #   OKF agent + task definitions for the ops crew
shared/         # Shared OKF loader, Bedrock LLM factory, CrewAI tools
designs/        # Git submodule → YourAmaryllis/designs (SOPs, ADRs, ADDs — all OKF)
scripts/        # Utility scripts (OKF conversion, etc.)
```

## Key principles

- **No hardcoded prompts** — all agent/task instructions are OKF `.md` files in `*/knowledge/`
- **Self-contained** — `knowledge/` embeds all SOPs/ADRs/ADDs/DoD; no runtime dep on `designs/` or `../platform/`
- **IAM auth only** — Bedrock uses instance profile / AWS_PROFILE, never hardcoded keys
- **Human review gate** — crew output is text for review; agents don't push, apply, or promote autonomously

## Running the crews

```bash
# Install
pip install -e .

# Code crew
code-crew --jira LOOPLAT-72 --story "..." --ac "..." --sprint-goal "..." [--figma <url>]

# Ops crew
ops-crew --jira LOOPLAT-55 --description "..." --service portal --env staging
```

## OKF documents (designs/ submodule)

All SOPs, ADRs, and ADDs in `designs/` are OKF format (YAML frontmatter + markdown body).
The `SOPReaderTool` loads them directly from `designs/SOP/`, `designs/ADR/`, `designs/ADD/` at crew startup.

To add frontmatter to a new file without it:
```bash
python scripts/convert_designs_to_okf.py --dry-run   # preview
python scripts/convert_designs_to_okf.py              # apply
```

The DoD is canonical at `designs/SOP/SOP-DoD-Definition-of-Done.md`.

## Tool environment

Required env vars (copy `.env.example` → `.env`):
- `BEDROCK_MODEL_ID`, `BEDROCK_FAST_MODEL_ID`, `BEDROCK_REGION`
- `PLATFORM_PATH` — path to `YourAmaryllis/platform` monorepo (default: `../platform`)
- `JIRA_PROJECT` — Jira project key (default: `LOOPLAT`)

## Adding/editing agents

Agent behavior is in `code/knowledge/agents/<name>.md` or `ops/knowledge/agents/<name>.md`.
Edit the `.md` file — no Python changes needed. OKF frontmatter fields:
- `role`, `goal` — passed directly to CrewAI Agent
- `tools` — documentation only; actual tools wired in `crew.py`
- Body (markdown) → agent `backstory`

## designs/ submodule

The `designs/` submodule is the canonical source for ADRs, ADDs, and SOPs.
All files in `designs/` use OKF format (YAML frontmatter + markdown body).
To convert files without frontmatter: `python scripts/convert_designs_to_okf.py`
