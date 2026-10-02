"""Concurrency tests for ProjectMemory (issue #71).

`ProjectMemory.upsert()` / `delete()` are read-modify-write cycles over one
shared file. `/batch` gives each worker its own session and its own
`ProjectMemory` instance, but with no `agent_name` they all point at the same
`.devagent/memory.md`, so two workers could each write a snapshot that predates
the other's key — a silently dropped fact.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from devagent.session.project_memory import ProjectMemory


def _widen_window(pm: ProjectMemory) -> None:
    """Make the read-modify-write window deterministic instead of racy.

    `upsert()` reads, then writes. Sleeping inside `save()` after the read has
    happened means every thread has already loaded its snapshot before any of
    them writes, so an unserialised upsert loses updates on every run rather
    than only when the scheduler happens to interleave. This stands in for a
    slow disk; it does not change what is being tested.
    """
    real_save = pm.save

    def slow_save(facts: dict) -> None:
        time.sleep(0.02)
        real_save(facts)

    pm.save = slow_save  # type: ignore[method-assign]


def test_concurrent_upserts_do_not_lose_facts(tmp_path: Path) -> None:
    """Every key written by every worker must survive (issue #71)."""
    pm = ProjectMemory(tmp_path)
    _widen_window(pm)

    keys = [f"fact_{i}" for i in range(6)]

    with ThreadPoolExecutor(max_workers=len(keys)) as pool:
        list(pool.map(lambda k: pm.upsert(k, f"value_{k}"), keys))

    stored = pm.load()
    missing = [k for k in keys if k not in stored]
    assert missing == [], f"lost updates: {missing} (stored={sorted(stored)})"


def test_sequential_upsert_baseline(tmp_path: Path) -> None:
    """The same operations, serialised, are the control for the test above."""
    pm = ProjectMemory(tmp_path)
    _widen_window(pm)

    keys = [f"fact_{i}" for i in range(6)]
    for k in keys:
        pm.upsert(k, f"value_{k}")

    assert set(pm.load()) == set(keys)


def test_concurrent_upsert_keeps_pre_existing_facts(tmp_path: Path) -> None:
    """A fact already on disk is not dropped by concurrent writers."""
    pm = ProjectMemory(tmp_path)
    pm.upsert("existing", "keep-me")
    _widen_window(pm)

    keys = [f"new_{i}" for i in range(5)]
    with ThreadPoolExecutor(max_workers=len(keys)) as pool:
        list(pool.map(lambda k: pm.upsert(k, "v"), keys))

    stored = pm.load()
    assert stored.get("existing") == "keep-me"
    assert all(k in stored for k in keys)


def test_concurrent_upsert_and_delete_do_not_interleave(tmp_path: Path) -> None:
    """`delete()` is in the same critical section as `upsert()`."""
    pm = ProjectMemory(tmp_path)
    for k in ("a", "b", "c"):
        pm.upsert(k, "v")
    _widen_window(pm)

    barrier = threading.Barrier(3)

    def worker(fn) -> None:
        barrier.wait()
        fn()

    threads = [
        threading.Thread(target=worker, args=(lambda: pm.upsert("d", "v"),)),
        threading.Thread(target=worker, args=(lambda: pm.delete("a"),)),
        threading.Thread(target=worker, args=(lambda: pm.upsert("e", "v"),)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    stored = pm.load()
    assert "a" not in stored
    assert {"b", "c", "d", "e"} <= set(stored)


def test_lock_is_shared_per_file_not_per_instance(tmp_path: Path) -> None:
    """Two instances on the same file share one lock; different files do not."""
    a1 = ProjectMemory(tmp_path)
    a2 = ProjectMemory(tmp_path / ".")  # same file, different spelling
    other = ProjectMemory.for_agent(tmp_path, "agent-x")

    assert ProjectMemory._lock_for(a1.path) is ProjectMemory._lock_for(a2.path)
    assert ProjectMemory._lock_for(a1.path) is not ProjectMemory._lock_for(other.path)
