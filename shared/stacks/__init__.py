"""Stack-specific Python detection modules.

Each module in this package implements:
    detect(root: Path, svc_dir: Path) -> list[str]

Returns a list of sub-executable paths (relative to repo root) found in svc_dir
for that stack. Returns [] if the stack is not present in svc_dir.

The dispatcher tries every available detector against every service directory
rather than filtering by detected stacks — each detector checks its own
preconditions internally (e.g. go.py checks for go.mod, node.py for package.json).
"""

from __future__ import annotations

import importlib
from pathlib import Path

_DETECTORS = ["go", "python", "java", "node", "rust"]


def detect_sub_executables(root: Path, svc_dirs: list[str]) -> list[str]:
    """Return de-duplicated sub-executables across all service dirs and all stacks."""
    results: list[str] = []
    for svc in svc_dirs:
        svc_path = root / svc
        if not svc_path.is_dir():
            continue
        for name in _DETECTORS:
            try:
                mod = importlib.import_module(f"shared.stacks.{name}")
                results.extend(mod.detect(root, svc_path))
            except (ImportError, Exception):
                continue
    seen: set[str] = set()
    out: list[str] = []
    for item in results:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
