"""Phase 9 tests: multi-agent orchestration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cfg(provider="ollama", model="qwen2.5-coder:7b"):
    from devagent.core.config import DevAgentConfig, GitHubConfig, LLMConfig
    return DevAgentConfig(
        llm=LLMConfig(provider=provider, model=model),
        github=GitHubConfig(token=""),
    )


def _make_llm_mock(tool_call_name=None, tool_call_args=None, content=""):
    from devagent.core.llm import LLMConfig, LLMResponse, ToolCallRequest
    mock = MagicMock()
    mock.cfg = LLMConfig(provider="ollama", model="qwen2.5-coder:7b")
    tool_calls = []
    if tool_call_name:
        tool_calls = [ToolCallRequest(id="tc1", name=tool_call_name, args=tool_call_args or {})]
    mock.complete_with_tools.return_value = LLMResponse(
        content=content,
        tool_calls=tool_calls,
        input_tokens=100,
        output_tokens=50,
    )
    return mock


# ---------------------------------------------------------------------------
# 1. TaskNode & TaskGraph
# ---------------------------------------------------------------------------

def test_task_node_defaults():
    from devagent.agent.task_graph import TaskNode
    node = TaskNode.make("implement auth module")
    assert node.description == "implement auth module"
    assert node.worker_type == "implementer"
    assert node.depends_on == []
    assert node.status == "pending"
    assert node.result == ""
    assert len(node.id) > 0


def test_task_node_make_with_deps():
    from devagent.agent.task_graph import TaskNode
    n1 = TaskNode.make("impl", "implementer")
    n2 = TaskNode.make("test", "tester", depends_on=[n1.id])
    assert n1.id in n2.depends_on


def test_task_graph_ready_tasks_no_deps(tmp_path):
    db = tmp_path / "test.db"
    from devagent.agent.task_graph import TaskGraph, TaskNode
    from devagent.session import store
    store.init_schema(db_path=db)
    store.create_session("sess", db_path=db)

    graph = TaskGraph("sess", db_path=db)
    n1 = TaskNode.make("task A")
    n2 = TaskNode.make("task B")
    graph.add(n1)
    graph.add(n2)

    ready = graph.ready_tasks()
    assert len(ready) == 2


def test_task_graph_dependency_blocks_until_done(tmp_path):
    db = tmp_path / "test.db"
    from devagent.agent.task_graph import TaskGraph, TaskNode
    from devagent.session import store
    store.init_schema(db_path=db)
    store.create_session("sess2", db_path=db)

    graph = TaskGraph("sess2", db_path=db)
    n1 = TaskNode.make("impl")
    n2 = TaskNode.make("test", "tester", depends_on=[n1.id])
    graph.add(n1)
    graph.add(n2)

    ready = graph.ready_tasks()
    assert len(ready) == 1
    assert ready[0].id == n1.id

    graph.mark_done(n1.id, result="done impl")
    ready2 = graph.ready_tasks()
    assert len(ready2) == 1
    assert ready2[0].id == n2.id


def test_task_graph_is_complete(tmp_path):
    db = tmp_path / "test.db"
    from devagent.agent.task_graph import TaskGraph, TaskNode
    from devagent.session import store
    store.init_schema(db_path=db)
    store.create_session("sess3", db_path=db)

    graph = TaskGraph("sess3", db_path=db)
    n1 = TaskNode.make("only task")
    graph.add(n1)
    assert not graph.is_complete()
    graph.mark_done(n1.id, result="ok")
    assert graph.is_complete()


def test_task_graph_mark_failed(tmp_path):
    db = tmp_path / "test.db"
    from devagent.agent.task_graph import TaskGraph, TaskNode
    from devagent.session import store
    store.init_schema(db_path=db)
    store.create_session("sess4", db_path=db)

    graph = TaskGraph("sess4", db_path=db)
    n = TaskNode.make("risky task")
    graph.add(n)
    graph.mark_failed(n.id, result="timeout")
    assert graph.has_failures()
    assert graph.is_complete()


def test_task_graph_summary_contains_nodes(tmp_path):
    db = tmp_path / "test.db"
    from devagent.agent.task_graph import TaskGraph, TaskNode
    from devagent.session import store
    store.init_schema(db_path=db)
    store.create_session("sess5", db_path=db)

    graph = TaskGraph("sess5", db_path=db)
    n = TaskNode.make("build the feature")
    graph.add(n)
    summary = graph.summary()
    assert "build the feature" in summary


# ---------------------------------------------------------------------------
# 2. Store — task_graph and file_locks tables
# ---------------------------------------------------------------------------

def test_upsert_and_get_tasks(tmp_path):
    db = tmp_path / "test.db"
    from devagent.session import store
    store.init_schema(db_path=db)
    store.create_session("s1", db_path=db)
    store.upsert_task("s1", "t1", "do thing", db_path=db)
    tasks = store.get_tasks("s1", db_path=db)
    assert len(tasks) == 1
    assert tasks[0]["id"] == "t1"
    assert tasks[0]["description"] == "do thing"


def test_update_task_status(tmp_path):
    db = tmp_path / "test.db"
    from devagent.session import store
    store.init_schema(db_path=db)
    store.create_session("s2", db_path=db)
    store.upsert_task("s2", "t1", "task", db_path=db)
    store.update_task_status("s2", "t1", "done", result="finished", db_path=db)
    tasks = store.get_tasks("s2", db_path=db)
    assert tasks[0]["status"] == "done"
    assert tasks[0]["result"] == "finished"


def test_file_lock_acquire_release(tmp_path):
    db = tmp_path / "test.db"
    from devagent.session import store
    store.init_schema(db_path=db)
    store.create_session("s3", db_path=db)

    ok = store.acquire_file_lock("s3", "src/auth.py", "worker-1", db_path=db)
    assert ok is True

    store.release_file_lock("s3", "src/auth.py", "worker-1", db_path=db)
    locks = store.get_file_locks("s3", db_path=db)
    assert len(locks) == 0


def test_file_lock_conflict(tmp_path):
    db = tmp_path / "test.db"
    from devagent.session import store
    store.init_schema(db_path=db)
    store.create_session("s4", db_path=db)

    ok1 = store.acquire_file_lock("s4", "src/auth.py", "worker-1", db_path=db)
    ok2 = store.acquire_file_lock("s4", "src/auth.py", "worker-2", db_path=db)
    assert ok1 is True
    assert ok2 is False  # already locked


def test_file_lock_release_allows_reacquire(tmp_path):
    db = tmp_path / "test.db"
    from devagent.session import store
    store.init_schema(db_path=db)
    store.create_session("s5", db_path=db)

    store.acquire_file_lock("s5", "auth.py", "w1", db_path=db)
    store.release_file_lock("s5", "auth.py", "w1", db_path=db)
    ok = store.acquire_file_lock("s5", "auth.py", "w2", db_path=db)
    assert ok is True


def test_release_all_worker_locks(tmp_path):
    db = tmp_path / "test.db"
    from devagent.session import store
    store.init_schema(db_path=db)
    store.create_session("s6", db_path=db)

    store.acquire_file_lock("s6", "a.py", "w1", db_path=db)
    store.acquire_file_lock("s6", "b.py", "w1", db_path=db)
    store.release_all_worker_locks("s6", "w1", db_path=db)
    assert store.get_file_locks("s6", db_path=db) == []


# ---------------------------------------------------------------------------
# 3. Coordinator — decompose_task
# ---------------------------------------------------------------------------

def test_decompose_task_from_tool_call():
    from devagent.agent.coordinator import decompose_task
    llm = _make_llm_mock(
        tool_call_name="submit_task_graph",
        tool_call_args={
            "tasks": [
                {"id": "t1", "description": "implement login", "worker_type": "implementer", "depends_on": []},
                {"id": "t2", "description": "write tests", "worker_type": "tester", "depends_on": ["t1"]},
            ]
        },
    )
    result = decompose_task(llm, "add login feature", "/project")
    assert len(result.nodes) == 2
    assert result.nodes[0].id == "t1"
    assert result.nodes[1].worker_type == "tester"
    assert "t1" in result.nodes[1].depends_on


def test_decompose_task_fallback_on_empty_tool_call():
    from devagent.agent.coordinator import decompose_task
    llm = _make_llm_mock(
        tool_call_name="submit_task_graph",
        tool_call_args={"tasks": []},
        content="",
    )
    result = decompose_task(llm, "do something", "/project")
    assert len(result.nodes) == 1
    assert result.nodes[0].description == "do something"


def test_decompose_task_fallback_on_llm_error():
    from devagent.agent.coordinator import decompose_task
    mock = MagicMock()
    mock.cfg = MagicMock()
    mock.cfg.provider = "ollama"
    mock.cfg.model = "qwen2.5-coder:7b"
    mock.complete_with_tools.side_effect = RuntimeError("network error")
    result = decompose_task(mock, "task", "/project")
    assert len(result.nodes) == 1  # single fallback task


def test_decompose_task_fallback_on_llm_error_logs_warning(caplog):
    import logging

    from devagent.agent.coordinator import decompose_task

    mock = MagicMock()
    mock.cfg = MagicMock()
    mock.cfg.provider = "ollama"
    mock.cfg.model = "qwen2.5-coder:7b"
    mock.complete_with_tools.side_effect = RuntimeError("network error")
    with caplog.at_level(logging.WARNING, logger="devagent.agent.coordinator"):
        result = decompose_task(mock, "task", "/project")

    assert len(result.nodes) == 1
    warnings = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING
        and "decompose_task: LLM call failed, falling back to single task" in r.message
    ]
    assert len(warnings) == 1
    assert warnings[0].exc_info is not None


def test_decompose_task_safe_worker_type():
    from devagent.agent.coordinator import decompose_task
    llm = _make_llm_mock(
        tool_call_name="submit_task_graph",
        tool_call_args={
            "tasks": [
                {"id": "t1", "description": "do X", "worker_type": "invalid_type", "depends_on": []},
            ]
        },
    )
    result = decompose_task(llm, "task", "/project")
    assert result.nodes[0].worker_type == "implementer"  # safe fallback


def test_synthesise_results_calls_llm(tmp_path):
    from devagent.agent.coordinator import synthesise_results
    from devagent.agent.task_graph import TaskGraph, TaskNode
    from devagent.session import store

    db = tmp_path / "t.db"
    store.init_schema(db_path=db)
    store.create_session("synth-sess", db_path=db)

    graph = TaskGraph("synth-sess", db_path=db)
    n = TaskNode.make("impl thing")
    graph.add(n)
    graph.mark_done(n.id, result="implemented auth.py")

    llm = _make_llm_mock(content="## Summary\n- Implemented auth.py")
    summary = synthesise_results(llm, "add auth", graph)
    assert len(summary) > 0


def test_synthesise_results_fallback_on_llm_error_logs_warning(caplog, tmp_path):
    import logging

    from devagent.agent.coordinator import synthesise_results
    from devagent.agent.task_graph import TaskGraph, TaskNode
    from devagent.session import store

    db = tmp_path / "t.db"
    store.init_schema(db_path=db)
    store.create_session("synth-sess-err", db_path=db)

    graph = TaskGraph("synth-sess-err", db_path=db)
    n = TaskNode.make("impl thing")
    graph.add(n)

    mock = MagicMock()
    mock.complete_with_tools.side_effect = RuntimeError("synthesis error")
    with caplog.at_level(logging.WARNING, logger="devagent.agent.coordinator"):
        summary = synthesise_results(mock, "task", graph)

    assert len(summary) > 0
    warnings = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING
        and "synthesise_results: LLM call failed, returning graph summary" in r.message
    ]
    assert len(warnings) == 1
    assert warnings[0].exc_info is not None


# ---------------------------------------------------------------------------
# 4. Worker types and tool sets
# ---------------------------------------------------------------------------

def test_worker_tool_sets_defined():
    from devagent.agent.worker import WORKER_TOOL_SETS
    assert "implementer" in WORKER_TOOL_SETS
    assert "tester" in WORKER_TOOL_SETS
    assert "reviewer" in WORKER_TOOL_SETS


def test_implementer_has_all_tools():
    from devagent.agent.worker import WORKER_TOOL_SETS
    assert WORKER_TOOL_SETS["implementer"] == []  # empty = all tools


def test_reviewer_has_no_write_tools():
    from devagent.agent.worker import WORKER_TOOL_SETS
    reviewer_tools = WORKER_TOOL_SETS["reviewer"]
    assert "write_file" not in reviewer_tools
    assert "edit_file" not in reviewer_tools
    assert "read_file" in reviewer_tools


# ---------------------------------------------------------------------------
# 5. System prompt — worker prompts
# ---------------------------------------------------------------------------

def test_build_worker_system_prompt_implementer():
    from devagent.agent.system_prompt import build_worker_system_prompt
    prompt = build_worker_system_prompt("implementer", "/project")
    assert "Implementer" in prompt
    assert "/project" in prompt


def test_build_worker_system_prompt_tester():
    from devagent.agent.system_prompt import build_worker_system_prompt
    prompt = build_worker_system_prompt("tester")
    assert "Tester" in prompt
    assert "NOT modify production" in prompt


def test_build_worker_system_prompt_reviewer():
    from devagent.agent.system_prompt import build_worker_system_prompt
    prompt = build_worker_system_prompt("reviewer")
    assert "Reviewer" in prompt
    assert "NOT write" in prompt or "do NOT write" in prompt.lower() or "Read-only" in prompt


def test_build_worker_system_prompt_unknown_type():
    from devagent.agent.system_prompt import build_worker_system_prompt
    prompt = build_worker_system_prompt("unknown_type")
    assert len(prompt) > 0  # still returns something


# ---------------------------------------------------------------------------
# 6. Orchestrator — OrchestratorSession importable + basic structure
# ---------------------------------------------------------------------------

def test_orchestrator_session_importable():
    from devagent.agent.orchestrator import OrchestratorSession
    assert OrchestratorSession is not None


def test_orchestrator_run_yields_events(tmp_path):
    """Smoke-test: OrchestratorSession.run() yields events without hitting real LLM."""
    from devagent.agent.coordinator import DecomposedTask
    from devagent.agent.orchestrator import OrchestratorSession
    from devagent.agent.task_graph import TaskNode
    from devagent.agent.worker import WorkerResult

    cfg = _make_cfg()

    session = OrchestratorSession(cfg, tmp_path, max_workers=1)

    single_node = TaskNode.make("write hello.py", "implementer")
    decomposed = DecomposedTask(original_task="write hello.py", nodes=[single_node])

    worker_result = WorkerResult(
        task_id=single_node.id,
        worker_type="implementer",
        success=True,
        output="Wrote hello.py with a greeting.",
        output_files=["hello.py"],
    )

    with (
        patch("devagent.agent.orchestrator.decompose_task", return_value=decomposed),
        patch("devagent.agent.orchestrator.synthesise_results", return_value="All done."),
        patch.object(OrchestratorSession, "_run_wave", return_value=[worker_result]),
    ):
        events = list(session.run("write hello.py"))

    event_types = [type(e).__name__ for e in events]
    assert "ThinkingEvent" in event_types
    assert "FinalAnswerEvent" in event_types


# ---------------------------------------------------------------------------
# 6b. Orchestrator — worker limits come from config (agent.max_iterations /
#     agent.max_repair_iterations), with explicit overrides still honoured
# ---------------------------------------------------------------------------

def test_orchestrator_worker_limits_default_to_config(tmp_path):
    from devagent.agent.orchestrator import OrchestratorSession

    cfg = _make_cfg()
    cfg.agent.max_iterations = 42
    cfg.agent.max_repair_iterations = 7

    session = OrchestratorSession(cfg, tmp_path, max_workers=1)
    assert session._worker_max_iters == 42
    assert session._worker_max_repair == 7


def test_orchestrator_worker_limits_accept_explicit_overrides(tmp_path):
    from devagent.agent.orchestrator import OrchestratorSession

    cfg = _make_cfg()  # config defaults are 50 / 3
    session = OrchestratorSession(
        cfg, tmp_path, max_workers=1,
        worker_max_iterations=9, worker_max_repair=1,
    )
    assert session._worker_max_iters == 9
    assert session._worker_max_repair == 1


def test_orchestrator_threads_limits_into_workers(tmp_path):
    from devagent.agent.orchestrator import OrchestratorSession
    from devagent.agent.task_graph import TaskGraph, TaskNode
    from devagent.agent.worker import WorkerResult
    from devagent.session import store

    db = tmp_path / "orch.db"
    store.init_schema(db_path=db)
    store.create_session("orch-thread", db_path=db)

    cfg = _make_cfg()
    cfg.agent.max_iterations = 50
    cfg.agent.max_repair_iterations = 3
    session = OrchestratorSession(cfg, tmp_path, max_workers=1)

    graph = TaskGraph("orch-thread", db_path=db)
    node = TaskNode.make("do it", "implementer")
    graph.add(node)

    captured: dict = {}

    class _FakeWorker:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run(self):
            return WorkerResult(
                task_id=node.id, worker_type="implementer",
                success=True, output="ok",
            )

    with patch("devagent.agent.orchestrator.Worker", _FakeWorker):
        results = session._run_wave([node], graph)

    assert captured["max_iterations"] == 50
    assert captured["max_repair"] == 3
    assert results and results[0].success


def test_worker_max_repair_defaults_to_cfg_and_accepts_override():
    from devagent.agent.task_graph import TaskNode
    from devagent.agent.worker import Worker

    cfg = _make_cfg()
    cfg.agent.max_repair_iterations = 4
    node = TaskNode.make("x")

    default = Worker(task=node, cfg=cfg, project_root=".", coordinator_session_id="s")
    assert default._max_repair is None          # resolved from cfg when the loop is built

    explicit = Worker(
        task=node, cfg=cfg, project_root=".", coordinator_session_id="s", max_repair=2,
    )
    assert explicit._max_repair == 2


# ---------------------------------------------------------------------------
# 7. CLI command
# ---------------------------------------------------------------------------

def test_orchestrate_command_exists():
    import inspect

    from devagent.cli import orchestrate
    sig = inspect.signature(orchestrate)
    assert "task" in sig.parameters
    assert "workers" in sig.parameters
    assert "plan" in sig.parameters
