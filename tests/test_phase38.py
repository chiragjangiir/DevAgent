"""Tests for Phase 38 — /background command (detached subprocess)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# devagent.background.jobs module tests
# ---------------------------------------------------------------------------

class TestStateDir:
    def test_creates_devagent_dir(self, tmp_path) -> None:
        from devagent.background.jobs import _state_dir
        d = _state_dir(tmp_path)
        assert d.exists()
        assert d.name == ".devagent"

    def test_idempotent(self, tmp_path) -> None:
        from devagent.background.jobs import _state_dir
        _state_dir(tmp_path)
        _state_dir(tmp_path)  # no error on second call
        assert (tmp_path / ".devagent").is_dir()


class TestIsRunning:
    def test_current_process_is_running(self) -> None:
        from devagent.background.jobs import _is_running
        assert _is_running(os.getpid()) is True

    def test_nonexistent_pid_not_running(self) -> None:
        from devagent.background.jobs import _is_running
        # PID 999999 is almost certainly dead or non-existent
        assert _is_running(999999) is False


class TestBackgroundJob:
    def test_dataclass_fields(self) -> None:
        from devagent.background.jobs import BackgroundJob
        job = BackgroundJob(
            id="abc12345",
            task="do something",
            pid=1234,
            log_path="/tmp/bg_abc12345.log",
            state_path="/tmp/bg_abc12345.json",
            started_at=1234567890.0,
            status="running",
        )
        assert job.id == "abc12345"
        assert job.status == "running"

    def test_default_status_is_running(self) -> None:
        from devagent.background.jobs import BackgroundJob
        job = BackgroundJob(
            id="x",
            task="t",
            pid=1,
            log_path="",
            state_path="",
            started_at=0.0,
        )
        assert job.status == "running"


class TestSaveLoad:
    def test_round_trip(self, tmp_path) -> None:
        from devagent.background.jobs import BackgroundJob, _load, _save
        state_path = str(tmp_path / "bg_test.json")
        job = BackgroundJob(
            id="test1",
            task="write tests",
            pid=os.getpid(),
            log_path=str(tmp_path / "bg_test.log"),
            state_path=state_path,
            started_at=time.time(),
            status="running",
        )
        _save(job)
        loaded = _load(state_path)
        assert loaded.id == "test1"
        assert loaded.task == "write tests"
        assert loaded.status == "running"

    def test_save_writes_json(self, tmp_path) -> None:
        from devagent.background.jobs import BackgroundJob, _save
        state_path = str(tmp_path / "bg_x.json")
        job = BackgroundJob(
            id="x",
            task="t",
            pid=1,
            log_path="",
            state_path=state_path,
            started_at=0.0,
            status="running",
        )
        _save(job)
        data = json.loads(Path(state_path).read_text())
        assert data["id"] == "x"
        assert data["status"] == "running"


class TestPoll:
    def test_running_pid_stays_running(self, tmp_path) -> None:
        from devagent.background.jobs import BackgroundJob, _save, poll
        state_path = str(tmp_path / "bg_poll.json")
        log_path = str(tmp_path / "bg_poll.log")
        job = BackgroundJob(
            id="poll1",
            task="t",
            pid=os.getpid(),   # current process — definitely alive
            log_path=log_path,
            state_path=state_path,
            started_at=time.time(),
            status="running",
        )
        _save(job)
        updated = poll(job)
        assert updated.status == "running"

    def test_dead_pid_marked_done(self, tmp_path) -> None:
        from devagent.background.jobs import BackgroundJob, _save, poll
        state_path = str(tmp_path / "bg_dead.json")
        log_path = str(tmp_path / "bg_dead.log")
        job = BackgroundJob(
            id="dead1",
            task="t",
            pid=999999,   # almost certainly not running
            log_path=log_path,
            state_path=state_path,
            started_at=time.time(),
            status="running",
        )
        _save(job)
        updated = poll(job)
        assert updated.status == "done"

    def test_already_done_not_rechecked(self, tmp_path) -> None:
        from devagent.background.jobs import BackgroundJob, _save, poll
        state_path = str(tmp_path / "bg_done.json")
        job = BackgroundJob(
            id="d1",
            task="t",
            pid=999999,
            log_path="",
            state_path=state_path,
            started_at=0.0,
            status="done",
        )
        _save(job)
        updated = poll(job)
        assert updated.status == "done"


class TestListJobs:
    def test_empty_project_returns_empty(self, tmp_path) -> None:
        from devagent.background.jobs import list_jobs
        assert list_jobs(tmp_path) == []

    def test_returns_saved_jobs(self, tmp_path) -> None:
        from devagent.background.jobs import BackgroundJob, _save, _state_dir, list_jobs
        state_d = _state_dir(tmp_path)
        for i in range(3):
            state_path = str(state_d / f"bg_job{i}.json")
            _save(BackgroundJob(
                id=f"job{i}",
                task=f"task {i}",
                pid=999999,
                log_path="",
                state_path=state_path,
                started_at=float(i),
                status="running",
            ))
        jobs = list_jobs(tmp_path)
        assert len(jobs) == 3


class TestLaunch:
    def test_creates_log_and_state_files(self, tmp_path) -> None:
        from devagent.background.jobs import launch
        job = launch("echo hello", tmp_path)
        assert Path(job.log_path).exists()
        assert Path(job.state_path).exists()

    def test_returns_job_with_pid(self, tmp_path) -> None:
        from devagent.background.jobs import launch
        job = launch("echo hello", tmp_path)
        assert job.pid > 0
        assert job.status == "running"
        assert len(job.id) == 8

    def test_job_id_unique(self, tmp_path) -> None:
        from devagent.background.jobs import launch
        j1 = launch("echo a", tmp_path)
        j2 = launch("echo b", tmp_path)
        assert j1.id != j2.id
