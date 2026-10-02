"""File-based cross-session project memory.

Facts are stored in <project_root>/.devagent/memory.md as a Markdown list
so they persist across sessions and can be inspected or edited by hand:

  # DevAgent Memory
  <!-- auto-managed — edit with care -->
  - framework: FastAPI
  - test_command: pytest tests/ -q
  - auth_module: devagent/core/auth.py

On session start, these facts are merged into the SQLite MemoryBlock.
When the agent calls remember_fact / forget_fact, the file is kept in sync.
"""

from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Any, ClassVar

_MEMORY_FILE = ".devagent/memory.md"
_HEADER = "# DevAgent Memory\n<!-- auto-managed — edit with care -->\n"
_ITEM_RE = re.compile(r"^-\s+(\S+?):\s+(.+)$", re.MULTILINE)


class ProjectMemory:
    """Read/write .devagent/memory.md for cross-session fact persistence."""

    # One lock per memory file, shared by every instance in this process that
    # points at the same path. Guarded by _locks_guard because two threads may
    # create the entry for a new path at the same time.
    _locks: ClassVar[dict[str, threading.Lock]] = {}
    _locks_guard: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self, project_root: str | Path, *, path: Path | None = None) -> None:
        if path is not None:
            self._path = Path(path)
        else:
            self._path = Path(project_root) / _MEMORY_FILE

    @classmethod
    def _lock_for(cls, path: Path) -> threading.Lock:
        """The lock guarding read-modify-write cycles for `path`.

        Keyed by the resolved path, not by a project root, so that two
        instances reaching the same file by different spellings share one lock,
        while `for_agent` scopes (a different file) stay independent.
        """
        key = str(path.resolve())
        with cls._locks_guard:
            lock = cls._locks.get(key)
            if lock is None:
                lock = threading.Lock()
                cls._locks[key] = lock
            return lock

    @classmethod
    def for_agent(cls, project_root: str | Path, agent_name: str) -> ProjectMemory:
        """Return a ProjectMemory scoped to .devagent/agent-memory/<agent_name>/memory.md."""
        safe = agent_name.replace("/", "_").replace("\\", "_")
        p = Path(project_root) / ".devagent" / "agent-memory" / safe / "memory.md"
        return cls(project_root, path=p)

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> dict[str, str]:
        """Parse memory.md and return a key → value dict. Returns {} if missing."""
        if not self._path.exists():
            return {}
        text = self._path.read_text(encoding="utf-8")
        return {m.group(1): m.group(2).strip() for m in _ITEM_RE.finditer(text)}

    def save(self, facts: dict[str, Any]) -> None:
        """Overwrite memory.md with all facts, sorted by key."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        lines = [_HEADER]
        for key in sorted(facts):
            lines.append(f"- {key}: {facts[key]}")
        self._path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def upsert(self, key: str, value: Any) -> None:
        # load -> mutate -> save is a read-modify-write on a shared file; two
        # /batch workers running it concurrently would otherwise both write a
        # snapshot that predates the other's key, silently dropping one fact.
        with self._lock_for(self._path):
            facts = self.load()
            facts[key] = str(value)
            self.save(facts)

    def delete(self, key: str) -> None:
        with self._lock_for(self._path):
            facts = self.load()
            if key not in facts:
                return
            facts.pop(key)
            if facts:
                self.save(facts)
            else:
                self._path.write_text(_HEADER + "\n", encoding="utf-8")
