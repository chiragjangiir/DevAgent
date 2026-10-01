"""Tests for ShellSession side-effect tracking (cd / export parsing).

Regression coverage for issue #70: a `cd` appearing on its own line of a
multi-line command must update the session cwd, exactly like one after `;`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devagent.tools.shell_tool import ShellSession


@pytest.fixture()
def session(tmp_path: Path) -> ShellSession:
    """A session rooted in a temp dir that contains a `sub` subdirectory."""
    (tmp_path / "sub").mkdir()
    (tmp_path / "other").mkdir()
    return ShellSession(str(tmp_path))


def test_starts_in_project_root(session: ShellSession, tmp_path: Path) -> None:
    assert session.cwd == str(tmp_path.resolve())


@pytest.mark.parametrize(
    "command",
    [
        "echo hi; cd sub",
        "true && cd sub",
        "false || cd sub",
    ],
)
def test_cd_after_sequencing_operator(
    session: ShellSession, tmp_path: Path, command: str
) -> None:
    session.apply_side_effects(command)
    assert session.cwd == str((tmp_path / "sub").resolve())


@pytest.mark.parametrize(
    "command",
    [
        "echo hi\ncd sub\npwd",       # \n
        "echo hi\r\ncd sub\r\npwd",   # \r\n (Windows newlines from tools)
        "\ncd sub",                    # leading newline
        "echo hi\n    cd sub",         # indented line inside a script/heredoc
    ],
)
def test_cd_on_its_own_line(
    session: ShellSession, tmp_path: Path, command: str
) -> None:
    """Issue #70: a newline-joined `cd` was previously not detected."""
    session.apply_side_effects(command)
    assert session.cwd == str((tmp_path / "sub").resolve())


def test_multiple_cd_apply_in_order(session: ShellSession, tmp_path: Path) -> None:
    """Each `cd` resolves against the cwd left by the previous one (shell order)."""
    session.apply_side_effects("cd sub\ncd ../other")
    assert session.cwd == str((tmp_path / "other").resolve())


def test_cd_in_single_pipe_does_not_move(session: ShellSession, tmp_path: Path) -> None:
    """`cd` in a pipeline runs in a subshell — it must not change session cwd."""
    session.apply_side_effects("echo x | cd sub")
    assert session.cwd == str(tmp_path.resolve())


def test_cd_in_subshell_does_not_move(session: ShellSession, tmp_path: Path) -> None:
    session.apply_side_effects("( cd sub; pwd )")
    assert session.cwd == str(tmp_path.resolve())


def test_cd_dash_is_ignored(session: ShellSession, tmp_path: Path) -> None:
    session.apply_side_effects("cd -")
    assert session.cwd == str(tmp_path.resolve())


def test_cd_to_missing_dir_is_ignored(session: ShellSession, tmp_path: Path) -> None:
    session.apply_side_effects("cd no_such_dir")
    assert session.cwd == str(tmp_path.resolve())


def test_cd_relative_resolves_against_current_cwd(
    session: ShellSession, tmp_path: Path
) -> None:
    session.apply_side_effects("cd sub\ncd ..")
    assert session.cwd == str(tmp_path.resolve())


def test_export_after_newline_is_tracked(session: ShellSession) -> None:
    """The export parser is separator-agnostic; a multi-line command still works."""
    session.apply_side_effects("echo hi\nexport FOO=bar")
    assert session.env["FOO"] == "bar"
