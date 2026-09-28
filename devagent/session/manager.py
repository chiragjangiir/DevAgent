"""Session manager -- create, resume, list, and close agent sessions.

Wraps store.py with higher-level operations used by the agent loop and CLI.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

from devagent.session import store


class SessionManager:
    """Manage agent sessions backed by SQLite."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path
        store.init_schema(db_path)

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def new(
        self,
        project: str = "",
        model: str = "",
        provider: str = "",
        title: str = "",
        metadata: dict | None = None,
    ) -> str:
        """Create a new session and return its ID."""
        session_id = str(uuid.uuid4())
        store.create_session(
            session_id,
            project=project,
            model=model,
            provider=provider,
            title=title or f"Session {time.strftime('%Y-%m-%d %H:%M')}",
            metadata=metadata,
            db_path=self.db_path,
        )
        return session_id

    def resume(self, session_id: str) -> dict:
        """Load an existing session. Raises KeyError if not found."""
        session = store.get_session(session_id, db_path=self.db_path)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")
        return session

    def close(self, session_id: str) -> None:
        store.update_session(session_id, db_path=self.db_path)

    def list(self, limit: int = 50) -> list[dict]:
        return store.list_sessions(limit=limit, db_path=self.db_path)

    def delete(self, session_id: str) -> None:
        store.delete_session(session_id, db_path=self.db_path)

    def get(self, session_id: str) -> dict | None:
        return store.get_session(session_id, db_path=self.db_path)

    def set_title(self, session_id: str, title: str) -> None:
        store.update_session(session_id, title=title, db_path=self.db_path)

    def find_by_name(self, name: str) -> dict | None:
        """Find a session whose title matches name (case-insensitive), or None."""
        name_lower = name.lower()
        for s in self.list(limit=500):
            if (s.get("title") or "").lower() == name_lower:
                return s
        return None

    def rename(self, session_id: str, name: str) -> None:
        self.set_title(session_id, name)

    # ------------------------------------------------------------------
    # Event log helpers
    # ------------------------------------------------------------------

    def record_user(self, session_id: str, content: str) -> None:
        store.append_event(session_id, role="user", content=content, db_path=self.db_path)

    def record_assistant(
        self,
        session_id: str,
        content: str,
        tool_calls: list[dict] | None = None,
        tokens_in: int = 0,
        tokens_out: int = 0,
    ) -> None:
        store.append_event(
            session_id,
            role="assistant",
            content=content,
            tool_calls=tool_calls,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            db_path=self.db_path,
        )

    def record_tool_result(
        self,
        session_id: str,
        tool_call_id: str,
        tool_name: str,
        content: str,
    ) -> None:
        store.append_event(
            session_id,
            role="tool_result",
            content=content,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            db_path=self.db_path,
        )

    def get_events(self, session_id: str) -> list[dict]:
        return store.get_events(session_id, db_path=self.db_path)

    def get_token_totals(self, session_id: str) -> dict[str, int]:
        return store.get_token_totals(session_id, db_path=self.db_path)

    # ------------------------------------------------------------------
    # Structured memory
    # ------------------------------------------------------------------

    def remember(
        self,
        session_id: str,
        key: str,
        value: Any,
        scope: str = "session",
        item_type: str = "fact",
    ) -> None:
        store.upsert_memory(
            session_id, key, value, scope=scope, item_type=item_type, db_path=self.db_path
        )

    def recall(self, session_id: str, scope: str = "session") -> dict[str, Any]:
        return store.get_memory(session_id, scope=scope, db_path=self.db_path)

    def forget(self, session_id: str, key: str, scope: str = "session") -> None:
        store.delete_memory_key(session_id, key, scope=scope, db_path=self.db_path)
