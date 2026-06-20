"""
User-managed memory store for the code and ops crews.

A JSONL file (default: ~/.code-crew/memory/crew-memory.jsonl) that users
populate via the CLI. At crew startup, relevant entries are retrieved by
keyword match against the Jira key, sprint terms, and tags, then injected
into the context header.

No LLM or embedder required — user context is explicit, not inferred.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shared.home import default_memory_path


def _memory_path() -> Path:
    raw = os.environ.get("CREW_MEMORY_PATH", "")
    path = Path(raw).expanduser() if raw else default_memory_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


class MemoryEntry:
    def __init__(
        self,
        content: str,
        category: str = "general",
        tags: list[str] | None = None,
        entry_id: str | None = None,
        timestamp: str | None = None,
    ):
        self.id = entry_id or str(uuid.uuid4())[:8]
        self.content = content
        self.category = category
        self.tags = [t.upper() for t in (tags or [])]
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "category": self.category,
            "tags": self.tags,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "MemoryEntry":
        return cls(
            content=d["content"],
            category=d.get("category", "general"),
            tags=d.get("tags", []),
            entry_id=d.get("id"),
            timestamp=d.get("timestamp"),
        )

    def __str__(self) -> str:
        tags_str = f" [{', '.join(self.tags)}]" if self.tags else ""
        ts = self.timestamp[:10] if self.timestamp else ""
        return f"[{self.id}] ({self.category}{tags_str}) {self.content}  — {ts}"


class UserMemory:
    def __init__(self, path: Path | None = None):
        self._path = path or _memory_path()

    def _load_all(self) -> list[MemoryEntry]:
        if not self._path.exists():
            return []
        entries = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    entries.append(MemoryEntry.from_dict(json.loads(line)))
                except (json.JSONDecodeError, KeyError):
                    pass
        return entries

    def _save_all(self, entries: list[MemoryEntry]) -> None:
        self._path.write_text(
            "\n".join(json.dumps(e.to_dict()) for e in entries) + "\n",
            encoding="utf-8",
        )

    def add(self, content: str, category: str = "general", tags: list[str] | None = None) -> MemoryEntry:
        entry = MemoryEntry(content=content, category=category, tags=tags)
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")
        return entry

    def list(self, category: str | None = None, tag: str | None = None) -> list[MemoryEntry]:
        entries = self._load_all()
        if category:
            entries = [e for e in entries if e.category == category]
        if tag:
            entries = [e for e in entries if tag.upper() in e.tags]
        return entries

    def remove(self, entry_id: str) -> bool:
        entries = self._load_all()
        before = len(entries)
        entries = [e for e in entries if e.id != entry_id]
        if len(entries) < before:
            self._save_all(entries)
            return True
        return False

    def clear(self, category: str | None = None) -> int:
        entries = self._load_all()
        before = len(entries)
        if category:
            entries = [e for e in entries if e.category != category]
        else:
            entries = []
        self._save_all(entries)
        return before - len(entries)

    def recall(self, jira_key: str = "", terms: list[str] | None = None) -> list[MemoryEntry]:
        """Return entries relevant to a sprint run.

        Matches by: Jira key tag, keyword overlap with terms, or category 'always'.
        """
        all_entries = self._load_all()
        if not all_entries:
            return []

        jira_upper = jira_key.upper()
        term_words = {w.lower() for w in (terms or []) if len(w) > 3}

        scored: list[tuple[int, MemoryEntry]] = []
        for entry in all_entries:
            score = 0
            if entry.category == "always":
                score += 10
            if jira_upper and jira_upper in entry.tags:
                score += 5
            content_lower = entry.content.lower()
            for word in term_words:
                if word in content_lower:
                    score += 1
            if score > 0:
                scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored]

    def format_for_context(self, jira_key: str = "", terms: list[str] | None = None) -> str:
        """Return a markdown block of relevant memories for injection into crew context."""
        entries = self.recall(jira_key=jira_key, terms=terms)
        if not entries:
            return ""
        lines = ["## User context (from memory)"]
        for e in entries:
            tag_str = f" `[{', '.join(e.tags)}]`" if e.tags else ""
            lines.append(f"- **{e.category}**{tag_str}: {e.content}")
        return "\n".join(lines)


CATEGORIES = ("decisions", "blockers", "env", "jira", "security", "notes", "always")
