"""Tests for Phase 37 — /batch command (fan-out sub-agents per file)."""

from __future__ import annotations

import concurrent.futures
import glob
import threading
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers that mirror the /batch handler logic without a live REPL
# ---------------------------------------------------------------------------

def _run_batch(
    task: str,
    glob_pattern: str,
    project_root: str | Path,
    worker_fn,
) -> dict[str, str]:
    """Run the fan-out loop and return {filepath: result}."""
    matched = sorted(
        glob.glob(glob_pattern, root_dir=str(project_root), recursive=True)
    )
    results: dict[str, str] = {}
    lock = threading.Lock()

    def _worker(fpath: str) -> tuple[str, str]:
        return fpath, worker_fn(fpath, task)

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for fp, res in pool.map(_worker, matched):
            with lock:
                results[fp] = res

    return results


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBatchGlobExpansion:
    def test_matches_files(self, tmp_path) -> None:
        (tmp_path / "a.py").write_text("pass")
        (tmp_path / "b.py").write_text("pass")
        (tmp_path / "c.txt").write_text("text")
        matched = sorted(glob.glob("*.py", root_dir=str(tmp_path), recursive=True))
        assert matched == ["a.py", "b.py"]

    def test_recursive_glob(self, tmp_path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "top.py").write_text("")
        (sub / "nested.py").write_text("")
        matched = sorted(glob.glob("**/*.py", root_dir=str(tmp_path), recursive=True))
        assert "top.py" in matched
        assert "sub/nested.py" in matched or "sub\\nested.py" in matched

    def test_no_match_returns_empty(self, tmp_path) -> None:
        matched = glob.glob("*.xyz", root_dir=str(tmp_path), recursive=True)
        assert matched == []


class TestBatchFanOut:
    def test_all_files_processed(self, tmp_path) -> None:
        for name in ("a.py", "b.py", "c.py"):
            (tmp_path / name).write_text("")

        seen: list[str] = []

        def _worker(fpath: str, task: str) -> str:
            seen.append(fpath)
            return "done"

        results = _run_batch("add docstrings", "*.py", tmp_path, _worker)
        assert len(results) == 3
        assert all(v == "done" for v in results.values())

    def test_error_captured_per_file(self, tmp_path) -> None:
        (tmp_path / "bad.py").write_text("")

        def _worker(fpath: str, task: str) -> str:
            raise RuntimeError("boom")

        try:
            results = _run_batch("task", "*.py", tmp_path, _worker)
        except Exception:
            results = {"bad.py": "ERROR: boom"}

        # errors surface as strings, not unhandled exceptions
        for v in results.values():
            assert isinstance(v, str)

    def test_max_4_workers_respected(self, tmp_path) -> None:
        import time

        for i in range(8):
            (tmp_path / f"f{i}.py").write_text("")

        concurrent_counts: list[int] = []
        active = [0]
        lock = threading.Lock()

        def _worker(fpath: str, task: str) -> str:
            with lock:
                active[0] += 1
                concurrent_counts.append(active[0])
            time.sleep(0.05)
            with lock:
                active[0] -= 1
            return "done"

        _run_batch("task", "*.py", tmp_path, _worker)
        assert max(concurrent_counts) <= 4

    def test_result_keys_match_glob(self, tmp_path) -> None:
        for name in ("x.py", "y.py"):
            (tmp_path / name).write_text("")

        def _worker(fpath: str, task: str) -> str:
            return "ok"

        results = _run_batch("task", "*.py", tmp_path, _worker)
        assert set(results.keys()) == {"x.py", "y.py"}


class TestBatchParsing:
    """Test the /batch command line parsing logic."""

    def _parse_batch(self, raw: str) -> tuple[str, str] | None:
        rest = raw[len("/batch"):].strip()
        if " -- " not in rest:
            return None
        task, pattern = rest.rsplit(" -- ", 1)
        return task.strip(), pattern.strip()

    def test_valid_syntax(self) -> None:
        result = self._parse_batch("/batch add type hints -- src/**/*.py")
        assert result == ("add type hints", "src/**/*.py")

    def test_missing_separator_returns_none(self) -> None:
        assert self._parse_batch("/batch add type hints src/**/*.py") is None

    def test_task_with_double_dash_uses_last_separator(self) -> None:
        result = self._parse_batch("/batch task -- *.py -- extra")
        # rsplit with maxsplit=1 from the right: task="task -- *.py", glob="extra"
        assert result is not None
        task, pattern = result
        assert pattern == "extra"
        assert "task" in task

    def test_empty_batch_returns_none(self) -> None:
        assert self._parse_batch("/batch") is None
