"""Background job management for /background REPL command.

Jobs are launched as detached subprocesses running `devagent do <task>`.
State is persisted to <project>/.devagent/bg_<id>.json so the user can
check status across terminal sessions.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class BackgroundJob:
    id: str
    task: str
    pid: int
    log_path: str
    state_path: str
    started_at: float
    status: str = "running"   # running | done | failed | unknown


def _state_dir(project_root: str | Path) -> Path:
    d = Path(project_root) / ".devagent"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _is_running(pid: int) -> bool:
    """Return True if the process with the given PID is still alive."""
    try:
        if os.name == "nt":
            import ctypes
            SYNCHRONIZE = 0x100000
            handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, pid)  # type: ignore[attr-defined]
            if handle == 0:
                return False
            result = ctypes.windll.kernel32.WaitForSingleObject(handle, 0)  # type: ignore[attr-defined]
            ctypes.windll.kernel32.CloseHandle(handle)  # type: ignore[attr-defined]
            return result != 0   # 0 = WAIT_OBJECT_0 (exited), non-zero = still running
        else:
            os.kill(pid, 0)
            return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


def launch(
    task: str,
    project_root: str | Path,
    python: str | None = None,
) -> BackgroundJob:
    """Launch `devagent do <task>` as a detached background process.

    Output (stdout + stderr) is redirected to a log file in
    <project>/.devagent/bg_<id>.log. A companion JSON state file
    records the PID and metadata.
    """
    job_id = uuid.uuid4().hex[:8]
    state_d = _state_dir(project_root)
    log_path = str(state_d / f"bg_{job_id}.log")
    state_path = str(state_d / f"bg_{job_id}.json")
    py = python or sys.executable

    cmd = [py, "-m", "devagent", "do", task, "--output-format", "stream-json"]

    with open(log_path, "w") as log_fh:
        if os.name == "nt":
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=log_fh,
                stderr=log_fh,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                cwd=str(project_root),
            )
        else:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=log_fh,
                stderr=log_fh,
                start_new_session=True,
                cwd=str(project_root),
            )

    job = BackgroundJob(
        id=job_id,
        task=task,
        pid=proc.pid,
        log_path=log_path,
        state_path=state_path,
        started_at=time.time(),
        status="running",
    )
    _save(job)
    return job


def _save(job: BackgroundJob) -> None:
    with open(job.state_path, "w") as f:
        json.dump(asdict(job), f, indent=2)


def _load(state_path: str | Path) -> BackgroundJob:
    with open(state_path) as f:
        data = json.load(f)
    return BackgroundJob(**data)


def poll(job: BackgroundJob) -> BackgroundJob:
    """Refresh and persist the job's status from the OS."""
    if job.status == "running":
        job.status = "running" if _is_running(job.pid) else "done"
        _save(job)
    return job


def list_jobs(project_root: str | Path) -> list[BackgroundJob]:
    """Return all background jobs for this project, newest first."""
    state_d = _state_dir(project_root)
    jobs = []
    for p in sorted(state_d.glob("bg_*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            job = _load(p)
            job = poll(job)
            jobs.append(job)
        except Exception:  # noqa: S112
            continue
    return jobs
