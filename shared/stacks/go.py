"""Sub-executable detection for Go projects.

Looks for the cmd/ convention: each subdirectory of cmd/ is a separate binary.
Handles both flat (svc/cmd/) and nested (svc/backend/cmd/) layouts.
"""

from __future__ import annotations

from pathlib import Path


def detect(root: Path, svc_dir: Path) -> list[str]:
    """Return sub-executables found under any cmd/ directory in svc_dir."""
    if not any((svc_dir / f).exists() for f in ("go.mod",)):
        # Walk one level deeper in case of monorepo sub-layout (e.g. svc/backend/go.mod)
        has_gomod = any(svc_dir.glob("*/go.mod"))
        if not has_gomod:
            return []

    results: list[str] = []
    # Check svc/cmd/ and svc/*/cmd/ (one level of nesting)
    candidates = [svc_dir / "cmd"] + [
        child / "cmd"
        for child in svc_dir.iterdir()
        if child.is_dir() and not child.name.startswith(".")
    ]
    for cmd_dir in candidates:
        if not cmd_dir.is_dir():
            continue
        for sub in sorted(cmd_dir.iterdir()):
            if sub.is_dir() and not sub.name.startswith("."):
                # Confirm it's actually a Go executable (contains .go files)
                if any(sub.glob("*.go")):
                    results.append(str(sub.relative_to(root)))
    return results
