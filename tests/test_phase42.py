"""Tests for Phase 42 — /keybindings REPL command."""

from __future__ import annotations

from devagent.agent.flows import _KEYBINDINGS_TABLE, _REPL_COMMANDS


class TestKeybindingsTable:
    def test_is_list_of_tuples(self) -> None:
        assert isinstance(_KEYBINDINGS_TABLE, list)
        assert all(isinstance(entry, tuple) and len(entry) == 2 for entry in _KEYBINDINGS_TABLE)

    def test_all_entries_are_strings(self) -> None:
        for key, action in _KEYBINDINGS_TABLE:
            assert isinstance(key, str) and key
            assert isinstance(action, str) and action

    def test_minimum_entries(self) -> None:
        assert len(_KEYBINDINGS_TABLE) >= 8

    def test_covers_ctrl_c(self) -> None:
        keys = [k.lower() for k, _ in _KEYBINDINGS_TABLE]
        assert any("ctrl+c" in k for k in keys)

    def test_covers_ctrl_d(self) -> None:
        keys = [k.lower() for k, _ in _KEYBINDINGS_TABLE]
        assert any("ctrl+d" in k for k in keys)

    def test_covers_tab(self) -> None:
        keys = [k.lower() for k, _ in _KEYBINDINGS_TABLE]
        assert any("tab" in k for k in keys)

    def test_covers_f1(self) -> None:
        keys = [k.lower() for k, _ in _KEYBINDINGS_TABLE]
        assert any("f1" in k for k in keys)

    def test_covers_f2(self) -> None:
        keys = [k.lower() for k, _ in _KEYBINDINGS_TABLE]
        assert any("f2" in k for k in keys)

    def test_no_duplicate_keys(self) -> None:
        keys = [k for k, _ in _KEYBINDINGS_TABLE]
        assert len(keys) == len(set(keys))


class TestKeybindingsInReplCommands:
    def test_keybindings_in_repl_commands(self) -> None:
        assert "/keybindings" in _REPL_COMMANDS

    def test_repl_commands_is_list_of_strings(self) -> None:
        assert all(isinstance(c, str) for c in _REPL_COMMANDS)
