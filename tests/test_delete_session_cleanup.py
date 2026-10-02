"""`delete_session()` must purge every table that carries a `session_id` (issue #64).

`task_graph` and `file_locks` were left behind: they have no `ON DELETE CASCADE`
and SQLite does not enforce foreign keys unless `PRAGMA foreign_keys=ON` is set
(which `store._conn` does not do), so those rows outlived the session that owned
them with no reader able to reach them.

The two tables are asserted in separate tests on purpose: one shared test would
stop at whichever assertion failed first and could call a half-fix green.
"""

from __future__ import annotations


def _seed(db, session_id: str) -> None:
    """Create a session with at least one row in every child table."""
    from devagent.session import store

    store.create_session(session_id, db_path=db)
    store.append_event(session_id, "user", content="hello", db_path=db)
    store.upsert_memory(session_id, "k", "v", db_path=db)
    store.upsert_task(session_id, "t1", "do a thing", db_path=db)
    assert store.acquire_file_lock(session_id, "src/a.py", "worker-1", db_path=db)


def test_delete_session_purges_task_graph(tmp_path) -> None:
    from devagent.session import store

    db = tmp_path / "sessions.db"
    store.init_schema(db_path=db)
    _seed(db, "s1")
    assert len(store.get_tasks("s1", db_path=db)) == 1

    store.delete_session("s1", db_path=db)

    assert store.get_tasks("s1", db_path=db) == []


def test_delete_session_purges_file_locks(tmp_path) -> None:
    from devagent.session import store

    db = tmp_path / "sessions.db"
    store.init_schema(db_path=db)
    _seed(db, "s1")
    assert len(store.get_file_locks("s1", db_path=db)) == 1

    store.delete_session("s1", db_path=db)

    assert store.get_file_locks("s1", db_path=db) == []


def test_delete_session_purges_session_events_and_memory(tmp_path) -> None:
    """The three tables the original code already handled keep working."""
    from devagent.session import store

    db = tmp_path / "sessions.db"
    store.init_schema(db_path=db)
    _seed(db, "s1")

    store.delete_session("s1", db_path=db)

    assert store.get_session("s1", db_path=db) is None
    assert store.get_events("s1", db_path=db) == []
    assert store.get_memory("s1", db_path=db) == {}


def test_delete_session_leaves_other_sessions_untouched(tmp_path) -> None:
    """The cleanup is scoped to the deleted id, not a table-wide truncation."""
    from devagent.session import store

    db = tmp_path / "sessions.db"
    store.init_schema(db_path=db)
    _seed(db, "s1")
    _seed(db, "s2")

    store.delete_session("s1", db_path=db)

    assert store.get_session("s2", db_path=db) is not None
    assert len(store.get_events("s2", db_path=db)) == 1
    assert store.get_memory("s2", db_path=db) == {"k": "v"}
    assert len(store.get_tasks("s2", db_path=db)) == 1
    assert len(store.get_file_locks("s2", db_path=db)) == 1


def test_delete_session_is_idempotent(tmp_path) -> None:
    """Deleting an id that was never created (or already deleted) is a no-op."""
    from devagent.session import store

    db = tmp_path / "sessions.db"
    store.init_schema(db_path=db)
    store.delete_session("never-existed", db_path=db)
    store.delete_session("never-existed", db_path=db)
