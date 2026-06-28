"""
Persistent conversation sessions for /ask and free-text chat.

Sessions are stored as .jsonl files in .code-crew/sessions/ (project-scoped).
Each line is a JSON-encoded exchange: {role, content, ts}.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


def _sessions_dir() -> Path:
    d = Path.cwd() / ".code-crew" / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


@dataclass
class Exchange:
    role: str      # agent name or "user"
    content: str
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Session:
    def __init__(self, name: str) -> None:
        self.name = name
        self._path = _sessions_dir() / f"{name}.jsonl"
        self._lock = threading.Lock()
        self._exchanges: list[Exchange] = self._load()

    def _load(self) -> list[Exchange]:
        if not self._path.exists():
            return []
        exchanges = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    exchanges.append(Exchange(**json.loads(line)))
                except Exception:
                    pass
        return exchanges

    def add(self, role: str, content: str) -> None:
        ex = Exchange(role=role, content=content)
        with self._lock:
            self._exchanges.append(ex)
            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(ex)) + "\n")

    def recent(self, n: int = 10) -> list[Exchange]:
        return self._exchanges[-n:]

    def context_block(self, n: int = 10, max_chars: int = 500) -> str:
        recent = self.recent(n)
        if not recent:
            return ""
        lines = ["## Conversation history (this session)"]
        for ex in recent:
            snippet = ex.content[:max_chars].replace("\n", " ")
            if len(ex.content) > max_chars:
                snippet += "…"
            lines.append(f"**{ex.role}:** {snippet}")
        return "\n\n".join(lines)

    def summary(self, n: int = 5) -> str:
        recent = self.recent(n)
        if not recent:
            return "(empty)"
        lines = []
        for ex in recent:
            snippet = ex.content[:80].replace("\n", " ")
            lines.append(f"  {ex.role}: {snippet}")
        return "\n".join(lines)

    @staticmethod
    def default_name() -> str:
        return datetime.now().strftime("%Y-%m-%d")

    @staticmethod
    def list_all() -> list[str]:
        return sorted(p.stem for p in _sessions_dir().glob("*.jsonl"))

    @staticmethod
    def load_or_create(name: str) -> "Session":
        return Session(name)
