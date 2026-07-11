"""Sub-executable detection for Rust projects.

Detects runnable targets via:
- Cargo.toml [[bin]] sections (multiple named binaries)
- Cargo workspace members (workspace.members)
- src/bin/ directory convention (each .rs file = a binary)
"""

from __future__ import annotations

import re
from pathlib import Path


def detect(root: Path, svc_dir: Path) -> list[str]:
    """Return sub-executables found in svc_dir for Rust projects."""
    cargo_toml = svc_dir / "Cargo.toml"
    if not cargo_toml.exists():
        return []

    results: list[str] = []

    try:
        text = cargo_toml.read_text(encoding="utf-8", errors="replace")

        # Workspace members
        in_workspace_members = False
        for line in text.splitlines():
            stripped = line.strip()
            if re.match(r'^\[workspace\]', stripped):
                continue
            if re.match(r'^members\s*=', stripped):
                in_workspace_members = True
            if in_workspace_members:
                for m in re.finditer(r'"([^"]+)"', line):
                    member = m.group(1)
                    # Handle glob patterns like "crates/*"
                    if "*" in member:
                        import glob as _glob
                        for match in sorted(_glob.glob(str(svc_dir / member))):
                            p = Path(match)
                            if p.is_dir() and (p / "Cargo.toml").exists():
                                results.append(str(p.relative_to(root)))
                    else:
                        member_path = svc_dir / member
                        if member_path.is_dir():
                            results.append(str(member_path.relative_to(root)))
                if "]" in line and in_workspace_members and line.strip() != "members = [":
                    in_workspace_members = False

        # [[bin]] sections
        bin_names: list[str] = []
        in_bin = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped == "[[bin]]":
                in_bin = True
                continue
            if in_bin:
                if stripped.startswith("[[") or stripped.startswith("["):
                    in_bin = False
                    continue
                m = re.match(r'^name\s*=\s*"([^"]+)"', stripped)
                if m:
                    bin_names.append(m.group(1))
                    in_bin = False

        if len(bin_names) > 1:
            for name in bin_names:
                results.append(f"{str(svc_dir.relative_to(root))}:{name}")

        # src/bin/ convention — each .rs file is a binary
        src_bin = svc_dir / "src" / "bin"
        if src_bin.is_dir() and not results:
            for f in sorted(src_bin.glob("*.rs")):
                results.append(f"{str(svc_dir.relative_to(root))}:{f.stem}")

    except Exception:
        pass

    return results
