# Pending Infrastructure

## --output-format json / stream-json
CLI flag for `devagent run` / `devagent do` to emit machine-readable output for CI pipelines.
Plan:
- `--output-format json` — collect all events, emit a single JSON object at exit
- `--output-format stream-json` — emit one JSON line per event (NDJSON)
- Add `JsonEventRenderer` and `StreamJsonEventRenderer` alongside the existing Rich renderer

## OAuth 2.0 MCP auth
MCP servers that require OAuth (e.g. cloud APIs) currently need manual token injection.
Plan:
- Read MCP server auth config from `.mcp.json`
- Implement PKCE flow: open browser, capture redirect, exchange code for token
- Cache token in platform keyring; refresh on expiry

## .mcp.json project file
Standard MCP project config file (analogous to Claude Code's `.mcp.json`).
Plan:
- `load_mcp_json(project_root)` — parse `.mcp.json` or `.devagent/mcp.json`
- Merge with global MCP config from `~/.config/devagent/mcp.json`
- Auto-start declared servers on `devagent run`

## WebSocket MCP transport
Currently only stdio transport is supported.
Plan:
- Implement `WebSocketTransport` in `devagent/mcp/`
- Declare transport type in `.mcp.json` server entries
- Re-use existing message framing; swap stdio streams for WebSocket send/recv
