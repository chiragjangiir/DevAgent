"""Phase 16 — Jupyter notebook tools.

Only registered when `nbformat` is importable. `notebook_run` requires
`jupyter nbconvert` in PATH (install with: pip install jupyter).
"""

from __future__ import annotations

import subprocess
import warnings
from pathlib import Path
from typing import Any


def register_notebook_tools(registry, project_root: str) -> None:
    """Register notebook_read, notebook_edit, notebook_run.

    Caller must ensure nbformat is importable before calling this function.
    """
    import nbformat

    def notebook_read(args: dict[str, Any]) -> str:
        path = args.get("path", "").strip()
        if not path:
            return "[error] path is required"
        target = Path(project_root) / path
        if not target.exists():
            return f"[error] Notebook not found: {path}"
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                nb = nbformat.read(str(target), as_version=4)
        except Exception as exc:
            return f"[error] Could not parse notebook: {exc}"

        lines = [f"Notebook: {path} ({len(nb.cells)} cells)"]
        for i, cell in enumerate(nb.cells):
            source = cell.source.strip()
            if not source:
                continue
            out_text = ""
            if cell.cell_type == "code" and cell.get("outputs"):
                parts = []
                for out in cell.outputs:
                    ot = out.get("output_type", "")
                    if ot == "stream":
                        parts.append("".join(out.get("text", [])))
                    elif ot in ("execute_result", "display_data"):
                        data = out.get("data", {})
                        if "text/plain" in data:
                            parts.append("".join(data["text/plain"]))
                if parts:
                    out_text = "\nOutput:\n" + "\n".join(parts)
            lines.append(f"\n[Cell {i} — {cell.cell_type}]\n{source}{out_text}")
        return "\n".join(lines)

    registry.register(
        "notebook_read",
        "Read a Jupyter notebook and return its cells with any existing outputs.",
        {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the .ipynb file, relative to the project root",
                },
            },
            "required": ["path"],
        },
        notebook_read,
    )

    def notebook_edit(args: dict[str, Any]) -> str:
        path = args.get("path", "").strip()
        cell_index = args.get("cell_index")
        new_source = args.get("source", "")
        if not path:
            return "[error] path is required"
        if cell_index is None:
            return "[error] cell_index is required"
        target = Path(project_root) / path
        if not target.exists():
            return f"[error] Notebook not found: {path}"
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                nb = nbformat.read(str(target), as_version=4)
        except Exception as exc:
            return f"[error] Could not parse notebook: {exc}"
        idx = int(cell_index)
        if idx < 0 or idx >= len(nb.cells):
            return f"[error] Cell index {idx} out of range (0–{len(nb.cells) - 1})"
        nb.cells[idx].source = new_source
        if nb.cells[idx].cell_type == "code":
            nb.cells[idx]["outputs"] = []
            nb.cells[idx]["execution_count"] = None
        try:
            nbformat.write(nb, str(target))
        except Exception as exc:
            return f"[error] Could not write notebook: {exc}"
        return f"Cell {idx} updated in {path}"

    registry.register(
        "notebook_edit",
        "Edit a cell in a Jupyter notebook by replacing its source code.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the .ipynb file"},
                "cell_index": {
                    "type": "integer",
                    "description": "0-based cell index to edit",
                },
                "source": {
                    "type": "string",
                    "description": "New source code for the cell",
                },
            },
            "required": ["path", "cell_index", "source"],
        },
        notebook_edit,
    )

    def notebook_run(args: dict[str, Any]) -> str:
        path = args.get("path", "").strip()
        timeout = int(args.get("timeout", 60))
        if not path:
            return "[error] path is required"
        target = Path(project_root) / path
        if not target.exists():
            return f"[error] Notebook not found: {path}"
        try:
            result = subprocess.run(
                [
                    "jupyter", "nbconvert", "--to", "notebook",
                    "--execute", "--inplace",
                    f"--ExecutePreprocessor.timeout={timeout}",
                    str(target),
                ],
                capture_output=True,
                text=True,
                timeout=timeout + 10,
            )
        except FileNotFoundError:
            return "[error] jupyter not found — install with: pip install jupyter"
        except subprocess.TimeoutExpired:
            return f"[error] Execution timed out after {timeout}s"
        except Exception as exc:
            return f"[error] {exc}"
        if result.returncode != 0:
            return f"[error] Execution failed:\n{result.stderr[:2000]}"
        return f"Notebook executed successfully: {path}"

    registry.register(
        "notebook_run",
        (
            "Execute a Jupyter notebook in place using jupyter nbconvert. "
            "Outputs are saved back to the file. Requires jupyter in PATH."
        ),
        {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the .ipynb file"},
                "timeout": {
                    "type": "integer",
                    "description": "Max seconds to allow execution (default 60)",
                },
            },
            "required": ["path"],
        },
        notebook_run,
    )
