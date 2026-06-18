#!/usr/bin/env python3
"""
Convert all files in designs/ADR/, designs/ADD/, designs/SOP/ to OKF format.

Adds YAML frontmatter to every .md file that doesn't already have it.
Skips index files and files that already start with ---.
Run from the tools/ repo root:

    python scripts/convert_designs_to_okf.py [--dry-run]
"""

import argparse
import re
import sys
from pathlib import Path

import yaml

DESIGNS_ROOT = Path(__file__).resolve().parents[1] / "designs"

SKIP_STEMS = {"ADR", "ADD", "SOP", "CRD", "EVAL", "PLAN", "REF", "SAD", "README"}


def _extract_title(text: str) -> str:
    """Extract the first # heading as title."""
    for line in text.splitlines():
        m = re.match(r"^#\s+(.+)", line)
        if m:
            return m.group(1).strip()
    return ""


def _extract_status(text: str) -> str:
    """Extract status from ADR/ADD headers like **Status:** Accepted."""
    m = re.search(r"\*\*Status[:\*]+\*?\*?\s*([A-Za-z ]+)", text)
    if m:
        return m.group(1).strip().rstrip("*")
    return ""


def _extract_date(text: str) -> str:
    """Extract date from **Date:** or **Date**:."""
    m = re.search(r"\*\*Date[:\*]+\*?\*?\s*(\d{4}-\d{2}-\d{2})", text)
    if m:
        return m.group(1)
    return ""


def _extract_description(text: str, title: str) -> str:
    """Extract first meaningful paragraph after the title as description."""
    lines = text.splitlines()
    past_title = False
    para_lines = []
    for line in lines:
        stripped = line.strip()
        if not past_title:
            if stripped.startswith("#"):
                past_title = True
            continue
        if stripped.startswith(("#", "**Status", "**Date", "---")):
            continue
        if stripped == "":
            if para_lines:
                break
            continue
        # Strip markdown bold/italic markers for plain description
        clean = re.sub(r"\*{1,3}|`", "", stripped)
        para_lines.append(clean)

    desc = " ".join(para_lines)
    # Trim to ~160 chars
    if len(desc) > 160:
        desc = desc[:157].rsplit(" ", 1)[0] + "…"
    return desc or title


def _dir_type(directory: str) -> str:
    mapping = {"ADR": "ADR", "ADD": "ADD", "SOP": "SOP"}
    return mapping.get(directory, "document")


def _generate_tags(text: str, doc_type: str, stem: str) -> list[str]:
    tags = [doc_type.lower()]
    # Add slug from stem: ADR-024-Monorepo → monorepo
    parts = stem.replace("_", "-").split("-")
    # Skip numeric parts and type prefixes
    slug_parts = [p.lower() for p in parts if not re.match(r"^\d+$", p) and p.upper() not in ("ADR", "ADD", "SOP")]
    if slug_parts:
        tags.append("-".join(slug_parts[:3]))
    return tags


def build_frontmatter(path: Path, text: str) -> dict:
    doc_type = _dir_type(path.parent.name)
    title = _extract_title(text)
    description = _extract_description(text, title)
    fm: dict = {
        "type": doc_type,
        "title": title or path.stem,
        "description": description,
        "tags": _generate_tags(text, doc_type, path.stem),
        "resource": f"designs/{path.parent.name}/{path.name}",
    }
    if doc_type == "ADR":
        status = _extract_status(text)
        date = _extract_date(text)
        if status:
            fm["status"] = status
        if date:
            fm["date"] = date
    elif doc_type == "ADD":
        status = _extract_status(text)
        date = _extract_date(text)
        if status:
            fm["status"] = status
        if date:
            fm["date"] = date
    return fm


def convert_file(path: Path, dry_run: bool = False) -> bool:
    text = path.read_text(encoding="utf-8")

    if text.lstrip().startswith("---"):
        return False  # already has frontmatter

    fm = build_frontmatter(path, text)
    fm_yaml = yaml.dump(fm, allow_unicode=True, sort_keys=False, default_flow_style=False)
    new_text = f"---\n{fm_yaml}---\n\n{text}"

    if dry_run:
        print(f"[dry-run] Would update: {path.relative_to(DESIGNS_ROOT.parent)}")
        print(f"  title: {fm['title']}")
        return True

    path.write_text(new_text, encoding="utf-8")
    print(f"Updated: {path.relative_to(DESIGNS_ROOT.parent)}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Add OKF frontmatter to designs/ docs")
    parser.add_argument("--dry-run", action="store_true", help="Print what would change without writing")
    parser.add_argument("--dir", help="Limit to a single subdir (ADR, ADD, SOP)")
    args = parser.parse_args()

    if not DESIGNS_ROOT.exists():
        print(f"Error: designs/ not found at {DESIGNS_ROOT}", file=sys.stderr)
        print("Run from the tools/ repo root with designs/ submodule initialized.", file=sys.stderr)
        sys.exit(1)

    dirs = [args.dir] if args.dir else ["ADR", "ADD", "SOP"]
    updated = 0
    skipped = 0

    for subdir in dirs:
        target = DESIGNS_ROOT / subdir
        if not target.exists():
            print(f"Warning: {target} not found, skipping", file=sys.stderr)
            continue
        for md_file in sorted(target.glob("*.md")):
            if md_file.stem in SKIP_STEMS or md_file.stem.upper() in SKIP_STEMS:
                skipped += 1
                continue
            if convert_file(md_file, dry_run=args.dry_run):
                updated += 1
            else:
                skipped += 1

    print(f"\nDone: {updated} updated, {skipped} skipped (already have frontmatter or index files).")
    if args.dry_run:
        print("Re-run without --dry-run to apply changes.")


if __name__ == "__main__":
    main()
