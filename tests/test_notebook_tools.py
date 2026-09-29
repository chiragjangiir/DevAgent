"""Tests for Jupyter notebook tools (notebook_read, notebook_edit, notebook_run)."""

from __future__ import annotations

import json
import pathlib

import pytest

pytest.importorskip("nbformat")

from devagent.tools.notebook_tools import register_notebook_tools
from devagent.tools.registry import ToolRegistry


def _make_notebook(cells: list[dict]) -> dict:
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
            "language_info": {"name": "python"},
        },
        "cells": cells,
    }


def _write_nb(tmp_path: pathlib.Path, name: str, nb: dict) -> pathlib.Path:
    p = tmp_path / name
    p.write_text(json.dumps(nb))
    return p


def _registry(tmp_path: pathlib.Path) -> ToolRegistry:
    reg = ToolRegistry()
    register_notebook_tools(reg, str(tmp_path))
    return reg


# ---------------------------------------------------------------------------
# notebook_read
# ---------------------------------------------------------------------------

class TestNotebookRead:
    def test_reads_markdown_and_code_cells(self, tmp_path):
        nb = _make_notebook([
            {"cell_type": "markdown", "metadata": {}, "source": "# Hello"},
            {"cell_type": "code", "metadata": {}, "source": "x = 1", "outputs": [], "execution_count": None},
        ])
        _write_nb(tmp_path, "test.ipynb", nb)
        reg = _registry(tmp_path)
        result = reg.call("notebook_read", {"path": "test.ipynb"})
        assert "# Hello" in result
        assert "x = 1" in result
        assert "2 cells" in result

    def test_includes_outputs(self, tmp_path):
        nb = _make_notebook([
            {
                "cell_type": "code",
                "metadata": {},
                "source": "print('hi')",
                "outputs": [{"output_type": "stream", "name": "stdout", "text": "hi\n"}],
                "execution_count": 1,
            }
        ])
        _write_nb(tmp_path, "out.ipynb", nb)
        reg = _registry(tmp_path)
        result = reg.call("notebook_read", {"path": "out.ipynb"})
        assert "hi" in result
        assert "Output:" in result

    def test_skips_empty_cells(self, tmp_path):
        nb = _make_notebook([
            {"cell_type": "code", "metadata": {}, "source": "", "outputs": [], "execution_count": None},
            {"cell_type": "code", "metadata": {}, "source": "x = 1", "outputs": [], "execution_count": None},
        ])
        _write_nb(tmp_path, "empty.ipynb", nb)
        reg = _registry(tmp_path)
        result = reg.call("notebook_read", {"path": "empty.ipynb"})
        assert result.count("[Cell") == 1  # only non-empty cell shown

    def test_missing_path_returns_error(self, tmp_path):
        reg = _registry(tmp_path)
        result = reg.call("notebook_read", {"path": "nonexistent.ipynb"})
        assert "[error]" in result

    def test_missing_path_arg_returns_error(self, tmp_path):
        reg = _registry(tmp_path)
        result = reg.call("notebook_read", {})
        assert "[error]" in result

    def test_execute_result_output_shown(self, tmp_path):
        nb = _make_notebook([
            {
                "cell_type": "code",
                "metadata": {},
                "source": "1 + 1",
                "outputs": [{"output_type": "execute_result", "data": {"text/plain": "2"}, "metadata": {}, "execution_count": 1}],
                "execution_count": 1,
            }
        ])
        _write_nb(tmp_path, "exec.ipynb", nb)
        reg = _registry(tmp_path)
        result = reg.call("notebook_read", {"path": "exec.ipynb"})
        assert "2" in result


# ---------------------------------------------------------------------------
# notebook_edit
# ---------------------------------------------------------------------------

class TestNotebookEdit:
    def _nb_with_code(self, tmp_path, source="x = 1") -> pathlib.Path:
        nb = _make_notebook([
            {"cell_type": "code", "metadata": {}, "source": source, "outputs": [], "execution_count": None},
        ])
        return _write_nb(tmp_path, "edit.ipynb", nb)

    def test_updates_source(self, tmp_path):
        self._nb_with_code(tmp_path)
        reg = _registry(tmp_path)
        result = reg.call("notebook_edit", {"path": "edit.ipynb", "cell_index": 0, "source": "x = 99"})
        assert "updated" in result
        read_back = reg.call("notebook_read", {"path": "edit.ipynb"})
        assert "x = 99" in read_back

    def test_clears_outputs_on_code_cell(self, tmp_path):
        nb = _make_notebook([
            {
                "cell_type": "code",
                "metadata": {},
                "source": "print('old')",
                "outputs": [{"output_type": "stream", "name": "stdout", "text": "old\n"}],
                "execution_count": 5,
            }
        ])
        _write_nb(tmp_path, "clear.ipynb", nb)
        reg = _registry(tmp_path)
        reg.call("notebook_edit", {"path": "clear.ipynb", "cell_index": 0, "source": "print('new')"})
        read_back = reg.call("notebook_read", {"path": "clear.ipynb"})
        assert "old" not in read_back

    def test_out_of_range_index_returns_error(self, tmp_path):
        self._nb_with_code(tmp_path)
        reg = _registry(tmp_path)
        result = reg.call("notebook_edit", {"path": "edit.ipynb", "cell_index": 99, "source": "x"})
        assert "[error]" in result

    def test_missing_cell_index_returns_error(self, tmp_path):
        self._nb_with_code(tmp_path)
        reg = _registry(tmp_path)
        result = reg.call("notebook_edit", {"path": "edit.ipynb", "source": "x"})
        assert "[error]" in result

    def test_nonexistent_file_returns_error(self, tmp_path):
        reg = _registry(tmp_path)
        result = reg.call("notebook_edit", {"path": "no.ipynb", "cell_index": 0, "source": "x"})
        assert "[error]" in result


# ---------------------------------------------------------------------------
# notebook_run (mocked — requires jupyter in PATH)
# ---------------------------------------------------------------------------

class TestNotebookRun:
    def test_missing_jupyter_returns_error(self, tmp_path):
        nb = _make_notebook([
            {"cell_type": "code", "metadata": {}, "source": "x = 1", "outputs": [], "execution_count": None},
        ])
        _write_nb(tmp_path, "run.ipynb", nb)
        reg = _registry(tmp_path)
        from unittest.mock import patch
        with patch("subprocess.run", side_effect=FileNotFoundError("jupyter not found")):
            result = reg.call("notebook_run", {"path": "run.ipynb"})
        assert "[error]" in result
        assert "jupyter" in result

    def test_execution_failure_returns_error(self, tmp_path):
        from unittest.mock import MagicMock, patch
        nb = _make_notebook([
            {"cell_type": "code", "metadata": {}, "source": "raise ValueError('bad')", "outputs": [], "execution_count": None},
        ])
        _write_nb(tmp_path, "fail.ipynb", nb)
        reg = _registry(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "CellExecutionError: bad"
        with patch("subprocess.run", return_value=mock_result):
            result = reg.call("notebook_run", {"path": "fail.ipynb"})
        assert "[error]" in result

    def test_successful_run(self, tmp_path):
        from unittest.mock import MagicMock, patch
        nb = _make_notebook([
            {"cell_type": "code", "metadata": {}, "source": "x = 1", "outputs": [], "execution_count": None},
        ])
        _write_nb(tmp_path, "ok.ipynb", nb)
        reg = _registry(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            result = reg.call("notebook_run", {"path": "ok.ipynb"})
        assert "successfully" in result
