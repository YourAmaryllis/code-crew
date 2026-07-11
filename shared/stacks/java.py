"""Sub-executable detection for Java projects.

Detects runnable modules via:
- Maven multi-module pom.xml (<modules> section)
- Gradle settings.gradle / settings.gradle.kts (include statements)
- Presence of multiple Application.java / Main.java entry points
"""

from __future__ import annotations

import re
from pathlib import Path


def detect(root: Path, svc_dir: Path) -> list[str]:
    """Return sub-executables / modules found in svc_dir for Java projects."""
    has_java = (svc_dir / "pom.xml").exists() or (svc_dir / "build.gradle").exists() or \
               (svc_dir / "build.gradle.kts").exists()
    if not has_java:
        return []

    results: list[str] = []

    # Maven multi-module: pom.xml with <modules>
    pom = svc_dir / "pom.xml"
    if pom.exists():
        try:
            text = pom.read_text(encoding="utf-8", errors="replace")
            in_modules = False
            for line in text.splitlines():
                stripped = line.strip()
                if "<modules>" in stripped:
                    in_modules = True
                    continue
                if "</modules>" in stripped:
                    break
                if in_modules:
                    m = re.search(r"<module>([^<]+)</module>", stripped)
                    if m:
                        module_name = m.group(1).strip()
                        module_path = svc_dir / module_name
                        if module_path.is_dir():
                            results.append(str(module_path.relative_to(root)))
        except Exception:
            pass

    # Gradle multi-project: settings.gradle includes
    for settings_file in ("settings.gradle", "settings.gradle.kts"):
        settings = svc_dir / settings_file
        if settings.exists():
            try:
                text = settings.read_text(encoding="utf-8", errors="replace")
                for m in re.finditer(r"""include\s*['"]([\w\-:/]+)['"]""", text):
                    # Gradle module name: ':module-name' → 'module-name' directory
                    module_name = m.group(1).lstrip(":")
                    module_path = svc_dir / module_name
                    if module_path.is_dir():
                        results.append(str(module_path.relative_to(root)))
            except Exception:
                pass
            break

    # If no multi-module structure found, look for multiple Application.java / Main.java
    if not results:
        entry_points = list(svc_dir.rglob("Application.java")) + list(svc_dir.rglob("Main.java"))
        if len(entry_points) > 1:
            # Multiple entry points in different packages — each src/main subtree is a module
            for ep in sorted(entry_points):
                # Walk up to find the nearest directory containing src/main
                candidate = ep.parent
                while candidate != svc_dir and candidate != root:
                    if (candidate / "src" / "main").exists() or (candidate / "pom.xml").exists():
                        rel = str(candidate.relative_to(root))
                        if rel not in results:
                            results.append(rel)
                        break
                    candidate = candidate.parent

    return results
