# ADD-004: Startup Checks and /fix Command

**Status:** Accepted
**Date:** 2026-07-03
**Related:**
- [SAD-001: code-crew system architecture](../sad/SAD-001-code-crew.md)
- [ADD-002: /init, /explore, and /verify commands](ADD-002-Init-Explore-Verify.md)

---

## Purpose

When a developer runs `code-crew` in a new environment or project, they may be missing required tools (CLI binaries), misconfigured credentials, or pointing at a non-existent designs directory. A silent failure — the run starts, an agent calls `gh` and gets "command not found" — is worse than an upfront check with actionable fix instructions.

The startup check system runs before any flow and:
1. Identifies what is missing or misconfigured
2. Provides an exact shell command to fix each issue
3. Exposes `/fix` to auto-run all fixable commands

---

## Check Inventory

Startup checks run via `startup.run_checks()` before the REPL accepts any command. Each check produces a `CheckResult(name, ok, detail, fix)`.

### Git repository
- Checks: `git rev-parse --abbrev-ref HEAD` in cwd
- Ok: branch name + dirty/clean status
- Fix: `run /init to scaffold a new project`
- Category: **error** (flows require git)

### Required CLI tools
Required CLIs are derived dynamically from two sources:
1. **Detected stacks** — stack OKF files declare `metadata.required-cli` entries
2. **Detected CI/CD methods** — mapped to CLI tools:

| CI method | Required CLIs |
|-----------|--------------|
| `github-actions` | `gh` |
| `gitlab-ci` | `glab` |
| `docker-compose` | `docker` |
| `aws-cdk` | `cdk`, `aws` |
| `pulumi` | `pulumi` |
| `fly-io` | `fly` |
| `vercel` | `vercel` |
| `terraform` | `terraform` |

`gh` is always checked if github-actions is detected or no CI method is detected (safe default). `aws` is always checked if any configured LLM tier resolves to Bedrock.

### ast-grep (optional)
- Structural AST search used by engineer and architect agents for precise code navigation
- Checks both `ast-grep` and `sg` binary names
- Category: **optional** — agents fall back to `grep` if absent
- Fix: `brew install ast-grep` (macOS) or `cargo install ast-grep`

### Langfuse (optional)
- Checks `LANGFUSE_PUBLIC_KEY` presence; if set, probes credentials via REST API
- Category: **optional** — no tracing if absent, but the run still works
- Fix: check `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST`

### Designs directory (optional)
- Checks `DESIGNS_PATH` env var or `./designs/` in cwd
- Category: **optional** — agents continue with a warning; knowledge_reader returns empty
- Fix: `run /fix to configure one`

---

## Fix Command

`/fix` iterates all failed checks and runs each `fix` shell command.

Three fix categories:

| Category | Behaviour | Examples |
|----------|-----------|---------|
| Auto-run | Run silently; report success/failure | `pip install awscli`, `go install github.com/cli/...`, `npm i -g vercel` |
| Prompt | Show command; ask before running (auth step needed) | `gh auth login`, `glab auth login` |
| URL hint | Print instructions; cannot be auto-run | Docker Desktop download, manual platform installers |

Install hint selection:
- Cross-platform package managers first: `pip install` (Python tools), `go install` (Go tools), `npm i -g` (Node tools)
- `brew install` when Homebrew is on PATH (macOS common path)
- URL hint fallback for tools with no reliable single-command install

---

## Stack Detection

Stack detection runs at startup and is used by: check system (to derive required CLIs), `/explore` (to initialise context), `_format_context()` (to inject architecture style into every task).

Resolution order:
1. `CODE_CREW_STACKS` env var — explicit override (comma-separated)
2. `stacks:` in `.code-crew/config.yaml` — project declaration
3. Profile stacks (`_CODE_CREW_STACKS_PROFILE`) — from loaded profile
4. Auto-detection from file signals:

| Signal | Stack |
|--------|-------|
| `go.mod` | `go-backend` |
| `package.json` | `typescript-react` |
| `pyproject.toml` or `setup.py` | `python` |
| `*.tf` in root or `terraform/` | `terraform-aws` |

---

## CI Method Detection

Resolution order:
1. `ci.deployment_methods` list in `.code-crew/config.yaml`
2. File-based auto-detection:

| Signal | Method |
|--------|--------|
| `.github/workflows/*.yml` | `github-actions` |
| `.gitlab-ci.yml` | `gitlab-ci` |
| `Jenkinsfile` | `jenkins` |
| `docker-compose.yml/yaml` | `docker-compose` |
| `cdk.json` | `aws-cdk` |
| `pulumi.yaml` | `pulumi` |
| `fly.toml` | `fly-io` |
| `vercel.json` or `.vercel/` | `vercel` |
| `*.tf` or `ops/modules/**/*.tf` | `terraform` |

---

## Startup Banner

The REPL startup banner renders check results in a table:

```
✓ git repo        main (dirty)
✓ gh              /usr/local/bin/gh
✓ aws             /usr/bin/aws
✗ golangci-lint   → go install github.com/golangci/golangci-lint/...
✓ langfuse        us.cloud.langfuse.com
✓ designs         ./designs
```

Errors (git) block operation. Warnings (missing CLIs) do not block but are surfaced. Optional checks (langfuse, designs, ast-grep) show status but never block.

---

## Key Files

| File | Purpose |
|------|---------|
| `code_crew/startup.py` | `run_checks()`, `detect_stacks()`, `detect_ci_methods()`, `CheckResult`, `StartupSummary` |
| `code_crew/repl.py` | Renders startup banner, implements `/fix` command |
| `shared/telemetry.py` | `setup_langfuse()` — called by `_check_langfuse()` |
