"""Tests for Phase 29 — REPL tab completion, session naming, banner trim."""

from __future__ import annotations

from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# _REPL_COMMANDS — module-level list for tab completion
# ---------------------------------------------------------------------------

class TestReplCommands:
    def test_list_exists(self):
        from devagent.agent.flows import _REPL_COMMANDS
        assert isinstance(_REPL_COMMANDS, list)
        assert len(_REPL_COMMANDS) > 0

    def test_contains_core_commands(self):
        from devagent.agent.flows import _REPL_COMMANDS
        for cmd in ("/help", "/model", "/exit", "/rename", "/status", "/clear"):
            assert cmd in _REPL_COMMANDS, f"{cmd} missing from _REPL_COMMANDS"

    def test_all_slash_prefixed(self):
        from devagent.agent.flows import _REPL_COMMANDS
        for cmd in _REPL_COMMANDS:
            assert cmd.startswith("/"), f"{cmd!r} does not start with /"

    def test_rename_in_list(self):
        from devagent.agent.flows import _REPL_COMMANDS
        assert "/rename" in _REPL_COMMANDS


# ---------------------------------------------------------------------------
# SessionManager.find_by_name
# ---------------------------------------------------------------------------

class TestFindByName:
    def _mgr(self, sessions):
        from devagent.session.manager import SessionManager
        mgr = SessionManager.__new__(SessionManager)
        mgr.db_path = None
        mgr.list = MagicMock(return_value=sessions)
        return mgr

    def test_finds_exact_match(self):
        mgr = self._mgr([
            {"id": "aaa", "title": "my-project"},
            {"id": "bbb", "title": "other"},
        ])
        result = mgr.find_by_name("my-project")
        assert result is not None
        assert result["id"] == "aaa"

    def test_case_insensitive(self):
        mgr = self._mgr([{"id": "aaa", "title": "My-Project"}])
        result = mgr.find_by_name("my-project")
        assert result is not None
        assert result["id"] == "aaa"

    def test_returns_none_when_not_found(self):
        mgr = self._mgr([{"id": "aaa", "title": "something-else"}])
        result = mgr.find_by_name("nonexistent")
        assert result is None

    def test_returns_none_on_empty_list(self):
        mgr = self._mgr([])
        assert mgr.find_by_name("anything") is None

    def test_handles_missing_title_key(self):
        mgr = self._mgr([{"id": "aaa"}])  # no 'title' key
        assert mgr.find_by_name("aaa") is None


# ---------------------------------------------------------------------------
# SessionManager.rename
# ---------------------------------------------------------------------------

class TestRename:
    def test_rename_calls_set_title(self):
        from devagent.session.manager import SessionManager
        mgr = SessionManager.__new__(SessionManager)
        mgr.db_path = None
        mgr.set_title = MagicMock()
        mgr.rename("sess-123", "my-name")
        mgr.set_title.assert_called_once_with("sess-123", "my-name")


# ---------------------------------------------------------------------------
# Resume by name — find_by_name is tried before ID prefix
# ---------------------------------------------------------------------------

class TestResumeByName:
    def test_find_by_name_called_first(self):
        """When resume_id is given, find_by_name is tried before list scan."""
        from devagent.session.manager import SessionManager
        mgr = SessionManager.__new__(SessionManager)
        mgr.db_path = None
        named_session = {"id": "aaaa-bbbb-cccc", "title": "mywork"}
        mgr.find_by_name = MagicMock(return_value=named_session)
        mgr.list = MagicMock(return_value=[named_session])

        # Simulate the resume logic from DevAgentSession.__init__
        resume_id = "mywork"
        match = mgr.find_by_name(resume_id) or next(
            (s for s in mgr.list(limit=200) if s["id"].startswith(resume_id)), None
        )
        mgr.find_by_name.assert_called_once_with("mywork")
        assert match is not None
        assert match["id"] == "aaaa-bbbb-cccc"

    def test_falls_back_to_id_prefix(self):
        """When find_by_name returns None, falls back to ID prefix scan."""
        from devagent.session.manager import SessionManager
        mgr = SessionManager.__new__(SessionManager)
        mgr.db_path = None
        session = {"id": "abcd-1234", "title": "other"}
        mgr.find_by_name = MagicMock(return_value=None)
        mgr.list = MagicMock(return_value=[session])

        resume_id = "abcd"
        match = mgr.find_by_name(resume_id) or next(
            (s for s in mgr.list(limit=200) if s["id"].startswith(resume_id)), None
        )
        assert match is not None
        assert match["id"] == "abcd-1234"


# ---------------------------------------------------------------------------
# Banner trim — intro no longer contains full command list
# ---------------------------------------------------------------------------

class TestBannerTrim:
    def test_banner_has_no_skill_line(self):
        import pathlib
        src = pathlib.Path(__file__).parent.parent / "devagent" / "agent" / "flows.py"
        text = src.read_text(encoding="utf-8")
        assert "Skills: /explain" not in text

    def test_banner_has_tab_hint(self):
        import pathlib
        src = pathlib.Path(__file__).parent.parent / "devagent" / "agent" / "flows.py"
        text = src.read_text(encoding="utf-8")
        assert "Tab to autocomplete" in text
