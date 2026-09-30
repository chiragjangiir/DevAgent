"""Tool registry -- maps tool names to handler callables.

All tools take a single dict of arguments and return a string result.
Tool definitions (for the LLM) are generated from registered entries.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from devagent.core.llm import ToolDef

ToolHandler = Callable[[dict[str, Any]], str]


class ToolRegistry:
    """Registry of all tools available to the agent."""

    def __init__(self, hook_runner=None) -> None:
        self._tools: dict[str, ToolDef] = {}
        self._handlers: dict[str, ToolHandler] = {}
        self._hook_runner = hook_runner  # HookRunner | None

    def register(
        self,
        name: str,
        description: str,
        parameters: dict,
        handler: ToolHandler,
    ) -> None:
        self._tools[name] = ToolDef(name=name, description=description, parameters=parameters)
        self._handlers[name] = handler

    def get_definitions(self) -> list[ToolDef]:
        return list(self._tools.values())

    def call(self, name: str, args: dict[str, Any]) -> str:
        handler = self._handlers.get(name)
        if handler is None:
            return f"[tool_error] Unknown tool: {name!r}"

        # Phase 10 — fire pre-tool-use hooks
        if self._hook_runner is not None:
            hook_result = self._hook_runner.pre_tool_use(name, args)
            if not hook_result.allowed:
                return f"[tool_error] Blocked by hook: {hook_result.feedback}"
            if hook_result.rewritten_args is not None:
                args = hook_result.rewritten_args

        try:
            result = handler(args)
        except Exception as exc:
            return f"[tool_error] {name} failed: {exc}"

        # Phase 10 — fire post-tool-use hooks (best-effort, non-blocking)
        if self._hook_runner is not None:
            try:
                self._hook_runner.post_tool_use(name, args, result)
            except Exception:
                pass

        return result

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def get_restricted_definitions(self, tool_names: list[str]) -> list[ToolDef]:
        """Return only ToolDefs whose names are in tool_names.

        If tool_names is empty, returns all definitions (no restriction).
        Silently ignores names that are not registered.
        """
        if not tool_names:
            return self.get_definitions()
        return [self._tools[n] for n in tool_names if n in self._tools]


def build_registry(
    project_root: str = ".",
    codeprism_client=None,           # CodePrismClient | None
    security_log: list | None = None,
    confirm_fn=None,                 # Callable[[str], bool] | None
    github_token: str | None = None,
    session_id: str | None = None,   # Phase 16: enables todo_* tools
    provider: str = "ollama",        # Phase 16: controls image encoding in vision tools
    # Phase 11 — web tools
    brave_api_key: str = "",
    searchx_api_key: str = "",
    searchx_base_url: str = "http://localhost:8888",
    search_provider: str = "searchx",
    # Phase 10 — hooks runner
    hook_runner=None,                # HookRunner | None
    # Phase 41 — extra dirs + diff confirm
    extra_dirs: list[str] | None = None,
    diff_confirm_fn=None,            # Callable[[str, str], bool] | None
) -> ToolRegistry:
    """Build and return the default tool registry with all built-in tools.

    codeprism_client:  enables cp_* graph tools + security gate on writes.
    security_log:      caller-owned list; security gate appends events to it.
    confirm_fn:        called on WARN-level writes; returns True to proceed.
    github_token:      enables all gh_* GitHub API tools.
    session_id:        enables todo_write / todo_read (Phase 16).
    provider:          LLM provider name; controls image content encoding (Phase 16).
    brave_api_key:     enables web_search via Brave Search API (Phase 11).
    searchx_api_key:   enables web_search via SearchX (Phase 11).
    searchx_base_url:  base URL of the SearchX instance (Phase 11).
    search_provider:   active search provider: 'brave' or 'searchx' (Phase 11).
    """
    from devagent.tools.file_tools import register_file_tools
    from devagent.tools.git_tools import register_git_tools
    from devagent.tools.search_tools import register_search_tools
    from devagent.tools.shell_tool import register_shell_tool

    registry = ToolRegistry(hook_runner=hook_runner)
    register_file_tools(registry, project_root, extra_dirs=extra_dirs, diff_confirm_fn=diff_confirm_fn)
    register_shell_tool(registry, project_root)
    register_search_tools(registry, project_root)
    register_git_tools(registry, project_root)

    if codeprism_client is not None:
        from devagent.tools.codeprism_tools import register_codeprism_tools
        from devagent.tools.security_gate import wrap_write_with_security

        register_codeprism_tools(registry, codeprism_client)

        for op in ("write_file", "edit_file"):
            original = registry._handlers.get(op)
            if original:
                registry._handlers[op] = wrap_write_with_security(
                    original,
                    codeprism_client,
                    project_root,
                    op.split("_")[0],
                    security_log=security_log,
                    confirm_fn=confirm_fn,
                )

    if github_token:
        from devagent.tools.github_tools import register_github_tools
        register_github_tools(registry, github_token)

    # Phase 11 — Web tools (fetch_url always; web_search when keys/base_url configured)
    from devagent.tools.web_tools import register_web_tools
    register_web_tools(
        registry,
        brave_api_key=brave_api_key,
        searchx_api_key=searchx_api_key,
        searchx_base_url=searchx_base_url,
        search_provider=search_provider,
    )

    # Phase 16 — Vision tools (always registered; provider controls image encoding)
    from devagent.tools.vision_tools import register_vision_tools
    register_vision_tools(registry, project_root, provider=provider)

    # Phase 16 — Notebook tools (optional: requires nbformat)
    try:
        import nbformat  # noqa: F401

        from devagent.tools.notebook_tools import register_notebook_tools
        register_notebook_tools(registry, project_root)
    except ImportError:
        pass

    # Phase 16 — Todo tools (optional: requires a session_id)
    if session_id:
        from devagent.tools.todo_tools import register_todo_tools
        register_todo_tools(registry, session_id)

    return registry
