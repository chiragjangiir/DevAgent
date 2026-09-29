"""Tests for Phase 36 — /branch (session copy) and /theme (UIConfig)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# store.copy_session_events
# ---------------------------------------------------------------------------

class TestCopySessionEvents:
    def _make_session(self, session_id: str, db_path=None) -> None:
        from devagent.session import store
        store.init_schema(db_path=db_path)
        store.create_session(
            session_id,
            project="/test",
            model="qwen2.5-coder:7b",
            provider="ollama",
            db_path=db_path,
        )

    def test_copies_all_events(self, tmp_path) -> None:
        from devagent.session import store
        db = tmp_path / "test.db"
        self._make_session("src", db_path=db)
        self._make_session("dst", db_path=db)
        store.append_event("src", role="user", content="hello", db_path=db)
        store.append_event("src", role="assistant", content="world", db_path=db)

        n = store.copy_session_events("src", "dst", db_path=db)
        assert n == 2
        dst_events = store.get_events("dst", db_path=db)
        assert len(dst_events) == 2
        assert dst_events[0]["content"] == "hello"
        assert dst_events[1]["content"] == "world"

    def test_resequences_from_zero(self, tmp_path) -> None:
        from devagent.session import store
        db = tmp_path / "test.db"
        self._make_session("src", db_path=db)
        self._make_session("dst", db_path=db)
        for i in range(3):
            store.append_event("src", role="user", content=str(i), db_path=db)

        store.copy_session_events("src", "dst", db_path=db)
        dst_events = store.get_events("dst", db_path=db)
        seqs = [e["seq"] for e in dst_events]
        assert seqs == [0, 1, 2]

    def test_copies_tool_calls(self, tmp_path) -> None:
        from devagent.session import store
        db = tmp_path / "test.db"
        self._make_session("src", db_path=db)
        self._make_session("dst", db_path=db)
        store.append_event(
            "src", role="assistant",
            tool_calls=[{"id": "tc1", "name": "read_file", "args": {}}],
            db_path=db,
        )

        store.copy_session_events("src", "dst", db_path=db)
        dst = store.get_events("dst", db_path=db)
        assert len(dst[0]["tool_calls"]) == 1
        assert dst[0]["tool_calls"][0]["name"] == "read_file"

    def test_empty_source_returns_zero(self, tmp_path) -> None:
        from devagent.session import store
        db = tmp_path / "test.db"
        self._make_session("src", db_path=db)
        self._make_session("dst", db_path=db)
        n = store.copy_session_events("src", "dst", db_path=db)
        assert n == 0

    def test_does_not_affect_source(self, tmp_path) -> None:
        from devagent.session import store
        db = tmp_path / "test.db"
        self._make_session("src", db_path=db)
        self._make_session("dst", db_path=db)
        store.append_event("src", role="user", content="original", db_path=db)

        store.copy_session_events("src", "dst", db_path=db)
        src_events = store.get_events("src", db_path=db)
        assert len(src_events) == 1
        assert src_events[0]["content"] == "original"


# ---------------------------------------------------------------------------
# UIConfig and theme field
# ---------------------------------------------------------------------------

class TestUIConfig:
    def test_default_theme_is_default(self) -> None:
        from devagent.core.config import UIConfig
        cfg = UIConfig()
        assert cfg.theme == "default"

    def test_valid_themes_accepted(self) -> None:
        from devagent.core.config import UIConfig
        for t in ("default", "dracula", "monokai", "solarized"):
            cfg = UIConfig(theme=t)
            assert cfg.theme == t

    def test_invalid_theme_rejected(self) -> None:
        from devagent.core.config import UIConfig
        with pytest.raises(ValidationError):
            UIConfig(theme="cyberpunk")

    def test_devagentconfig_has_ui_field(self) -> None:
        from devagent.core.config import DevAgentConfig
        cfg = DevAgentConfig()
        assert hasattr(cfg, "ui")
        assert cfg.ui.theme == "default"

    def test_theme_serialises_in_model_dump(self) -> None:
        from devagent.core.config import DevAgentConfig
        cfg = DevAgentConfig()
        cfg.ui.theme = "dracula"
        d = cfg.model_dump()
        assert d["ui"]["theme"] == "dracula"


# ---------------------------------------------------------------------------
# _THEME_STYLES registry
# ---------------------------------------------------------------------------

class TestThemeStyles:
    def test_all_four_themes_defined(self) -> None:
        from devagent.agent.flows import _THEME_STYLES
        assert "default" in _THEME_STYLES
        assert "dracula" in _THEME_STYLES
        assert "monokai" in _THEME_STYLES
        assert "solarized" in _THEME_STYLES

    def test_default_theme_is_none(self) -> None:
        from devagent.agent.flows import _THEME_STYLES
        assert _THEME_STYLES["default"] is None

    def test_non_default_themes_are_dicts(self) -> None:
        from devagent.agent.flows import _THEME_STYLES
        for name, val in _THEME_STYLES.items():
            if name != "default":
                assert isinstance(val, dict)
                assert len(val) > 0
