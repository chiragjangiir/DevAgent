"""Tests for Phase 41 — diff viewer before writes + --add-dir support."""

from __future__ import annotations

from devagent.tools.file_tools import _safe_resolve, register_file_tools
from devagent.tools.registry import ToolRegistry

# ---------------------------------------------------------------------------
# _safe_resolve — extra_roots
# ---------------------------------------------------------------------------

class TestSafeResolveExtraDirs:
    def test_project_root_still_allowed(self, tmp_path) -> None:
        target = _safe_resolve(str(tmp_path), "foo.txt")
        assert target == tmp_path / "foo.txt"

    def test_path_inside_extra_root_allowed(self, tmp_path) -> None:
        extra = tmp_path / "extra"
        extra.mkdir()
        target = _safe_resolve(str(tmp_path), "extra/bar.txt", [extra])
        assert target.name == "bar.txt"

    def test_path_outside_all_roots_raises(self, tmp_path) -> None:
        import pytest
        with pytest.raises(ValueError):
            _safe_resolve(str(tmp_path), "../../../etc/passwd")

    def test_sibling_sharing_a_name_prefix_raises(self, tmp_path) -> None:
        """Containment is not a string prefix: `proj-other` is not inside `proj`."""
        import pytest
        project = tmp_path / "proj"
        project.mkdir()
        sibling = tmp_path / "proj-other"
        sibling.mkdir()
        with pytest.raises(ValueError):
            _safe_resolve(str(project), str(sibling / "f.txt"))

    def test_extra_roots_none_equals_default(self, tmp_path) -> None:
        a = _safe_resolve(str(tmp_path), "f.txt", None)
        b = _safe_resolve(str(tmp_path), "f.txt")
        assert a == b


# ---------------------------------------------------------------------------
# register_file_tools — extra_dirs
# ---------------------------------------------------------------------------

class TestFileToolsExtraDirs:
    def _registry(self, project_root, extra_dirs=None):
        registry = ToolRegistry()
        register_file_tools(registry, str(project_root), extra_dirs=extra_dirs)
        return registry

    def test_read_inside_extra_dir(self, tmp_path) -> None:
        extra = tmp_path / "extra"
        extra.mkdir()
        (extra / "note.txt").write_text("hello")

        reg = self._registry(tmp_path / "project", extra_dirs=[str(extra)])
        (tmp_path / "project").mkdir()
        result = reg.call("read_file", {"path": str(extra / "note.txt")})
        assert "hello" in result

    def test_write_inside_extra_dir(self, tmp_path) -> None:
        extra = tmp_path / "extra"
        extra.mkdir()
        project = tmp_path / "project"
        project.mkdir()

        reg = self._registry(project, extra_dirs=[str(extra)])
        result = reg.call("write_file", {"path": str(extra / "out.txt"), "content": "hi"})
        assert "error" not in result.lower()
        assert (extra / "out.txt").read_text() == "hi"

    def test_write_outside_all_dirs_rejected(self, tmp_path) -> None:
        project = tmp_path / "project"
        project.mkdir()
        reg = self._registry(project)
        # try to escape via traversal
        result = reg.call("write_file", {"path": "../../../tmp/evil.txt", "content": "x"})
        assert "[error]" in result


# ---------------------------------------------------------------------------
# register_file_tools — diff_confirm_fn
# ---------------------------------------------------------------------------

class TestDiffConfirmFn:
    def _registry_with_confirm(self, project_root, confirm_return=True):
        registry = ToolRegistry()
        calls: list[tuple[str, str]] = []

        def _confirm(path: str, diff: str) -> bool:
            calls.append((path, diff))
            return confirm_return

        register_file_tools(registry, str(project_root), diff_confirm_fn=_confirm)
        return registry, calls

    def test_confirm_called_on_write(self, tmp_path) -> None:
        (tmp_path / "f.txt").write_text("old")
        reg, calls = self._registry_with_confirm(tmp_path)
        reg.call("write_file", {"path": "f.txt", "content": "new"})
        assert len(calls) == 1
        assert calls[0][0] == "f.txt"
        assert "old" in calls[0][1] or "new" in calls[0][1]

    def test_rejected_write_does_not_change_file(self, tmp_path) -> None:
        (tmp_path / "f.txt").write_text("original")
        reg, _ = self._registry_with_confirm(tmp_path, confirm_return=False)
        result = reg.call("write_file", {"path": "f.txt", "content": "changed"})
        assert "[skipped]" in result
        assert (tmp_path / "f.txt").read_text() == "original"

    def test_accepted_write_changes_file(self, tmp_path) -> None:
        (tmp_path / "f.txt").write_text("old")
        reg, _ = self._registry_with_confirm(tmp_path, confirm_return=True)
        reg.call("write_file", {"path": "f.txt", "content": "new content"})
        assert (tmp_path / "f.txt").read_text() == "new content"

    def test_confirm_called_on_edit(self, tmp_path) -> None:
        (tmp_path / "g.txt").write_text("foo bar baz")
        reg, calls = self._registry_with_confirm(tmp_path)
        reg.call("edit_file", {"path": "g.txt", "old_str": "bar", "new_str": "qux"})
        assert len(calls) == 1

    def test_rejected_edit_does_not_change_file(self, tmp_path) -> None:
        (tmp_path / "g.txt").write_text("hello world")
        reg, _ = self._registry_with_confirm(tmp_path, confirm_return=False)
        result = reg.call("edit_file", {"path": "g.txt", "old_str": "world", "new_str": "there"})
        assert "[skipped]" in result
        assert (tmp_path / "g.txt").read_text() == "hello world"

    def test_new_file_write_confirm_called(self, tmp_path) -> None:
        """Creating a new file produces a diff (from empty) — confirm is called."""
        reg, calls = self._registry_with_confirm(tmp_path)
        reg.call("write_file", {"path": "brand_new.txt", "content": "hello"})
        assert len(calls) == 1
        assert "brand_new.txt" in calls[0][0]

    def test_no_confirm_fn_writes_unconditionally(self, tmp_path) -> None:
        (tmp_path / "h.txt").write_text("old")
        reg = ToolRegistry()
        register_file_tools(reg, str(tmp_path))
        reg.call("write_file", {"path": "h.txt", "content": "new"})
        assert (tmp_path / "h.txt").read_text() == "new"


# ---------------------------------------------------------------------------
# build_registry wires extra_dirs and diff_confirm_fn
# ---------------------------------------------------------------------------

class TestBuildRegistryPhase41:
    def test_extra_dirs_passed_through(self, tmp_path) -> None:
        from devagent.tools.registry import build_registry
        extra = tmp_path / "extra"
        extra.mkdir()
        project = tmp_path / "project"
        project.mkdir()
        (extra / "x.txt").write_text("data")

        reg = build_registry(project_root=str(project), extra_dirs=[str(extra)])
        result = reg.call("read_file", {"path": str(extra / "x.txt")})
        assert "data" in result

    def test_diff_confirm_fn_passed_through(self, tmp_path) -> None:
        from devagent.tools.registry import build_registry
        (tmp_path / "t.txt").write_text("before")
        confirmed: list[bool] = []

        def _fn(path, diff):
            confirmed.append(True)
            return False  # reject

        reg = build_registry(project_root=str(tmp_path), diff_confirm_fn=_fn)
        result = reg.call("write_file", {"path": "t.txt", "content": "after"})
        assert "[skipped]" in result
        assert confirmed
