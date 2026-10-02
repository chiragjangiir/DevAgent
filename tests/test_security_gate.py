"""Tests for the security gate wrapper.

These tests use a stub CodePrismClient that returns canned scan_diff results
so the security gate logic can be exercised without a live CodePrism index.
"""

from __future__ import annotations

from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Helpers / stubs
# ---------------------------------------------------------------------------

def _make_client(scan_status: str = "PASS", issues: list | None = None) -> MagicMock:
    """Build a minimal stub CodePrismClient."""
    client = MagicMock()
    client.is_indexed = True
    client.scan_diff.return_value = {
        "status": scan_status,
        "new_issues": issues or [],
    }
    client.get_module_summary.return_value = {"error": "not indexed"}
    client.record_write.return_value = {"status": "PASS"}
    return client


def _make_handler(result: str = "ok: file written") -> MagicMock:
    """Build a stub original write handler."""
    h = MagicMock(return_value=result)
    return h


def _wrap(
    scan_status: str = "PASS",
    issues: list | None = None,
    security_log: list | None = None,
    confirm_fn=None,
    handler_result: str = "ok: file written",
    project_root: str = "/tmp",
    extra_dirs: list | None = None,
):
    """Build a wrapped handler under test."""
    from devagent.tools.security_gate import wrap_write_with_security

    client = _make_client(scan_status, issues)
    handler = _make_handler(handler_result)
    log = security_log if security_log is not None else []
    wrapped = wrap_write_with_security(
        handler,
        client,
        project_root,
        "write",
        security_log=log,
        confirm_fn=confirm_fn,
        extra_dirs=extra_dirs,
    )
    return wrapped, handler, client, log


# ---------------------------------------------------------------------------
# PASS path
# ---------------------------------------------------------------------------

def test_pass_calls_original_handler(tmp_path):
    wrapped, handler, _, _ = _wrap(
        scan_status="PASS",
        project_root=str(tmp_path),
    )
    args = {"path": "foo.py", "content": "x = 1"}
    result = wrapped(args)
    handler.assert_called_once_with(args)
    assert result == "ok: file written"


def test_pass_logs_write(tmp_path):
    log = []
    wrapped, _, _, _ = _wrap(
        scan_status="PASS",
        project_root=str(tmp_path),
        security_log=log,
    )
    # Write the file so record_write actually fires
    (tmp_path / "foo.py").write_text("x = 1")
    wrapped({"path": "foo.py", "content": "x = 2"})
    write_events = [e for e in log if e.get("action") == "WRITE"]
    assert len(write_events) == 1
    assert write_events[0]["file"] == "foo.py"


# ---------------------------------------------------------------------------
# BLOCK path
# ---------------------------------------------------------------------------

def test_block_returns_error_string(tmp_path):
    issues = [{"severity": "CRITICAL", "description": "hardcoded secret"}]
    wrapped, handler, _, _ = _wrap(
        scan_status="BLOCK",
        issues=issues,
        project_root=str(tmp_path),
    )
    result = wrapped({"path": "creds.py", "content": "password = 'abc'"})
    handler.assert_not_called()
    assert "[security_block]" in result
    assert "creds.py" in result


def test_block_logged(tmp_path):
    log = []
    issues = [{"severity": "CRITICAL", "description": "eval injection"}]
    wrapped, _, _, _ = _wrap(
        scan_status="BLOCK",
        issues=issues,
        security_log=log,
        project_root=str(tmp_path),
    )
    wrapped({"path": "bad.py", "content": "eval(x)"})
    block_events = [e for e in log if e.get("action") == "BLOCK"]
    assert len(block_events) == 1
    assert block_events[0]["file"] == "bad.py"


# ---------------------------------------------------------------------------
# WARN path
# ---------------------------------------------------------------------------

def test_warn_no_confirm_fn_proceeds(tmp_path):
    """Without a confirm_fn, WARN writes should proceed."""
    log = []
    issues = [{"severity": "WARN", "description": "use of eval"}]
    wrapped, handler, _, _ = _wrap(
        scan_status="WARN",
        issues=issues,
        security_log=log,
        confirm_fn=None,
        project_root=str(tmp_path),
    )
    wrapped({"path": "ok.py", "content": "eval('x')"})
    handler.assert_called_once()
    warn_events = [e for e in log if e.get("action") == "WARN"]
    assert len(warn_events) == 1


def test_warn_confirm_fn_true_proceeds(tmp_path):
    """confirm_fn returning True → write proceeds."""
    log = []
    issues = [{"severity": "WARN", "description": "suspicious import"}]
    confirm = MagicMock(return_value=True)
    wrapped, handler, _, _ = _wrap(
        scan_status="WARN",
        issues=issues,
        security_log=log,
        confirm_fn=confirm,
        project_root=str(tmp_path),
    )
    wrapped({"path": "mod.py", "content": "import os"})
    confirm.assert_called_once()
    handler.assert_called_once()


def test_warn_confirm_fn_false_rejects(tmp_path):
    """confirm_fn returning False → write rejected."""
    log = []
    issues = [{"severity": "WARN", "description": "suspicious import"}]
    confirm = MagicMock(return_value=False)
    wrapped, handler, _, _ = _wrap(
        scan_status="WARN",
        issues=issues,
        security_log=log,
        confirm_fn=confirm,
        project_root=str(tmp_path),
    )
    result = wrapped({"path": "mod.py", "content": "import subprocess"})
    handler.assert_not_called()
    assert "[security_rejected]" in result
    rejected = [e for e in log if e.get("action") == "REJECTED_BY_USER"]
    assert len(rejected) == 1


# ---------------------------------------------------------------------------
# Error result from original handler → no record_write
# ---------------------------------------------------------------------------

def test_error_from_handler_no_record_write(tmp_path):
    log = []
    client = _make_client("PASS")
    handler = _make_handler("[error] permission denied")
    from devagent.tools.security_gate import wrap_write_with_security
    wrapped = wrap_write_with_security(
        handler, client, str(tmp_path), "write", security_log=log
    )
    wrapped({"path": "x.py", "content": "y = 1"})
    # record_write should NOT be called on error
    client.record_write.assert_not_called()
    write_events = [e for e in log if e.get("action") == "WRITE"]
    assert len(write_events) == 0


# ---------------------------------------------------------------------------
# format_security_report
# ---------------------------------------------------------------------------

def test_format_security_report_empty():
    from devagent.tools.security_gate import format_security_report
    out = format_security_report([])
    assert "No security events" in out


def test_format_security_report_with_events():
    from devagent.tools.security_gate import format_security_report
    log = [
        {"action": "BLOCK", "file": "a.py", "reasons": "CRITICAL: hardcoded secret"},
        {"action": "WARN", "file": "b.py", "reasons": "WARN: eval"},
        {"action": "WRITE", "file": "c.py"},
    ]
    out = format_security_report(log)
    assert "Blocked" in out
    assert "1" in out
    assert "a.py" in out
    assert "b.py" in out


# ---------------------------------------------------------------------------
# Containment — the gate must not check a file outside the project
# ---------------------------------------------------------------------------

def test_traversal_path_is_blocked(tmp_path):
    """`../` escapes the root, so the checks must not run at all."""
    project = tmp_path / "project"
    project.mkdir()
    wrapped, handler, client, log = _wrap(project_root=str(project))

    result = wrapped({"path": "../../etc/passwd", "content": "x"})

    assert "security_block" in result
    handler.assert_not_called()          # the write itself never runs
    client.scan_diff.assert_not_called()  # and no scan of the wrong file
    assert [e["action"] for e in log] == ["BLOCK"]


def test_absolute_path_outside_root_is_blocked(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "elsewhere.txt"
    wrapped, handler, client, _log = _wrap(project_root=str(project))

    result = wrapped({"path": str(outside), "content": "x"})

    assert "security_block" in result
    handler.assert_not_called()
    client.scan_diff.assert_not_called()


def test_sibling_dir_sharing_a_name_prefix_is_blocked(tmp_path):
    """`project-other` is not inside `project` — a string prefix says it is."""
    project = tmp_path / "project"
    project.mkdir()
    sibling = tmp_path / "project-other"
    sibling.mkdir()
    wrapped, handler, _, _ = _wrap(project_root=str(project))

    result = wrapped({"path": str(sibling / "file.py"), "content": "x"})

    assert "security_block" in result
    handler.assert_not_called()


def test_absolute_path_inside_root_is_allowed(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    wrapped, handler, _, _ = _wrap(project_root=str(project))

    result = wrapped({"path": str(project / "a.py"), "content": "x"})

    assert "security_block" not in result
    handler.assert_called_once()


def test_relative_path_inside_root_is_allowed(tmp_path):
    project = tmp_path / "project"
    (project / "pkg").mkdir(parents=True)
    wrapped, handler, _, _ = _wrap(project_root=str(project))

    result = wrapped({"path": "pkg/mod.py", "content": "x"})

    assert "security_block" not in result
    handler.assert_called_once()


def test_symlink_escaping_the_root_is_blocked(tmp_path):
    """`.resolve()` follows the link, so containment sees the real location."""
    import os

    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = project / "link"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except (OSError, NotImplementedError):  # pragma: no cover - needs a privilege on Windows
        import pytest
        pytest.skip("symlink creation not permitted in this environment")

    wrapped, handler, _, _ = _wrap(project_root=str(project))
    result = wrapped({"path": "link/secret.txt", "content": "x"})

    assert "security_block" in result
    handler.assert_not_called()


def test_extra_dir_is_allowed_only_when_declared(tmp_path):
    """The gate must agree with the write tool's own extra_dirs."""
    project = tmp_path / "project"
    project.mkdir()
    extra = tmp_path / "extra"
    extra.mkdir()
    target = {"path": str(extra / "out.txt"), "content": "x"}

    undeclared, h1, _, _ = _wrap(project_root=str(project))
    assert "security_block" in undeclared(target)
    h1.assert_not_called()

    declared, h2, _, _ = _wrap(project_root=str(project), extra_dirs=[str(extra)])
    assert "security_block" not in declared(target)
    h2.assert_called_once()

