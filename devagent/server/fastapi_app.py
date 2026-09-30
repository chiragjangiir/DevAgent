"""DevAgent REST + WebSocket server — FastAPI.

REST endpoints (v1):
  GET    /api/v1/status                    server health + uptime + stats
  GET    /api/v1/sessions                  list sessions (filter, paginate)
  GET    /api/v1/sessions/{id}             session detail + token totals
  DELETE /api/v1/sessions/{id}             delete a session
  GET    /api/v1/sessions/{id}/events      event log (paginated, incremental)
  GET    /api/v1/sessions/{id}/memory      structured memory facts
  POST   /api/v1/sessions/{id}/approve     approve/deny a pending tool call (Phase 10)
  GET    /api/v1/orchestrate/{id}/graph    task DAG for orchestrate sessions
  GET    /api/v1/orchestrate/{id}/locks    active file locks
  GET    /api/v1/metrics                   aggregated token/cost/session metrics

Legacy endpoints (kept for backward compat with older clients):
  GET  /api/health
  GET  /api/status
  GET  /api/sessions
  GET  /api/sessions/{id}
  GET  /api/tools
  GET  /api/graph/stats
  GET  /api/graph/files

WebSocket:
  WS   /ws/v1/{session_id}                live event stream (DB polling, 500ms)

Docs:
  GET  /api/docs                           Swagger UI
  GET  /api/redoc                          ReDoc
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from devagent.server.ws_manager import manager as ws_manager
from devagent.session import store as session_store

_VERSION = "0.5.0"

# ---------------------------------------------------------------------------
# Module-level state — updated by create_app() before each server start
# ---------------------------------------------------------------------------

_state: dict[str, Any] = {
    "config": None,
    "project_root": Path("."),
    "start_time": time.time(),
    "host": "127.0.0.1",
    "port": 7331,
}

# ---------------------------------------------------------------------------
# Approximate cost lookup: (input_usd_per_1M_tokens, output_usd_per_1M_tokens)
# ---------------------------------------------------------------------------

_COST_TABLE: dict[str, tuple[float, float]] = {
    # Ollama (local) — free
    "qwen2.5-coder:7b": (0.0, 0.0),
    "qwen2.5-coder:32b": (0.0, 0.0),
    "qwen2.5:72b": (0.0, 0.0),
    "llama3.3:70b": (0.0, 0.0),
    "codellama:34b": (0.0, 0.0),
    "deepseek-coder": (0.0, 0.0),
    # Anthropic
    "claude-3-5-sonnet": (3.0, 15.0),
    "claude-3-5-haiku": (0.8, 4.0),
    "claude-3-opus": (15.0, 75.0),
    "claude-sonnet-4": (3.0, 15.0),
    "claude-haiku-4": (0.8, 4.0),
    "claude-opus-4": (15.0, 75.0),
    # OpenAI
    "gpt-4o": (5.0, 15.0),
    "gpt-4o-mini": (0.15, 0.6),
    "o1-preview": (15.0, 60.0),
    "o3-mini": (1.1, 4.4),
    # Google
    "gemini-1.5-pro": (1.25, 5.0),
    "gemini-1.5-flash": (0.075, 0.3),
    "gemini-2.0-flash": (0.1, 0.4),
    # Groq (inference cost — hardware rented, not per token)
    "mixtral-8x7b": (0.27, 0.27),
    "llama-3.1-70b": (0.59, 0.79),
}


def _estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    m = (model or "").lower()
    for key, (in_rate, out_rate) in _COST_TABLE.items():
        if key in m:
            return (tokens_in * in_rate + tokens_out * out_rate) / 1_000_000
    return 0.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def _db():
    """Open a SQLite connection and close it on exit."""
    conn = session_store._conn()
    try:
        yield conn
    finally:
        conn.close()


def _derive_status(session: dict) -> str:
    """Infer session status from metadata (no dedicated DB column yet)."""
    meta = session.get("metadata") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}
    if "status" in meta:
        return str(meta["status"])
    age = time.time() - float(session.get("updated_at") or 0)
    return "running" if age < 120 else "completed"


def _classify_event(event: dict) -> str:
    role = event.get("role", "")
    tool_calls = event.get("tool_calls") or []
    if role == "user":
        return "user_message"
    if role == "tool":
        return "tool_result"
    if role == "assistant":
        return "tool_call" if tool_calls else "thinking"
    return "status"


def _parse_tool_calls(raw: Any) -> list:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return []
    return []


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="DevAgent API",
    version=_VERSION,
    description="DevAgent REST + WebSocket API for the agent orchestrator UI.",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def _http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Return {"error": "..."} instead of FastAPI's default {"detail": "..."}.

    This keeps the response format consistent with the legacy stdlib server
    and makes the app-side error handling simpler.
    """
    return JSONResponse({"error": str(exc.detail)}, status_code=exc.status_code)


# ---------------------------------------------------------------------------
# Graph visualisation UI — served on demand, never written to disk.
# Exists only while the server is running; disappears on Ctrl-C.
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def graph_ui() -> str:
    from devagent.server.graph_ui import build_html
    return build_html(_state["host"], _state["port"])


# ---------------------------------------------------------------------------
# v1 endpoints
# ---------------------------------------------------------------------------

@app.get("/api/v1/status")
def v1_status() -> dict:
    cfg = _state["config"]
    project_root = _state["project_root"]

    cp_indexed = False
    try:
        from devagent.codeprism.client import CodePrismClient
        cp = CodePrismClient(str(project_root))
        cp_indexed = cp.is_indexed
    except Exception:
        pass

    with _db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        active = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE updated_at > ?",
            (time.time() - 120,),
        ).fetchone()[0]

    return {
        "version": _VERSION,
        "uptime_seconds": int(time.time() - _state["start_time"]),
        "project": str(project_root),
        "active_sessions": active,
        "total_sessions": total,
        "llm": {
            "provider": cfg.llm.provider if cfg else None,
            "model": cfg.llm.model if cfg else None,
            "offline_capable": (cfg.llm.provider == "ollama") if cfg else None,
        },
        "graph": {"indexed": cp_indexed},
    }


@app.get("/api/v1/sessions")
def v1_sessions(
    status: str | None = None,
    project: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    raw = session_store.list_sessions(limit=500)
    if not raw:
        return {"sessions": [], "total": 0}

    ids = [s["id"] for s in raw]
    placeholders = ",".join("?" * len(ids))

    with _db() as conn:
        token_rows = conn.execute(
            f"SELECT session_id, SUM(tokens_in), SUM(tokens_out) "
            f"FROM events WHERE session_id IN ({placeholders}) GROUP BY session_id",
            ids,
        ).fetchall()
        orchestrate_rows = conn.execute(
            f"SELECT DISTINCT session_id FROM task_graph WHERE session_id IN ({placeholders})",
            ids,
        ).fetchall()

    token_map = {r[0]: (int(r[1] or 0), int(r[2] or 0)) for r in token_rows}
    orchestrate_ids = {r[0] for r in orchestrate_rows}

    result = []
    for s in raw:
        s = dict(s)
        t_in, t_out = token_map.get(s["id"], (0, 0))
        s["token_input"] = t_in
        s["token_output"] = t_out
        s["cost_usd"] = _estimate_cost(s.get("model", ""), t_in, t_out)
        s["status"] = _derive_status(s)
        s["is_orchestrate"] = s["id"] in orchestrate_ids
        if status and s["status"] != status:
            continue
        if project and project.lower() not in (s.get("project") or "").lower():
            continue
        result.append(s)

    return {"sessions": result[offset: offset + limit], "total": len(result)}


@app.get("/api/v1/sessions/{session_id}")
def v1_session_detail(session_id: str) -> dict:
    session = session_store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    totals = session_store.get_token_totals(session_id)
    session["token_input"] = totals["tokens_in"]
    session["token_output"] = totals["tokens_out"]
    session["cost_usd"] = _estimate_cost(
        session.get("model", ""), totals["tokens_in"], totals["tokens_out"]
    )
    session["status"] = _derive_status(session)
    with _db() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM task_graph WHERE session_id = ?", (session_id,)
        ).fetchone()[0]
    session["is_orchestrate"] = count > 0
    return session


@app.delete("/api/v1/sessions/{session_id}")
def v1_delete_session(session_id: str) -> dict:
    if session_store.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    session_store.delete_session(session_id)
    return {"ok": True}


@app.get("/api/v1/sessions/{session_id}/events")
def v1_session_events(
    session_id: str,
    from_seq: int = -1,
    limit: int = 100,
) -> dict:
    if session_store.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    with _db() as conn:
        rows = conn.execute(
            "SELECT * FROM events WHERE session_id = ? AND seq > ? ORDER BY seq ASC LIMIT ?",
            (session_id, from_seq, limit + 1),
        ).fetchall()
    events = []
    for row in list(rows)[:limit]:
        e = dict(row)
        e["tool_calls"] = _parse_tool_calls(e.get("tool_calls"))
        e["event_type"] = _classify_event(e)
        events.append(e)
    return {"events": events, "has_more": len(rows) > limit}


@app.get("/api/v1/sessions/{session_id}/memory")
def v1_session_memory(session_id: str) -> dict:
    if session_store.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    memory = session_store.get_memory(session_id)
    return {"facts": [{"key": k, "value": v} for k, v in memory.items()]}


@app.post("/api/v1/sessions/{session_id}/approve")
async def v1_approve(session_id: str, request: Request) -> dict:
    """Approve or deny a pending tool call in an active session.

    Body (JSON): {"call_id": "...", "approved": true}
    call_id is optional — if omitted, resolves the most recent pending call.
    approved defaults to true.
    """
    if session_store.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    body: dict = {}
    try:
        body = await request.json()
    except Exception:
        pass

    call_id: str = body.get("call_id", "")
    approved: bool = bool(body.get("approved", True))

    from devagent.agent import permissions as perm_registry
    mgr = perm_registry.get(session_id)
    if mgr is not None and call_id:
        mgr.resolve(call_id, approved)
        return {"ok": True, "session_id": session_id, "call_id": call_id, "approved": approved}

    return {"ok": True, "session_id": session_id, "note": "No active permission gate for this session"}


@app.get("/api/v1/orchestrate/{session_id}/graph")
def v1_orchestrate_graph(session_id: str) -> dict:
    if session_store.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    tasks = session_store.get_tasks(session_id)
    is_complete = bool(tasks) and all(t["status"] in ("done", "failed") for t in tasks)
    has_failures = any(t["status"] == "failed" for t in tasks)
    return {
        "session_id": session_id,
        "nodes": tasks,
        "is_complete": is_complete,
        "has_failures": has_failures,
    }


@app.get("/api/v1/orchestrate/{session_id}/locks")
def v1_orchestrate_locks(session_id: str) -> dict:
    if session_store.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return {"locks": session_store.get_file_locks(session_id)}


@app.get("/api/v1/metrics")
def v1_metrics(period: str = "24h") -> dict:
    windows = {"1h": 3600, "24h": 86400, "7d": 604800, "30d": 2592000}
    window = windows.get(period, 86400)
    since = time.time() - window

    with _db() as conn:
        sessions_count = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE created_at >= ?", (since,)
        ).fetchone()[0]

        active_count = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE updated_at >= ?", (time.time() - 120,)
        ).fetchone()[0]

        token_rows = conn.execute(
            """SELECT s.model, SUM(e.tokens_in), SUM(e.tokens_out)
               FROM events e JOIN sessions s ON s.id = e.session_id
               WHERE e.created_at >= ? GROUP BY s.model""",
            (since,),
        ).fetchall()

        hour_rows = conn.execute(
            """SELECT CAST((e.created_at - ?) / 3600 AS INTEGER) AS h,
                      SUM(e.tokens_in + e.tokens_out)
               FROM events e WHERE e.created_at >= ?
               GROUP BY h ORDER BY h""",
            (since, since),
        ).fetchall()

    by_model = []
    total_tokens = 0
    total_cost = 0.0
    for model, t_in, t_out in token_rows:
        t_in = int(t_in or 0)
        t_out = int(t_out or 0)
        cost = _estimate_cost(model or "", t_in, t_out)
        by_model.append({
            "model": model or "unknown",
            "tokens": t_in + t_out,
            "cost_usd": round(cost, 6),
        })
        total_tokens += t_in + t_out
        total_cost += cost

    total_hours = max(1, window // 3600)
    hour_map = {int(r[0]): int(r[1] or 0) for r in hour_rows}
    by_hour = [
        {
            "hour": time.strftime("%Y-%m-%dT%H:00:00Z", time.gmtime(since + h * 3600)),
            "tokens": hour_map.get(h, 0),
            "cost_usd": 0.0,
        }
        for h in range(total_hours)
    ]

    return {
        "period": period,
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost, 6),
        "sessions_count": sessions_count,
        "active_sessions": active_count,
        "by_model": by_model,
        "by_hour": by_hour,
    }


# ---------------------------------------------------------------------------
# WebSocket endpoint — DB polling at 500ms intervals
# ---------------------------------------------------------------------------

@app.websocket("/ws/v1/{session_id}")
async def ws_endpoint(websocket: WebSocket, session_id: str) -> None:
    """Live event stream for a session.

    Protocol:
      - Server sends events as {"type": "event", "session_id": ..., "seq": ..., "data": {...}}
      - Server sends {"type": "ping"} every 30 seconds
      - Client responds with {"type": "pong"} to keep the connection alive
      - On task graph changes the server also sends {"type": "graph_update", ...}
    """
    await ws_manager.connect(session_id, websocket)
    last_seq = -1

    async def _ping_loop() -> None:
        while True:
            await asyncio.sleep(30)
            try:
                await websocket.send_text(json.dumps({"type": "ping"}))
            except Exception:
                return

    ping_task = asyncio.create_task(_ping_loop())
    try:
        while True:
            new_events = await asyncio.to_thread(_poll_events, session_id, last_seq)
            for ev in new_events:
                last_seq = ev["seq"]
                await websocket.send_text(json.dumps(
                    {
                        "type": "event",
                        "session_id": session_id,
                        "seq": ev["seq"],
                        "event_type": _classify_event(ev),
                        "data": ev,
                    },
                    default=str,
                ))

            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=0.5)
                msg = json.loads(raw)
                if msg.get("type") == "pong":
                    pass  # heartbeat acknowledged
            except TimeoutError:
                pass
            except (WebSocketDisconnect, Exception):
                break

    except WebSocketDisconnect:
        pass
    finally:
        ping_task.cancel()
        await ws_manager.disconnect(session_id, websocket)


def _poll_events(session_id: str, after_seq: int) -> list[dict]:
    """Sync DB fetch — executed via asyncio.to_thread."""
    conn = session_store._conn()
    try:
        rows = conn.execute(
            "SELECT * FROM events WHERE session_id = ? AND seq > ? ORDER BY seq ASC LIMIT 50",
            (session_id, after_seq),
        ).fetchall()
    finally:
        conn.close()
    result = []
    for row in rows:
        e = dict(row)
        e["tool_calls"] = _parse_tool_calls(e.get("tool_calls"))
        result.append(e)
    return result


# ---------------------------------------------------------------------------
# Legacy v0 endpoints — preserved for backward compat
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": _VERSION}


@app.get("/api/status")
def legacy_status():
    cfg = _state["config"]
    if cfg is None:
        return JSONResponse({"error": "no config loaded"}, status_code=503)
    return v1_status()


@app.get("/api/sessions")
def legacy_sessions() -> dict:
    sessions = session_store.list_sessions(limit=20)
    return {"sessions": sessions}


@app.get("/api/sessions/{session_id}")
def legacy_session_detail(session_id: str) -> dict:
    return v1_session_detail(session_id)


@app.get("/api/tools")
def legacy_tools() -> dict:
    try:
        from devagent.tools.registry import build_registry
        registry = build_registry(str(_state["project_root"]))
        tools = [{"name": t.name, "description": t.description} for t in registry.get_definitions()]
        return {"tools": tools, "count": len(tools)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/graph/stats")
def legacy_graph_stats() -> dict:
    try:
        from devagent.codeprism.client import CodePrismClient
        cp = CodePrismClient(str(_state["project_root"]))
        if not cp.is_indexed:
            raise HTTPException(status_code=404, detail="Project not indexed — run: codeprism index .")
        return cp.get_stats()
    except HTTPException:
        raise
    except ImportError:
        raise HTTPException(status_code=501, detail="codeprism-ai not installed")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/graph/files")
def legacy_graph_files() -> dict:
    try:
        from devagent.codeprism.client import CodePrismClient
        cp = CodePrismClient(str(_state["project_root"]))
        if not cp.is_indexed:
            raise HTTPException(status_code=404, detail="Project not indexed — run: codeprism index .")
        return cp.get_file_map()
    except HTTPException:
        raise
    except ImportError:
        raise HTTPException(status_code=501, detail="codeprism-ai not installed")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Public API — called from cli.py
# ---------------------------------------------------------------------------

def create_app(config=None, project_root: str | Path = ".") -> FastAPI:
    """Configure and return the FastAPI application instance."""
    _state["config"] = config
    _state["project_root"] = Path(project_root).resolve()
    _state["start_time"] = time.time()
    session_store.init_schema()
    return app


def serve(
    host: str = "127.0.0.1",
    port: int = 7331,
    config=None,
    project_root: str | Path = ".",
    open_ui: bool = False,
) -> None:
    """Start the server via uvicorn. Blocks until Ctrl-C."""
    import uvicorn
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    _state["host"] = host
    _state["port"] = port
    application = create_app(config=config, project_root=project_root)

    console.print(Panel(
        f"[bold cyan]DevAgent API server[/bold cyan]\n"
        f"Listening on [link]http://{host}:{port}[/link]\n\n"
        f"[dim]v1 REST API:[/dim]\n"
        f"  [dim]GET  /api/v1/status[/dim]\n"
        f"  [dim]GET  /api/v1/sessions[/dim]\n"
        f"  [dim]GET  /api/v1/sessions/{{id}}/events[/dim]\n"
        f"  [dim]GET  /api/v1/orchestrate/{{id}}/graph[/dim]\n"
        f"  [dim]GET  /api/v1/metrics[/dim]\n"
        f"  [dim]WS   /ws/v1/{{session_id}}[/dim]\n\n"
        f"[dim]Interactive docs: http://{host}:{port}/api/docs[/dim]\n"
        f"[dim]Press Ctrl-C to stop.[/dim]",
        border_style="cyan",
    ))

    if open_ui:
        import webbrowser
        webbrowser.open(f"http://{host}:{port}/")

    uvicorn.run(application, host=host, port=port, log_level="warning")
