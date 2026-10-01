"""Phase 9 — Multi-agent orchestration session.

OrchestratorSession is the top-level entry point for `devagent orchestrate`.
It wires together: coordinator decomposition → plan approval gate →
topological wave execution via ThreadPoolExecutor → synthesis.

Each wave executes all tasks whose dependencies are satisfied in parallel.
Workers run in daemon threads; the main thread collects results via join().
"""

from __future__ import annotations

from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from devagent.agent.coordinator import decompose_task, synthesise_results
from devagent.agent.loop import AgentEvent, ErrorEvent, FinalAnswerEvent, StatusEvent, ThinkingEvent
from devagent.agent.task_graph import TaskGraph, TaskNode
from devagent.agent.worker import Worker, WorkerResult
from devagent.session.manager import SessionManager


class OrchestratorSession:
    """Orchestrates multiple worker agents to complete a large task.

    Usage::

        session = OrchestratorSession(cfg, project_root, max_workers=4)
        for event in session.run("implement the payments module"):
            render(event)
    """

    def __init__(
        self,
        cfg: Any,                    # DevAgentConfig
        project_root: str | Path,
        max_workers: int = 4,
        plan_mode: bool = False,
        worker_max_iterations: int | None = None,
        worker_max_repair: int | None = None,
    ) -> None:
        from devagent.core.llm import LLMClient

        self._cfg = cfg
        self._project_root = str(Path(project_root).resolve())
        self._max_workers = max_workers
        self._plan_mode = plan_mode
        # Both worker limits default to their configured value (agent.*), so the
        # orchestrator path honours the config the same way the interactive loop
        # does; an explicit argument still overrides it.
        self._worker_max_iters = (
            cfg.agent.max_iterations
            if worker_max_iterations is None
            else worker_max_iterations
        )
        self._worker_max_repair = (
            cfg.agent.max_repair_iterations
            if worker_max_repair is None
            else worker_max_repair
        )

        mgr = SessionManager()
        self._session_id = mgr.new(
            project=self._project_root,
            model=cfg.llm.model,
            provider=cfg.llm.provider,
            title="[orchestrator]",
        )
        self._mgr = mgr
        self._llm = LLMClient(cfg.llm)

    @property
    def session_id(self) -> str:
        return self._session_id

    def run(self, task: str) -> Generator[AgentEvent, None, None]:
        """Full orchestration pipeline as an event generator."""
        # 1. Decompose
        yield ThinkingEvent("Decomposing task into subtasks...")
        decomposed = decompose_task(self._llm, task, self._project_root)

        if not decomposed.nodes:
            yield ErrorEvent("Coordinator produced an empty task graph.")
            return

        # 2. Plan approval gate (optional)
        if self._plan_mode:
            approved = _show_plan_and_confirm(decomposed.nodes)
            if not approved:
                yield ThinkingEvent("Orchestration cancelled by user.")
                return

        # 3. Build task graph and persist
        graph = TaskGraph(self._session_id)
        for node in decomposed.nodes:
            graph.add(node)

        yield ThinkingEvent(
            f"Starting orchestration: {len(decomposed.nodes)} subtasks, "
            f"up to {self._max_workers} parallel workers.\n"
            + graph.summary()
        )

        # 4. Execute in topological waves
        wave = 0
        while not graph.is_complete():
            ready = graph.ready_tasks()
            if not ready:
                if not graph.is_complete():
                    yield ErrorEvent(
                        "Task graph deadlock: no ready tasks but graph is not complete. "
                        "Check for circular dependencies."
                    )
                break

            wave += 1
            yield StatusEvent(
                status_line=f"wave {wave}: {len(ready)} task(s) running in parallel",
                iteration=wave,
            )

            batch_results = self._run_wave(ready, graph)

            for result in batch_results:
                node = next((n for n in graph.all_nodes() if n.id == result.task_id), None)
                if node is None:
                    continue

                if result.success:
                    graph.mark_done(
                        result.task_id,
                        result=result.output,
                        output_files=result.output_files,
                    )
                    yield ThinkingEvent(
                        f"[{result.worker_type}] {node.description}\n"
                        f"  Done. Files: {', '.join(result.output_files) or 'none'}\n"
                        f"  {result.output[:200]}"
                    )
                else:
                    graph.mark_failed(result.task_id, result=result.error or result.output)
                    yield ErrorEvent(
                        f"[{result.worker_type}] {node.description} FAILED: "
                        f"{result.error or result.output}"
                    )

        # 5. Synthesise
        yield ThinkingEvent("Synthesising results...")
        final_summary = synthesise_results(self._llm, task, graph)

        yield FinalAnswerEvent(text=final_summary)

    def _build_dep_context(self, task: TaskNode, graph: TaskGraph) -> str:
        """Build a summary of completed dependency results for a worker task.

        Gives each worker visibility into the work done by the tasks it depends
        on, so it can make informed decisions without calling read_peer_results.
        """
        if not task.depends_on:
            return ""
        all_nodes = {n.id: n for n in graph.all_nodes()}
        parts: list[str] = []
        for dep_id in task.depends_on:
            dep = all_nodes.get(dep_id)
            if dep and dep.status == "done" and dep.result:
                files = ", ".join(dep.output_files) or "none"
                snippet = dep.result[:400]
                parts.append(
                    f"- [{dep.worker_type}] {dep.description}\n"
                    f"  Files: {files}\n"
                    f"  Summary: {snippet}"
                )
        return "\n".join(parts)

    def _run_wave(self, tasks: list[TaskNode], graph: TaskGraph) -> list[WorkerResult]:
        """Execute a parallel wave of tasks; returns results in completion order."""
        workers = [
            Worker(
                task=task,
                cfg=self._cfg,
                project_root=self._project_root,
                coordinator_session_id=self._session_id,
                max_iterations=self._worker_max_iters,
                max_repair=self._worker_max_repair,
                dep_context=self._build_dep_context(task, graph),
            )
            for task in tasks
        ]

        # Mark all as running before spawning threads
        for task in tasks:
            graph.mark_running(task.id)

        results: list[WorkerResult] = []

        with ThreadPoolExecutor(max_workers=min(len(workers), self._max_workers)) as pool:
            futures = {pool.submit(w.run): w for w in workers}
            for future in as_completed(futures):
                try:
                    result = future.result()
                except Exception as exc:
                    worker = futures[future]
                    result = WorkerResult(
                        task_id=worker._task.id,
                        worker_type=worker._task.worker_type,
                        success=False,
                        output="",
                        error=str(exc),
                    )
                results.append(result)

        return results


def _show_plan_and_confirm(nodes: list[TaskNode]) -> bool:
    """Rich interactive plan display. Returns True if user approves."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt

    console = Console()
    lines = []
    for i, node in enumerate(nodes, 1):
        deps = f" (after: {', '.join(node.depends_on)})" if node.depends_on else ""
        lines.append(f"  Step {i}  [{node.worker_type}]  {node.description}{deps}")

    console.print(Panel(
        "\n".join(lines),
        title="[bold cyan]Orchestration Plan[/bold cyan]",
        border_style="cyan",
    ))

    choice = Prompt.ask("[A]pprove / [C]ancel", choices=["a", "c", "A", "C"], default="a")
    return choice.lower() == "a"
