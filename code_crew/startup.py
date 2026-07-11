"""
Startup checks: git repo, required CLIs, stack detection.

Reads stack OKFs from DESIGNS_PATH to know which CLIs are required
for the detected stacks. Prints a status banner and returns a summary.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""
    fix: str = ""


@dataclass
class StartupSummary:
    git_ok: bool
    git_branch: str
    detected_stacks: list[str]
    detected_ci_methods: list[str]
    checks: list[CheckResult]
    warnings: int
    errors: int

    @property
    def ok(self) -> bool:
        return self.errors == 0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_checks(code_path: Path | None = None) -> StartupSummary:
    """Run all startup checks and return a summary (does not print)."""
    root = code_path or Path.cwd()
    checks: list[CheckResult] = []

    git_ok, git_branch = _check_git(root)
    checks.append(CheckResult(
        name="git repo",
        ok=git_ok,
        detail=git_branch if git_ok else "not a git repository",
        fix="" if git_ok else "Run /init to scaffold a new project",
    ))

    stacks = detect_stacks(root)
    required_clis = _required_clis_for_stacks(stacks)

    ci_methods = detect_ci_methods(root)
    required_clis.update(_required_clis_for_ci_methods(ci_methods))

    # gh is always useful (PR creation, GHA status); only require if GHA detected
    if "github-actions" in ci_methods or not ci_methods:
        required_clis.setdefault("gh", "brew install gh && gh auth login")
    if _uses_bedrock():
        required_clis.setdefault("aws", "brew install awscli")

    for cli, install_hint in sorted(required_clis.items()):
        found = shutil.which(cli) is not None
        checks.append(CheckResult(
            name=cli,
            ok=found,
            detail=shutil.which(cli) or "",
            fix=install_hint if not found else "",
        ))

    checks.append(_check_ast_grep())
    checks.append(_check_graphviz())
    checks.append(_check_langfuse())
    checks.append(_check_designs_dir(root))

    # ast-grep, graphviz, langfuse, and designs are optional — don't count as errors/warnings
    _OPTIONAL = {"git repo", "langfuse", "designs", "ast-grep", "graphviz"}
    warnings = sum(1 for c in checks if not c.ok and c.name not in _OPTIONAL)
    errors = sum(1 for c in checks if not c.ok and c.name == "git repo")

    return StartupSummary(
        git_ok=git_ok,
        git_branch=git_branch,
        detected_stacks=stacks,
        detected_ci_methods=ci_methods,
        checks=checks,
        warnings=warnings,
        errors=errors,
    )


def detect_stacks(root: Path | None = None) -> list[str]:
    """
    Return the active stack list for the project.

    Resolution order:
      1. CODE_CREW_STACKS env var  — set in a profile or shell; comma-separated
      2. `stacks:` in .code-crew.yaml  — project-level declaration
      3. File-based auto-detection — go.mod, package.json, etc.
    """
    root = root or Path.cwd()

    # 1. Env var (set via profile or shell)
    env_stacks = os.environ.get("CODE_CREW_STACKS", "").strip()
    if env_stacks:
        return [s.strip() for s in env_stacks.split(",") if s.strip()]

    # 2. Project config stacks:
    explicit = _stacks_from_yaml(root)
    if explicit is not None:
        return explicit

    # 3. Profile stacks: (set as _CODE_CREW_STACKS_PROFILE when profile loads)
    profile_stacks = os.environ.get("_CODE_CREW_STACKS_PROFILE", "").strip()
    if profile_stacks:
        return [s.strip() for s in profile_stacks.split(",") if s.strip()]

    # 4. Auto-detect
    detected: list[str] = []
    if (root / "go.mod").exists():
        detected.append("go-backend")
    if (root / "package.json").exists():
        detected.append("typescript-react")
    if (root / "pyproject.toml").exists() or (root / "setup.py").exists():
        detected.append("python")
    tf_files = list(root.glob("*.tf")) + list(
        (root / "terraform").glob("*.tf") if (root / "terraform").is_dir() else []
    )
    if tf_files:
        detected.append("terraform-aws")
    return detected


def detect_ci_methods(root: Path | None = None) -> list[str]:
    """
    Return CI/CD tooling detected for the project.

    Resolution order:
      1. `ci.deployment_methods` list in .code-crew/config.yaml
      2. File-based auto-detection
    Multiple tools are common (e.g. github-actions + terraform).
    """
    root = root or Path.cwd()

    # 1. Explicit config
    cfg = root / ".code-crew" / "config.yaml"
    if cfg.exists():
        try:
            data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
            methods = data.get("ci", {}).get("deployment_methods")
            if isinstance(methods, list) and methods:
                return [str(m) for m in methods]
        except Exception:
            pass

    # 2. File-based detection
    methods: list[str] = []
    if (root / ".github" / "workflows").is_dir() and list((root / ".github" / "workflows").glob("*.yml")):
        methods.append("github-actions")
    if (root / ".gitlab-ci.yml").exists():
        methods.append("gitlab-ci")
    if (root / "Jenkinsfile").exists():
        methods.append("jenkins")
    if any(f.name in ("docker-compose.yml", "docker-compose.yaml") for f in root.iterdir() if f.is_file()):
        methods.append("docker-compose")
    if (root / "cdk.json").exists():
        methods.append("aws-cdk")
    if (root / "pulumi.yaml").exists():
        methods.append("pulumi")
    if (root / "fly.toml").exists():
        methods.append("fly-io")
    if (root / "vercel.json").exists() or (root / ".vercel").is_dir():
        methods.append("vercel")
    if list(root.glob("*.tf")) or list(root.rglob("ops/modules/**/*.tf")):
        methods.append("terraform")
    return methods


def _required_clis_for_ci_methods(ci_methods: list[str]) -> dict[str, str]:
    hints = _cli_install_hints()
    result: dict[str, str] = {}
    _method_clis: dict[str, list[str]] = {
        "github-actions": ["gh"],
        "gitlab-ci": ["glab"],
        "jenkins": [],
        "docker-compose": ["docker"],
        "aws-cdk": ["cdk", "aws"],
        "pulumi": ["pulumi"],
        "fly-io": ["fly"],
        "vercel": ["vercel"],
        "terraform": ["terraform"],
    }
    for method in ci_methods:
        for cli in _method_clis.get(method, []):
            result[cli] = hints.get(cli, f"install {cli}")
    return result


def _stacks_from_yaml(root: Path) -> list[str] | None:
    """Read `stacks:` from .code-crew/config.yaml. Returns None if not set."""
    cfg = root / ".code-crew" / "config.yaml"
    if not cfg.exists():
        return None
    try:
        data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
        stacks = data.get("stacks")
        if isinstance(stacks, list) and stacks:
            return [str(s) for s in stacks]
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Git check
# ---------------------------------------------------------------------------

def _check_langfuse() -> CheckResult:
    """Check Langfuse credentials (optional — not configured is OK)."""
    pk = os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip()
    if not pk:
        return CheckResult("langfuse", True, "not configured (optional)", "")
    from shared.telemetry import setup_langfuse
    ok, err = setup_langfuse()
    if ok:
        host = os.environ.get("LANGFUSE_HOST", "cloud.langfuse.com").replace("https://", "")
        return CheckResult("langfuse", True, host, "")
    return CheckResult(
        "langfuse", False, "",
        err or "invalid credentials — check LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY",
    )


def _check_git(root: Path) -> tuple[bool, str]:
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False, ""
    branch = result.stdout.strip()
    # Also get clean/dirty status
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(root), capture_output=True, text=True,
    )
    dirty = " (dirty)" if status.stdout.strip() else ""
    return True, f"{branch}{dirty}"


# ---------------------------------------------------------------------------
# Stack OKF → required CLIs
# ---------------------------------------------------------------------------

def _required_clis_for_stacks(stacks: list[str]) -> dict[str, str]:
    """Load stack OKFs and collect required-cli entries. Returns {cli: install_hint}."""
    designs_path = _designs_path()
    if not designs_path:
        return {}

    stacks_dir = designs_path / "SDLC" / "stacks"
    if not stacks_dir.exists():
        return {}

    install_hints = _cli_install_hints()
    result: dict[str, str] = {}

    for stack_name in stacks:
        okf_path = stacks_dir / f"{stack_name}.md"
        if not okf_path.exists():
            continue
        try:
            text = okf_path.read_text(encoding="utf-8")
            if not text.startswith("---"):
                continue
            end = text.index("---", 3)
            fm = yaml.safe_load(text[3:end]) or {}
            metadata = fm.get("metadata", {})
            for cli in metadata.get("required-cli", []):
                result[cli] = install_hints.get(cli, f"install {cli}")
        except Exception:
            continue

    return result


def _designs_path() -> Path | None:
    raw = os.environ.get("DESIGNS_PATH", "")
    if raw:
        p = Path(raw).expanduser()
        return p if p.exists() else None
    # Prefer designs/ submodule in cwd (inside the platform repo)
    local = Path.cwd() / "designs"
    if local.exists():
        return local
    # Fall back to sibling designs/ in the tools repo (dev mode)
    candidate = Path(__file__).parent.parent / "designs"
    return candidate if candidate.exists() else None


def _cli_install_hints() -> dict[str, str]:
    """Return {cli: install_command} using the best available installer for this platform.

    Priority:
      1. Cross-platform package managers (pip, go install, cargo install, npm i -g) — always first
         because they work everywhere the underlying runtime is present.
      2. brew — used for tools with no better cross-platform installer, only when brew is on PATH.
      3. URL hint — shown for tools that need a manual/GUI installer; /fix won't auto-run these
         but they appear in the startup table so the user knows what to do.
    """
    import sys
    _brew = shutil.which("brew") is not None
    _on_mac = sys.platform == "darwin"

    def _brew_or(brew_pkg: str, fallback: str) -> str:
        return f"brew install {brew_pkg}" if _brew else fallback

    return {
        # ── Always cross-platform (pip) ────────────────────────────────────────
        "ruff":       "pip install ruff",
        "checkov":    "pip install checkov",
        "pre-commit": "pip install pre-commit",
        "aws":        "pip install awscli",
        # ── Always cross-platform (go install — Go must already be present) ────
        "golangci-lint": "go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest",
        "godog":         "go install github.com/cucumber/godog/cmd/godog@latest",
        "tfsec":         "go install github.com/aquasecurity/tfsec/cmd/tfsec@latest",
        "jira":          "go install github.com/ankitpokhrel/jira-cli/cmd/jira@latest",
        "glab":          "go install gitlab.com/gitlab-org/cli/cmd/glab@main && glab auth login",
        # ── Always cross-platform (npm) ────────────────────────────────────────
        "cdk":    "npm i -g aws-cdk",
        "linear": "npm i -g @linear/linear && linear auth login",
        "vercel": "npm i -g vercel",
        # ── Prefer brew; cargo install as universal fallback ───────────────────
        "ast-grep": "brew install ast-grep" if _brew else "cargo install ast-grep",
        # ── Prefer brew; reasonable cross-platform fallback ───────────────────
        "dot":   _brew_or("graphviz", "# https://graphviz.org/download/"),
        "gh":    _brew_or("gh", "go install github.com/cli/cli/v2/cmd/gh@latest") + " && gh auth login",
        "pulumi": _brew_or("pulumi", "curl -fsSL https://get.pulumi.com | sh"),
        "fly":    _brew_or("flyctl", "curl -L https://fly.io/install.sh | sh"),
        # ── brew or URL hint (no reliable single-command cross-platform path) ──
        "go":      _brew_or("go",      "# https://go.dev/dl/"),
        "node":    _brew_or("node",    "# https://nodejs.org/en/download/"),
        "npm":     _brew_or("node",    "# https://nodejs.org/en/download/"),
        "npx":     _brew_or("node",    "# https://nodejs.org/en/download/"),
        "python3": _brew_or("python",  "# https://www.python.org/downloads/"),
        "terraform": _brew_or("terraform", "# https://developer.hashicorp.com/terraform/install"),
        "docker":  (
            "brew install --cask docker" if _on_mac and _brew
            else _brew_or("docker", "# https://docs.docker.com/get-docker/")
        ),
    }


def _check_ast_grep() -> CheckResult:
    """Check for ast-grep CLI (structural code search). Optional — agents fall back to grep."""
    for binary in ("ast-grep", "sg"):
        path = shutil.which(binary)
        if path:
            return CheckResult("ast-grep", True, path, "")
    hint = _cli_install_hints().get("ast-grep", "cargo install ast-grep")
    return CheckResult(
        "ast-grep", False, "",
        f"{hint}  # enables structural AST search for engineer/architect agents",
    )


def _check_graphviz() -> CheckResult:
    """Check for graphviz dot CLI (threat model diagram layout). Optional — falls back to grid."""
    path = shutil.which("dot")
    if path:
        return CheckResult("graphviz", True, path, "")
    hint = _cli_install_hints().get("dot", "brew install graphviz")
    return CheckResult(
        "graphviz", False, "",
        f"{hint}  # enables auto-layout for /threat Threat Dragon diagrams",
    )


def _check_designs_dir(root: Path) -> CheckResult:
    """Check that a designs directory is configured and exists."""
    explicit = os.environ.get("DESIGNS_PATH", "").strip()
    if explicit:
        p = Path(explicit)
        if p.exists():
            return CheckResult("designs", True, str(p), "")
        return CheckResult(
            "designs", False, "",
            f"DESIGNS_PATH={explicit} does not exist — run /fix to create it",
        )
    local = root / "designs"
    if local.exists():
        return CheckResult("designs", True, str(local), "")
    return CheckResult(
        "designs", False, "",
        "no designs directory — run /fix to configure one",
    )


def _uses_bedrock() -> bool:
    """Return True if any configured LLM tier resolves to the bedrock provider."""
    import json
    raw = os.environ.get("LLM_CONFIG", "").strip()
    if raw:
        try:
            cfg = json.loads(raw)
        except json.JSONDecodeError:
            return True  # malformed config — assume bedrock to be safe
        providers = set()
        default = cfg.get("default", {})
        if default.get("provider"):
            providers.add(default["provider"])
        for tier in cfg.get("tiers", {}).values():
            if tier.get("provider"):
                providers.add(tier["provider"])
        for agent in cfg.get("agents", {}).values():
            if agent.get("provider"):
                providers.add(agent["provider"])
        return "bedrock" in providers
    # No LLM_CONFIG → legacy Bedrock env vars path
    return bool(os.environ.get("BEDROCK_MODEL_ID", "").strip())
