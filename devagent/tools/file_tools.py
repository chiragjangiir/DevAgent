"""File read / write / edit / list tools.

All paths are resolved relative to project_root and must stay within it
(path traversal is rejected). These are the most commonly-called tools
in any coding agent loop.
"""

from __future__ import annotations

import difflib
from collections.abc import Callable
from pathlib import Path

from devagent.tools.registry import ToolRegistry

# Separator used to embed a unified diff in the tool result string.
# The agent loop splits on this to keep the LLM-facing result clean while
# letting the renderer show a colour-coded diff panel.
_DIFF_SEP = "\n---diff---\n"


def _within_roots(target: Path, roots: list[Path]) -> bool:
    """True when *target* is one of *roots* or sits inside one of them.

    A string prefix is not a containment test. ``/srv/project-other`` starts
    with ``/srv/project`` without being inside it, so the old
    ``str(target).startswith(str(root))`` spelling admitted a sibling whose
    name merely began with an allowed root's name.
    """
    return any(target.is_relative_to(root) for root in roots)


def _safe_resolve(project_root: str, path: str, extra_roots: list[Path] | None = None) -> Path:
    """Resolve path relative to project_root (or any extra_roots); raise ValueError on traversal."""
    main_root = Path(project_root).resolve()
    allowed_roots = [main_root] + (extra_roots or [])
    target = (main_root / path).resolve()
    if _within_roots(target, allowed_roots):
        return target
    # Try resolving as absolute path within an extra root
    abs_target = Path(path).resolve()
    if _within_roots(abs_target, allowed_roots):
        return abs_target
    raise ValueError(f"Path {path!r} escapes project root and all extra dirs")


def register_file_tools(
    registry: ToolRegistry,
    project_root: str = ".",
    extra_dirs: list[str] | None = None,
    diff_confirm_fn: Callable[[str, str], bool] | None = None,
) -> None:
    """Register file tools.

    extra_dirs:     additional directories the tools may read/write outside project_root.
    diff_confirm_fn: if set, called with (path, unified_diff) before each write/edit;
                     returning False aborts the operation (user rejected the change).
    """
    _extra_roots = [Path(d).resolve() for d in (extra_dirs or [])]

    def read_file(args: dict) -> str:
        path = args.get("path", "")
        start = int(args.get("start_line", 1))
        end = args.get("end_line")
        try:
            target = _safe_resolve(project_root, path, _extra_roots)
            lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
            if end:
                lines = lines[start - 1 : int(end)]
            else:
                lines = lines[start - 1 :]
            numbered = "\n".join(f"{i + start}: {l}" for i, l in enumerate(lines))
            return numbered or "(empty file)"
        except Exception as exc:
            return f"[error] {exc}"

    def write_file(args: dict) -> str:
        path = args.get("path", "")
        content = args.get("content", "")
        try:
            target = _safe_resolve(project_root, path, _extra_roots)
            target.parent.mkdir(parents=True, exist_ok=True)
            before_lines: list[str] = []
            if target.exists():
                before_lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
            after_lines = content.splitlines(keepends=True)
            diff = "".join(
                difflib.unified_diff(before_lines, after_lines, fromfile=f"a/{path}", tofile=f"b/{path}", n=3)
            )
            if diff and diff_confirm_fn is not None and not diff_confirm_fn(path, diff):
                return f"[skipped] Write to {path} rejected by user"
            target.write_text(content, encoding="utf-8")
            msg = f"Written {len(content)} bytes to {path}"
            return f"{msg}{_DIFF_SEP}{diff}" if diff else msg
        except Exception as exc:
            return f"[error] {exc}"

    def edit_file(args: dict) -> str:
        path = args.get("path", "")
        old_str = args.get("old_str", "")
        new_str = args.get("new_str", "")
        try:
            target = _safe_resolve(project_root, path, _extra_roots)
            original = target.read_text(encoding="utf-8")
            if old_str not in original:
                return f"[error] old_str not found in {path}"
            count = original.count(old_str)
            if count > 1:
                return f"[error] old_str found {count} times — be more specific"
            updated = original.replace(old_str, new_str, 1)
            diff = "".join(
                difflib.unified_diff(
                    original.splitlines(keepends=True),
                    updated.splitlines(keepends=True),
                    fromfile=f"a/{path}",
                    tofile=f"b/{path}",
                    n=3,
                )
            )
            if diff and diff_confirm_fn is not None and not diff_confirm_fn(path, diff):
                return f"[skipped] Edit to {path} rejected by user"
            target.write_text(updated, encoding="utf-8")
            msg = f"Edited {path}: replaced 1 occurrence"
            return f"{msg}{_DIFF_SEP}{diff}" if diff else msg
        except Exception as exc:
            return f"[error] {exc}"

    def list_files(args: dict) -> str:
        path = args.get("path", ".")
        max_depth = int(args.get("max_depth", 3))
        try:
            root = _safe_resolve(project_root, path, _extra_roots)
            results = []
            _walk(root, root, 0, max_depth, results)
            return "\n".join(results) or "(no files)"
        except Exception as exc:
            return f"[error] {exc}"

    def create_directory(args: dict) -> str:
        path = args.get("path", "")
        try:
            target = _safe_resolve(project_root, path, _extra_roots)
            target.mkdir(parents=True, exist_ok=True)
            return f"Directory created: {path}"
        except Exception as exc:
            return f"[error] {exc}"

    def delete_file(args: dict) -> str:
        path = args.get("path", "")
        confirm = args.get("confirm", False)
        if not confirm:
            return "[error] Set confirm=true to delete a file"
        try:
            target = _safe_resolve(project_root, path, _extra_roots)
            if target.is_file():
                target.unlink()
                return f"Deleted: {path}"
            return f"[error] Not a file: {path}"
        except Exception as exc:
            return f"[error] {exc}"

    registry.register(
        "read_file",
        "Read file contents from the project. Optionally specify start_line / end_line.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path from project root"},
                "start_line": {"type": "integer", "description": "First line to return (1-indexed)", "default": 1},
                "end_line": {"type": "integer", "description": "Last line to return (inclusive)"},
            },
            "required": ["path"],
        },
        read_file,
    )

    registry.register(
        "write_file",
        "Create or fully overwrite a file with the given content.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
        write_file,
    )

    registry.register(
        "edit_file",
        "Replace exactly one occurrence of old_str with new_str in a file.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_str": {"type": "string", "description": "Exact text to find (must be unique in file)"},
                "new_str": {"type": "string", "description": "Text to replace it with"},
            },
            "required": ["path", "old_str", "new_str"],
        },
        edit_file,
    )

    registry.register(
        "list_files",
        "List files in a directory tree (up to max_depth levels).",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path to list", "default": "."},
                "max_depth": {"type": "integer", "default": 3},
            },
        },
        list_files,
    )

    registry.register(
        "create_directory",
        "Create a directory (and parents) within the project.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
            },
            "required": ["path"],
        },
        create_directory,
    )

    registry.register(
        "delete_file",
        "Delete a file. Requires confirm=true as a safety guard.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "confirm": {"type": "boolean"},
            },
            "required": ["path", "confirm"],
        },
        delete_file,
    )


def _walk(root: Path, current: Path, depth: int, max_depth: int, results: list) -> None:
    if depth > max_depth:
        return
    skip = {".git", "__pycache__", ".venv", "venv", "node_modules", ".mypy_cache", ".pytest_cache"}
    try:
        entries = sorted(current.iterdir(), key=lambda p: (p.is_file(), p.name))
    except PermissionError:
        return
    for entry in entries:
        if entry.name in skip:
            continue
        rel = entry.relative_to(root).as_posix()
        if entry.is_dir():
            results.append(f"{rel}/")
            _walk(root, entry, depth + 1, max_depth, results)
        else:
            results.append(rel)
