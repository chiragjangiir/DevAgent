# Pending Infrastructure

## ✅ --output-format json / stream-json — SHIPPED (Phase 34)
`devagent do --output-format json` — collect all events, emit a single JSON object at exit.
`devagent do --output-format stream-json` — one JSON line per event (NDJSON).
Both implemented in `devagent/output/streaming.py` (`emit_json`, `stream_json_events`).

## ✅ OAuth 2.0 MCP auth — SHIPPED Phase 40
`devagent/mcp/auth/pkce.py` — `pkce_authorize()` full PKCE flow (verifier, challenge, local
redirect server, browser launch, code exchange). `refresh_token_flow()` for token refresh.
`devagent/mcp/auth/token_cache.py` — keyring save/get/clear with 60s expiry buffer.
`OAuthConfig` dataclass + `MCPServerEntry.auth` field in `project_config.py`.
23 tests in `tests/test_phase40.py`.

## ✅ .mcp.json project file — SHIPPED (Phase 35)
`devagent/mcp/project_config.py` — `load_mcp_json()`, `find_mcp_json()`, `save_mcp_json()`.
Searches `.mcp.json` then `.devagent/mcp.json`. Schema: `{"mcpServers": {"name": {...}}}`.
CLI: `devagent mcp ls` / `devagent mcp add` / `devagent mcp remove`.
20 tests in `tests/test_mcp_project_config.py`.

## ✅ WebSocket + SSE MCP transport — SHIPPED Phase 39
`devagent/mcp/transports/websocket.py` — `connect_websocket()` via `mcp.client.websocket`.
`devagent/mcp/transports/sse.py` — `connect_sse()` via `mcp.client.sse` (supports headers).
`devagent/mcp/transports/__init__.py` — `connect_entry()` dispatcher on `transport` field.
`MCPServerEntry` gains `transport`, `url`, `headers` fields; parser accepts URL-only entries.
`MCPManager._connect_remote_servers()` connects non-stdio servers from `.mcp.json` on startup.
20 tests in `tests/test_phase39.py`.
