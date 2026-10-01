"""Phase 14 — Agent spawning and peer coordination tools.

spawn_agent     — lets an agent delegate a sub-task to a new worker agent
read_peer_results — lets orchestration workers query completed peer results
"""

from __future__ import annotations

from typing import Any

from devagent.agent.task_graph import TaskNode
from devagent.agent.worker import Worker
from devagent.session import store
from devagent.tools.registry import ToolRegistry


def register_agent_tools(
    registry: ToolRegistry,
    cfg: Any,           # DevAgentConfig
    project_root: str,
) -> None:
    """Register spawn_agent so any session can delegate work to a sub-agent."""

    def spawn_agent(args: dict) -> str:
        task = args.get("task", "").strip()
        worker_type = args.get("worker_type", "implementer")
        if not task:
            return "[error] task is required"
        if worker_type not in ("implementer", "tester", "reviewer"):
            return "[error] worker_type must be one of: implementer, tester, reviewer"

        node = TaskNode.make(description=task, worker_type=worker_type)
        worker = Worker(
            task=node,
            cfg=cfg,
            project_root=project_root,
            coordinator_session_id="",
            max_iterations=cfg.agent.max_iterations,
        )
        result = worker.run()

        status = "succeeded" if result.success else "failed"
        files_part = (
            f"\nFiles modified: {', '.join(result.output_files)}"
            if result.output_files
            else ""
        )
        return f"[sub-agent:{worker_type}] {status}\n\n{result.output}{files_part}"

    registry.register(
        "spawn_agent",
        (
            "Spawn a sub-agent to complete a specific sub-task. "
            "The sub-agent runs and returns its result. "
            "Use this to delegate specialised work (testing, reviewing, implementation) "
            "without doing it yourself."
        ),
        {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Clear description of the sub-task to complete",
                },
                "worker_type": {
                    "type": "string",
                    "enum": ["implementer", "tester", "reviewer"],
                    "description": (
                        "Role: implementer (write/edit code), "
                        "tester (write and run tests), "
                        "reviewer (read-only code review)"
                    ),
                    "default": "implementer",
                },
            },
            "required": ["task"],
        },
        spawn_agent,
    )


def register_orchestration_tools(
    registry: ToolRegistry,
    coordinator_session_id: str,
) -> None:
    """Register read_peer_results for workers inside an OrchestratorSession.

    Enables light inter-worker coordination: a worker can inspect what
    completed peers have already done before starting its own work.
    """

    def read_peer_results(args: dict) -> str:
        worker_type_filter = args.get("worker_type", "")
        tasks = store.get_tasks(coordinator_session_id)
        done = [t for t in tasks if t["status"] == "done" and t.get("result")]
        if worker_type_filter:
            done = [t for t in done if t.get("worker_type") == worker_type_filter]
        if not done:
            return "No completed peer results yet."

        parts = []
        for t in done:
            snippet = t["result"][:600]
            files = ", ".join(t.get("output_files") or []) or "none"
            parts.append(
                f"Task: {t['description']}\n"
                f"Files: {files}\n"
                f"Result:\n{snippet}"
            )
        return "\n\n---\n\n".join(parts)

    registry.register(
        "read_peer_results",
        (
            "Read the results of completed peer tasks in this orchestration session. "
            "Use this to understand what other agents have already done before starting work."
        ),
        {
            "type": "object",
            "properties": {
                "worker_type": {
                    "type": "string",
                    "enum": ["implementer", "tester", "reviewer"],
                    "description": "Optional: filter results by worker type",
                },
            },
        },
        read_peer_results,
    )
