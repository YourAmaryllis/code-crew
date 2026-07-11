"""Sub-executable detection for Node.js / TypeScript projects.

Detects runnable packages via:
- package.json workspaces field (monorepo)
- Subdirectories each containing their own package.json with a bin or main field
- Next.js / Remix apps under apps/ or packages/ (common monorepo layouts)
"""

from __future__ import annotations

import json
from pathlib import Path


def detect(root: Path, svc_dir: Path) -> list[str]:
    """Return sub-executables / workspace packages found in svc_dir."""
    pkg_json = svc_dir / "package.json"
    if not pkg_json.exists():
        return []

    results: list[str] = []

    # Check for workspaces in root package.json
    try:
        pkg = json.loads(pkg_json.read_text(encoding="utf-8", errors="replace"))
        workspaces = pkg.get("workspaces", [])
        if isinstance(workspaces, dict):
            workspaces = workspaces.get("packages", [])
        if workspaces:
            import glob as _glob
            for pattern in workspaces:
                for match in sorted(_glob.glob(str(svc_dir / pattern))):
                    p = Path(match)
                    if p.is_dir() and (p / "package.json").exists():
                        results.append(str(p.relative_to(root)))
    except Exception:
        pass

    # Common monorepo layouts: apps/, packages/, services/ with subdirs
    if not results:
        for subdir_name in ("apps", "packages", "services"):
            subdir = svc_dir / subdir_name
            if not subdir.is_dir():
                continue
            for candidate in sorted(subdir.iterdir()):
                if candidate.is_dir() and (candidate / "package.json").exists():
                    if not candidate.name.startswith("."):
                        results.append(str(candidate.relative_to(root)))
            if results:
                break

    # Single package with bin entries — each bin is a CLI executable
    if not results:
        try:
            pkg = json.loads(pkg_json.read_text(encoding="utf-8", errors="replace"))
            bins = pkg.get("bin", {})
            if isinstance(bins, str):
                bins = {pkg.get("name", svc_dir.name): bins}
            if len(bins) > 1:
                for bin_name in sorted(bins):
                    results.append(f"{str(svc_dir.relative_to(root))}:{bin_name}")
        except Exception:
            pass

    return results
