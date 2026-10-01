"""Phase 9 — Worker agents for multi-agent orchestration.

Each worker is an isolated AgentLoop running in a thread.  Workers have
restricted tool sets depending on their type:

  implementer  — full file + shell + git tools; can write code
  tester       — write_file (test files only), run_shell; no prod edits
  reviewer     — read-only tools; produces a text review, no writes

Workers communicate results back to the Coordinator via a WorkerResult
dataclass returned from Worker.run().
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from devagent.agent.task_graph import TaskNode, WorkerType

# Tool sets per worker type
_IMPLEMENTER_TOOLS: list[str] = []   # empty = all tools
_TESTER_TOOLS: list[str] = [
    "write_file", "read_file", "list_files", "grep",
    "run_shell", "git_status", "git_diff",
]
_REVIEWER_TOOLS: list[str] = [
    "read_file", "list_files", "grep", "git_diff", "git_status",
]

WORKER_TOOL_SETS: dict[WorkerType, list[str]] = {
    "implementer": _IMPLEMENTER_TOOLS,
    "tester": _TESTER_TOOLS,
    "reviewer": _REVIEWER_TOOLS,
}

# System prompt supplements per worker type
_WORKER_ROLE_HINTS: dict[WorkerType, str] = {
    "implementer": (
        "You are an implementer worker in a multi-agent coding team.\n"
        "Your job: implement the assigned subtask by writing or editing code.\n"
        "Focus only on your assigned files. Do not touch files assigned to other workers.\n"
        "When done, produce a concise summary of what you changed and why."
    ),
    "tester": (
        "You are a tester worker in a multi-agent coding team.\n"
        "Your job: write tests for the assigned code and run them.\n"
        "Do not modify production code — only test files.\n"
        "Report which tests pass, which fail, and what the failures mean."
    ),
    "reviewer": (
        "You are a reviewer worker in a multi-agent coding team.\n"
        "Your job: read the assigned code and produce a quality review.\n"
        "Do NOT modify any files. Read-only.\n"
        "Report: bugs found, security issues, missing error handling, style problems."
    ),
}


@dataclass
class WorkerResult:
    task_id: str
    worker_type: WorkerType
    success: bool
    output: str                          # final LLM text summary
    output_files: list[str] = field(default_factory=list)
    error: str = ""


class Worker:
    """Runs one TaskNode in a thread using a dedicated AgentLoop."""

    def __init__(
        self,
        task: TaskNode,
        cfg: Any,                         # DevAgentConfig
        project_root: str,
        coordinator_session_id: str,      # parent session for context
        max_iterations: int = 20,
        max_repair: int | None = None,    # None = use cfg.agent.max_repair_iterations
        dep_context: str = "",            # Phase 14: completed dependency summaries
    ) -> None:
        self._task = task
        self._cfg = cfg
        self._project_root = project_root
        self._coordinator_session_id = coordinator_session_id
        self._max_iterations = max_iterations
        self._max_repair = max_repair
        self._dep_context = dep_context
        self._thread: threading.Thread | None = None
        self._result: WorkerResult | None = None

    # ------------------------------------------------------------------
    # Run (called inside a thread)
    # ------------------------------------------------------------------

    def run(self) -> WorkerResult:
        from devagent.agent.loop import AgentLoop, ErrorEvent, FinalAnswerEvent
        from devagent.agent.system_prompt import build_worker_system_prompt
        from devagent.core.llm import LLMClient
        from devagent.session.budget import TokenBudget
        from devagent.session.manager import SessionManager
        from devagent.session.memory import MemoryBlock
        from devagent.tools.registry import ToolRegistry, build_registry

        try:
            mgr = SessionManager()
            session_id = mgr.new(
                project=self._project_root,
                model=self._cfg.llm.model,
                provider=self._cfg.llm.provider,
                title=f"[worker:{self._task.worker_type}] {self._task.description[:60]}",
            )
            self._task.assigned_session = session_id

            registry: ToolRegistry = build_registry(
                project_root=self._project_root,
                github_token=self._cfg.github.token or None,
            )

            # Apply tool restrictions for this worker type
            tool_names = WORKER_TOOL_SETS.get(self._task.worker_type, [])
            if tool_names:
                registry.get_definitions = lambda _t=tool_names: registry.get_restricted_definitions(_t)  # type: ignore[method-assign]

            llm = LLMClient(self._cfg.llm)
            budget = TokenBudget(max_tokens=None, warn_at_percent=90)
            memory = MemoryBlock(session_id)

            system_prompt = build_worker_system_prompt(
                worker_type=self._task.worker_type,
                project_root=self._project_root,
            )

            loop = AgentLoop(
                llm=llm,
                registry=registry,
                session_mgr=mgr,
                session_id=session_id,
                memory=memory,
                budget=budget,
                system_prompt=system_prompt,
                max_iterations=self._max_iterations,
                max_repair=(
                    self._max_repair
                    if self._max_repair is not None
                    else self._cfg.agent.max_repair_iterations
                ),
                loop_detection=True,
            )

            # Phase 14: register orchestration tools when coordinator session is known
            if self._coordinator_session_id:
                from devagent.tools.agent_tools import register_orchestration_tools
                register_orchestration_tools(registry, self._coordinator_session_id)

            # Phase 14: register spawn_agent so workers can delegate further
            from devagent.tools.agent_tools import register_agent_tools
            register_agent_tools(registry, self._cfg, self._project_root)

            dep_section = (
                f"\n\n## Prior work by dependency tasks\n{self._dep_context}"
                if self._dep_context
                else ""
            )
            task_message = (
                f"Task: {self._task.description}\n\n"
                f"Project root: {self._project_root}"
                f"{dep_section}\n\n"
                "Complete this task and produce a concise summary of what you did."
            )

            final_text = ""
            had_error = False
            modified_files: list[str] = []

            for event in loop.run(task_message):
                if isinstance(event, FinalAnswerEvent):
                    final_text = event.text
                elif isinstance(event, ErrorEvent):
                    had_error = True
                    final_text = f"[error] {event.message}"

            # Collect modified files from the session events
            events = mgr.get_events(session_id)
            for ev in events:
                for tc in (ev.get("tool_calls") or []):
                    if tc.get("name") in ("write_file", "edit_file"):
                        path = tc.get("args", {}).get("path", "")
                        if path and path not in modified_files:
                            modified_files.append(path)

            return WorkerResult(
                task_id=self._task.id,
                worker_type=self._task.worker_type,
                success=not had_error,
                output=final_text or "(no output)",
                output_files=modified_files,
            )

        except Exception as exc:
            return WorkerResult(
                task_id=self._task.id,
                worker_type=self._task.worker_type,
                success=False,
                output="",
                error=str(exc),
            )

    def run_in_thread(self) -> threading.Thread:
        self._thread = threading.Thread(target=self._run_and_store, daemon=True)
        self._thread.start()
        return self._thread

    def _run_and_store(self) -> None:
        self._result = self.run()

    def join(self) -> WorkerResult:
        if self._thread:
            self._thread.join()
        return self._result or WorkerResult(
            task_id=self._task.id,
            worker_type=self._task.worker_type,
            success=False,
            output="",
            error="Worker thread did not complete",
        )
