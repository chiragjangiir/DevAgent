"""Phase 9 — Coordinator: task decomposition and synthesis.

The Coordinator calls the LLM once to decompose the user's task into a
DAG of subtasks, then calls it again at the end to synthesise all worker
results into a final answer.

Decomposition uses a single structured tool call (`submit_task_graph`) so
the LLM is forced to produce a machine-readable task list rather than free text.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from devagent.agent.task_graph import TaskGraph, TaskNode, WorkerType
from devagent.core.llm import AgentMessage, LLMClient, ToolDef

logger = logging.getLogger(__name__)

_DECOMPOSE_SYSTEM = """\
You are a task coordinator for a multi-agent AI coding team.
Your job is to break a user's coding task into small, independent subtasks
that can be worked on in parallel, then sequenced correctly using dependencies.

Rules for decomposition:
1. Each subtask must be concrete and actionable (a single developer could do it alone).
2. Assign the correct worker type:
   - implementer: writes or edits production code
   - tester: writes/runs tests — never edits production code
   - reviewer: reads and reviews code — no writes at all
3. Set depends_on to task IDs that must complete first.
   - Testers depend on the implementers whose code they test.
   - Reviewers depend on implementers.
   - Independent implementation subtasks have no dependencies (can run in parallel).
4. Aim for 2–6 subtasks.  Do not decompose trivial tasks.
5. Avoid file conflicts: two implementers should not edit the same file.

Call submit_task_graph exactly once with the full task list.
"""

_SYNTHESISE_SYSTEM = """\
You are a technical lead summarising the results of a multi-agent coding session.
Workers have completed their assigned subtasks.  Your job is to synthesise
their results into a clear, final summary for the user.

Include:
- What was implemented/changed and in which files
- Test results (pass/fail counts if available)
- Any issues or failures reported by workers
- What still needs to be done (if anything)

Be concise. Use markdown. Do not invent details not present in the worker results.
"""

_SUBMIT_TASK_GRAPH_TOOL = ToolDef(
    name="submit_task_graph",
    description="Submit the decomposed task graph.",
    parameters={
        "type": "object",
        "properties": {
            "tasks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "Short unique ID, e.g. 't1'"},
                        "description": {"type": "string"},
                        "worker_type": {
                            "type": "string",
                            "enum": ["implementer", "tester", "reviewer"],
                        },
                        "depends_on": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "IDs of tasks that must complete first",
                        },
                    },
                    "required": ["id", "description", "worker_type"],
                },
            }
        },
        "required": ["tasks"],
    },
)


@dataclass
class DecomposedTask:
    original_task: str
    nodes: list[TaskNode] = field(default_factory=list)


def decompose_task(
    llm: LLMClient,
    task: str,
    project_root: str,
) -> DecomposedTask:
    """Call LLM to decompose a task into a DAG of subtasks.

    Falls back to a single implementer task if the LLM call fails or
    produces an unparse-able response.
    """
    messages = [
        AgentMessage(role="system", content=_DECOMPOSE_SYSTEM),
        AgentMessage(
            role="user",
            content=(
                f"Project: {project_root}\n\n"
                f"Task to decompose:\n{task}\n\n"
                "Call submit_task_graph with the decomposed task list."
            ),
        ),
    ]

    try:
        response = llm.complete_with_tools(messages, tools=[_SUBMIT_TASK_GRAPH_TOOL])

        if response.has_tool_calls:
            tc = response.tool_calls[0]
            if tc.name == "submit_task_graph":
                raw_tasks: list[dict[str, Any]] = tc.args.get("tasks", [])
                nodes = [
                    TaskNode(
                        id=str(t.get("id", f"t{i+1}")),
                        description=str(t.get("description", "")),
                        worker_type=_safe_worker_type(t.get("worker_type", "implementer")),
                        depends_on=[str(d) for d in t.get("depends_on", [])],
                    )
                    for i, t in enumerate(raw_tasks)
                    if t.get("description")
                ]
                if nodes:
                    return DecomposedTask(original_task=task, nodes=nodes)

        # LLM returned text instead of a tool call — try to parse JSON from content
        if response.content:
            nodes = _parse_tasks_from_text(response.content, task)
            if nodes:
                return DecomposedTask(original_task=task, nodes=nodes)

    except Exception:
        logger.warning(
            "decompose_task: LLM call failed, falling back to single task",
            exc_info=True,
        )

    # Fallback: single implementer task
    return DecomposedTask(
        original_task=task,
        nodes=[TaskNode.make(task, worker_type="implementer")],
    )


def synthesise_results(llm: LLMClient, task: str, task_graph: TaskGraph) -> str:
    """Call LLM to synthesise all worker results into a final summary."""
    worker_summaries = []
    for node in task_graph.all_nodes():
        status_icon = "✓" if node.status == "done" else "✗"
        worker_summaries.append(
            f"{status_icon} [{node.worker_type}] {node.description}\n"
            f"   Result: {node.result or '(no output)'}\n"
            f"   Files: {', '.join(node.output_files) or 'none'}"
        )

    user_content = (
        f"Original task: {task}\n\n"
        "Worker results:\n"
        + "\n\n".join(worker_summaries)
    )

    messages = [
        AgentMessage(role="system", content=_SYNTHESISE_SYSTEM),
        AgentMessage(role="user", content=user_content),
    ]

    try:
        response = llm.complete_with_tools(messages, tools=[])
        return response.content.strip() or task_graph.summary()
    except Exception:
        logger.warning(
            "synthesise_results: LLM call failed, returning graph summary",
            exc_info=True,
        )
        return task_graph.summary()


def _safe_worker_type(value: Any) -> WorkerType:
    if value in ("implementer", "tester", "reviewer"):
        return value  # type: ignore[return-value]
    return "implementer"


def _parse_tasks_from_text(text: str, fallback_task: str) -> list[TaskNode]:
    """Try to parse a JSON array from free-form LLM text."""
    try:
        start = text.index("[")
        end = text.rindex("]") + 1
        raw = json.loads(text[start:end])
        if isinstance(raw, list) and raw:
            return [
                TaskNode(
                    id=str(t.get("id", f"t{i+1}")),
                    description=str(t.get("description", fallback_task)),
                    worker_type=_safe_worker_type(t.get("worker_type", "implementer")),
                    depends_on=[str(d) for d in t.get("depends_on", [])],
                )
                for i, t in enumerate(raw)
                if isinstance(t, dict)
            ]
    except (ValueError, KeyError, json.JSONDecodeError):
        pass
    return []
