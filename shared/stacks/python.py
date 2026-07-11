"""Sub-executable detection for Python projects.

Detects runnable packages/scripts via:
- pyproject.toml [project.scripts] or [tool.poetry.scripts]
- setup.py / setup.cfg console_scripts
- Packages with __main__.py (python -m <package>)
"""

from __future__ import annotations

import re
from pathlib import Path


def detect(root: Path, svc_dir: Path) -> list[str]:
    """Return sub-executables found in svc_dir for Python projects."""
    has_py = (
        (svc_dir / "pyproject.toml").exists()
        or (svc_dir / "setup.py").exists()
        or (svc_dir / "setup.cfg").exists()
        or any(svc_dir.glob("*.py"))
    )
    if not has_py:
        return []

    results: list[str] = []

    # pyproject.toml — [project.scripts] or [tool.poetry.scripts]
    pyproject = svc_dir / "pyproject.toml"
    if pyproject.exists():
        try:
            text = pyproject.read_text(encoding="utf-8", errors="replace")
            # Extract script names from [project.scripts] or [tool.poetry.scripts]
            in_scripts = False
            for line in text.splitlines():
                stripped = line.strip()
                if re.match(r'^\[(project|tool\.poetry)\.scripts\]', stripped):
                    in_scripts = True
                    continue
                if in_scripts:
                    if stripped.startswith("["):
                        break
                    m = re.match(r'^(\w[\w\-]*)s*=', stripped)
                    if m:
                        results.append(f"{str(svc_dir.relative_to(root))}:{m.group(1)}")
        except Exception:
            pass

    # setup.cfg — console_scripts
    setup_cfg = svc_dir / "setup.cfg"
    if setup_cfg.exists():
        try:
            text = setup_cfg.read_text(encoding="utf-8", errors="replace")
            in_scripts = False
            for line in text.splitlines():
                stripped = line.strip()
                if stripped == "console_scripts":
                    in_scripts = True
                    continue
                if in_scripts:
                    if stripped.startswith("[") or (stripped and not stripped[0].isspace() and "=" not in stripped):
                        break
                    m = re.match(r'(\w[\w\-]*)\s*=', stripped)
                    if m:
                        results.append(f"{str(svc_dir.relative_to(root))}:{m.group(1)}")
        except Exception:
            pass

    # Packages with __main__.py — each is runnable as `python -m <package>`
    for candidate in sorted(svc_dir.iterdir()):
        if candidate.is_dir() and (candidate / "__main__.py").exists():
            if not candidate.name.startswith((".", "_", "test")):
                results.append(str(candidate.relative_to(root)))

    # src/ layout: src/<package>/__main__.py
    src = svc_dir / "src"
    if src.is_dir():
        for candidate in sorted(src.iterdir()):
            if candidate.is_dir() and (candidate / "__main__.py").exists():
                if not candidate.name.startswith((".", "_", "test")):
                    results.append(str(candidate.relative_to(root)))

    return results
