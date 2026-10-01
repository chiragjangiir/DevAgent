"""Phase 14 — Advanced agent architecture tests.

Covers: spawn_agent tool, read_peer_results tool, dep_context injection,
and Worker registration of orchestration tools.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_registry(project_root: str = "."):
    from devagent.tools.registry import build_registry
    return build_registry(project_root=project_root)


def _make_cfg():
    from devagent.core.config import DevAgentConfig
    return DevAgentConfig()


# ---------------------------------------------------------------------------
# spawn_agent tool registration
# ---------------------------------------------------------------------------

class TestSpawnAgentRegistration:
    def test_registered_in_registry(self, tmp_path: Path) -> None:
        from devagent.tools.agent_tools import register_agent_tools
        reg = _make_registry(str(tmp_path))
        register_agent_tools(reg, _make_cfg(), str(tmp_path))
        assert "spawn_agent" in reg.names()

    def test_missing_task_returns_error(self, tmp_path: Path) -> None:
        from devagent.tools.agent_tools import register_agent_tools
        reg = _make_registry(str(tmp_path))
        register_agent_tools(reg, _make_cfg(), str(tmp_path))
        result = reg.call("spawn_agent", {"worker_type": "implementer"})
        assert result.startswith("[error]")

    def test_invalid_worker_type_returns_error(self, tmp_path: Path) -> None:
        from devagent.tools.agent_tools import register_agent_tools
        reg = _make_registry(str(tmp_path))
        register_agent_tools(reg, _make_cfg(), str(tmp_path))
        result = reg.call("spawn_agent", {"task": "do something", "worker_type": "wizard"})
        assert result.startswith("[error]")

    def test_spawn_calls_worker_run(self, tmp_path: Path) -> None:
        from devagent.agent.worker import WorkerResult
        from devagent.tools.agent_tools import register_agent_tools

        mock_result = WorkerResult(
            task_id="abc",
            worker_type="implementer",
            success=True,
            output="Done.",
            output_files=["src/foo.py"],
        )

        with patch("devagent.tools.agent_tools.Worker") as MockWorker:
            instance = MagicMock()
            instance.run.return_value = mock_result
            MockWorker.return_value = instance

            reg = _make_registry(str(tmp_path))
            register_agent_tools(reg, _make_cfg(), str(tmp_path))
            result = reg.call("spawn_agent", {"task": "write tests", "worker_type": "tester"})

        assert "succeeded" in result
        assert "Done." in result
        assert "src/foo.py" in result

    def test_spawn_failed_worker_shows_failed(self, tmp_path: Path) -> None:
        from devagent.agent.worker import WorkerResult
        from devagent.tools.agent_tools import register_agent_tools

        mock_result = WorkerResult(
            task_id="xyz",
            worker_type="implementer",
            success=False,
            output="",
            error="LLM timeout",
        )

        with patch("devagent.tools.agent_tools.Worker") as MockWorker:
            instance = MagicMock()
            instance.run.return_value = mock_result
            MockWorker.return_value = instance

            reg = _make_registry(str(tmp_path))
            register_agent_tools(reg, _make_cfg(), str(tmp_path))
            result = reg.call("spawn_agent", {"task": "fix bug"})

        assert "failed" in result

    def test_spawn_no_files_omits_files_line(self, tmp_path: Path) -> None:
        from devagent.agent.worker import WorkerResult
        from devagent.tools.agent_tools import register_agent_tools

        mock_result = WorkerResult(
            task_id="abc", worker_type="reviewer",
            success=True, output="LGTM.", output_files=[],
        )

        with patch("devagent.tools.agent_tools.Worker") as MockWorker:
            instance = MagicMock()
            instance.run.return_value = mock_result
            MockWorker.return_value = instance

            reg = _make_registry(str(tmp_path))
            register_agent_tools(reg, _make_cfg(), str(tmp_path))
            result = reg.call("spawn_agent", {"task": "review", "worker_type": "reviewer"})

        assert "Files modified" not in result

    def test_spawn_uses_configured_max_iterations(self, tmp_path: Path) -> None:
        """The sub-agent must honour agent.max_iterations, not a hardcoded 20."""
        from devagent.agent.worker import WorkerResult
        from devagent.tools.agent_tools import register_agent_tools

        cfg = _make_cfg()
        cfg.agent.max_iterations = 33

        mock_result = WorkerResult(
            task_id="abc", worker_type="implementer",
            success=True, output="Done.", output_files=[],
        )

        with patch("devagent.tools.agent_tools.Worker") as MockWorker:
            instance = MagicMock()
            instance.run.return_value = mock_result
            MockWorker.return_value = instance

            reg = _make_registry(str(tmp_path))
            register_agent_tools(reg, cfg, str(tmp_path))
            reg.call("spawn_agent", {"task": "do it", "worker_type": "implementer"})

        assert MockWorker.call_args.kwargs["max_iterations"] == 33


# ---------------------------------------------------------------------------
# read_peer_results tool
# ---------------------------------------------------------------------------

class TestReadPeerResults:
    def test_registered_when_coordinator_id_given(self, tmp_path: Path) -> None:
        from devagent.tools.agent_tools import register_orchestration_tools
        reg = _make_registry(str(tmp_path))
        register_orchestration_tools(reg, "sess-coord-001")
        assert "read_peer_results" in reg.names()

    def test_returns_no_results_when_empty(self, tmp_path: Path) -> None:
        from devagent.tools.agent_tools import register_orchestration_tools
        reg = _make_registry(str(tmp_path))
        register_orchestration_tools(reg, "sess-coord-001")

        with patch("devagent.tools.agent_tools.store") as mock_store:
            mock_store.get_tasks.return_value = []
            result = reg.call("read_peer_results", {})

        assert "No completed" in result

    def test_returns_done_task_summaries(self, tmp_path: Path) -> None:
        from devagent.tools.agent_tools import register_orchestration_tools
        reg = _make_registry(str(tmp_path))
        register_orchestration_tools(reg, "sess-coord-001")

        tasks = [
            {"status": "done", "result": "Implemented auth module", "description": "auth", "worker_type": "implementer", "output_files": ["auth.py"]},
            {"status": "pending", "result": "", "description": "tests", "worker_type": "tester", "output_files": []},
        ]

        with patch("devagent.tools.agent_tools.store") as mock_store:
            mock_store.get_tasks.return_value = tasks
            result = reg.call("read_peer_results", {})

        assert "auth" in result
        assert "Implemented auth module" in result
        assert "tests" not in result  # pending task not included

    def test_filters_by_worker_type(self, tmp_path: Path) -> None:
        from devagent.tools.agent_tools import register_orchestration_tools
        reg = _make_registry(str(tmp_path))
        register_orchestration_tools(reg, "sess-coord-001")

        tasks = [
            {"status": "done", "result": "code written", "description": "impl", "worker_type": "implementer", "output_files": []},
            {"status": "done", "result": "tests pass", "description": "tests", "worker_type": "tester", "output_files": []},
        ]

        with patch("devagent.tools.agent_tools.store") as mock_store:
            mock_store.get_tasks.return_value = tasks
            result = reg.call("read_peer_results", {"worker_type": "tester"})

        assert "tests pass" in result
        assert "code written" not in result


# ---------------------------------------------------------------------------
# Dependency context injection
# ---------------------------------------------------------------------------

class TestDepContext:
    def test_dep_context_passed_to_worker(self) -> None:
        from devagent.agent.task_graph import TaskNode
        from devagent.agent.worker import Worker
        node = TaskNode.make("write feature", "implementer", depends_on=[])
        w = Worker(
            task=node,
            cfg=_make_cfg(),
            project_root=".",
            coordinator_session_id="",
            dep_context="- [implementer] prior task\n  Files: auth.py\n  Summary: Done",
        )
        assert "prior task" in w._dep_context

    def test_orchestrator_builds_dep_context(self) -> None:
        from devagent.agent.orchestrator import OrchestratorSession
        from devagent.agent.task_graph import TaskGraph, TaskNode

        # Build a minimal graph with two tasks, B depends on A
        node_a = TaskNode.make("task A", "implementer")
        node_b = TaskNode.make("task B", "tester", depends_on=[node_a.id])

        # Simulate A being done
        node_a.status = "done"
        node_a.result = "A finished successfully"
        node_a.output_files = ["a.py"]

        graph = TaskGraph.__new__(TaskGraph)
        graph._session_id = "s"
        graph._db_path = None
        graph._nodes = {node_a.id: node_a, node_b.id: node_b}

        with patch("devagent.session.manager.SessionManager"):
            session = OrchestratorSession.__new__(OrchestratorSession)
            session._cfg = _make_cfg()
            session._project_root = "."
            session._max_workers = 2
            session._worker_max_iters = 20
            session._session_id = "orch-sess"

        ctx = session._build_dep_context(node_b, graph)
        assert "task A" in ctx
        assert "A finished successfully" in ctx
        assert "a.py" in ctx

    def test_no_deps_gives_empty_context(self) -> None:
        from devagent.agent.orchestrator import OrchestratorSession
        from devagent.agent.task_graph import TaskGraph, TaskNode

        node = TaskNode.make("standalone", "implementer")
        graph = TaskGraph.__new__(TaskGraph)
        graph._session_id = "s"
        graph._db_path = None
        graph._nodes = {node.id: node}

        session = OrchestratorSession.__new__(OrchestratorSession)
        session._cfg = _make_cfg()
        session._project_root = "."
        session._max_workers = 2
        session._worker_max_iters = 20
        session._session_id = "orch-sess"

        ctx = session._build_dep_context(node, graph)
        assert ctx == ""

    def test_dep_context_in_task_message(self) -> None:
        """Worker includes dep_context in the task message sent to AgentLoop."""
        from devagent.agent.loop import FinalAnswerEvent
        from devagent.agent.task_graph import TaskNode
        from devagent.agent.worker import Worker

        node = TaskNode.make("run tests", "tester")

        captured: list[str] = []

        def fake_loop_run(message: str):
            captured.append(message)
            yield FinalAnswerEvent(text="done")

        w = Worker(
            task=node, cfg=_make_cfg(), project_root=".",
            coordinator_session_id="", dep_context="dep: prior work done",
        )

        with patch("devagent.agent.loop.AgentLoop") as MockLoop, \
             patch("devagent.session.manager.SessionManager") as MockMgr, \
             patch("devagent.core.llm.LLMClient"), \
             patch("devagent.tools.registry.build_registry") as MockReg:

            mock_mgr = MagicMock()
            mock_mgr.new.return_value = "worker-sess"
            mock_mgr.get_events.return_value = []
            MockMgr.return_value = mock_mgr

            mock_reg = MagicMock()
            mock_reg.get_definitions.return_value = []
            MockReg.return_value = mock_reg

            mock_loop_instance = MagicMock()
            mock_loop_instance.run.side_effect = fake_loop_run
            MockLoop.return_value = mock_loop_instance

            w.run()

        assert captured
        assert "dep: prior work done" in captured[0]
        assert "Prior work" in captured[0]
