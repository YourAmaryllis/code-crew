# ADD-010: Guardrails on Destructive and Irreversible Operations

**Status:** Proposed  
**Date:** 2026-07-04  
**Related:**
- [ADR-001: CrewAI Multi-Agent Architecture](../adr/ADR-001-CrewAI-Multi-Agent-Architecture.md)
- [ADD-001: Virtual AI Development Team](ADD-001-Virtual-AI-Development-Team.md)

---

## Purpose

Define guardrails that prevent agents from executing destructive or hard-to-reverse operations without explicit verification. The primary risk is an agent making a correct-looking but wrong-target action — pushing to `main` instead of the feature branch, deleting a file that is still referenced, or deploying to production instead of staging.

---

## Problem

Agents are good at sequencing tasks but do not natively distinguish between "correct action" and "correct action on the correct target." An engineer agent that writes code and then pushes it may push to the wrong branch if the branch context is ambiguous or if the LLM infers the target from prior context rather than verifying it.

Failure modes observed:
- Push to `main` instead of feature branch
- Deploy to production environment instead of staging
- Delete a file that is imported elsewhere
- Apply Terraform to the wrong workspace
- Overwrite a migration that has already been applied

These failures are asymmetric: easy to do, hard to undo.

---

## Design

### Two layers of guardrails

**Layer 1 — Task-level guardrails (CrewAI built-in)**

CrewAI tasks accept a `guardrail` callable `(output) → (bool, str)`. Use this to validate the agent's proposed action before it executes:

```python
def _guardrail_git_push(output: TaskOutput) -> tuple[bool, str]:
    text = output.raw
    for branch in config.guardrails.protected_branches:
        if f"push origin {branch}" in text or "push --force" in text:
            return False, (
                f"Refused: push targets protected branch '{branch}'. "
                f"Push to the feature branch instead."
            )
    return True, text
```

Apply to: `scaffold_code`, `implementation`, `devops_coordination`, `promote_staging` tasks.

**Layer 2 — Tool-level intercepts**

The `platform_shell` tool checks every command against a blocklist before execution. A blocked command returns an error string instead of running — the agent sees it as a tool failure and must revise.

```python
_BLOCKED_PATTERNS = [
    (r"git push\s+\S*\s+(main|master|release|production)\b", "push to protected branch"),
    (r"git push.*--force", "force push"),
    (r"terraform apply(?!.*-target.*staging)", "terraform apply outside staging target"),
    (r"\brm\s+-rf\b", "recursive delete"),
    (r"\bDROP\s+TABLE\b", "database table drop"),
    (r"git\s+commit.*--no-verify", "skip pre-commit hooks"),
]
```

---

## Guardrail categories

| Category | Operations | Layer |
|---|---|---|
| **Branch protection** | `git push` to main/master/release | Both |
| **Force operations** | `git push --force`, `git reset --hard` | Tool intercept |
| **Infrastructure** | `terraform apply`, `kubectl delete`, `ecs update-service` | Tool intercept (require staging target) |
| **File deletion** | `rm -rf` on source files | Tool intercept (allow only in `/tmp`) |
| **Database** | `DROP`, `TRUNCATE`, migration rollback | Tool intercept |
| **Secrets** | Writing `*.pem`, `*.key`, `.env` to git index | Task guardrail on commit output |
| **Hook bypass** | `--no-verify` on git commit/push | Tool intercept |

---

## Configuration

```yaml
# ~/.code-crew/config.yaml
guardrails:
  protected_branches: [main, master, release, production]
  allow_force_push: false
  require_staging_target: true      # terraform apply must name staging workspace
  blocked_file_patterns:
    - "*.pem"
    - "*.key"
    - ".env"
    - "*.tfstate"
  allow_rm_rf_in: ["/tmp", ".build", "dist"]
```

Teams in sandboxed environments (no real remote, no real AWS) can widen the allowlist. Teams deploying to real infrastructure keep the defaults.

---

## Human review gate

Regardless of tool-level guardrails, the following require a human to trigger them outside the agent flow — via workflow_dispatch, a manual pipeline job, or explicit CLI prompt:

- Any push to a protected branch
- Any `terraform apply` to the production workspace
- Any database migration on a production database
- Any ECS / Kubernetes deployment to the production environment

Agents produce the artifact (PR, Terraform plan, migration file). Humans pull the trigger.

This is not a new constraint — it restates the core principle from ADD-001. Guardrails here enforce it mechanically so it cannot be accidentally bypassed.

---

## Implementation checklist

- [ ] Add `_check_command(cmd)` to `platform_shell` tool before `subprocess.run`
- [ ] Add `guardrail=_guardrail_git_push` to `scaffold_code`, `implementation`, `devops_coordination`, `promote_staging` in `crew.py`
- [ ] Add `guardrails` section to `.config.example.yaml` and `shared/config.py`
- [ ] Load `config.guardrails.protected_branches` in `_guardrail_git_push`
- [ ] Add ADR documenting the decision to enforce guardrails at both task and tool level
