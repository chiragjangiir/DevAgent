"""Tests for Phase 39 — WebSocket + SSE MCP transport."""

from __future__ import annotations

import json
from pathlib import Path

from devagent.mcp.project_config import MCPServerEntry, load_mcp_json, save_mcp_json

# ---------------------------------------------------------------------------
# MCPServerEntry — new fields
# ---------------------------------------------------------------------------

class TestMCPServerEntryTransportFields:
    def test_default_transport_is_stdio(self) -> None:
        entry = MCPServerEntry(name="t", command="python")
        assert entry.transport == "stdio"
        assert entry.url == ""
        assert entry.headers == {}

    def test_websocket_entry(self) -> None:
        entry = MCPServerEntry(
            name="ws-srv",
            transport="websocket",
            url="ws://localhost:8080/mcp",
        )
        assert entry.transport == "websocket"
        assert entry.url == "ws://localhost:8080/mcp"
        assert entry.command == ""

    def test_sse_entry_with_headers(self) -> None:
        entry = MCPServerEntry(
            name="sse-srv",
            transport="sse",
            url="http://localhost:9090/sse",
            headers={"Authorization": "Bearer tok"},
        )
        assert entry.transport == "sse"
        assert entry.headers["Authorization"] == "Bearer tok"

    def test_to_dict_stdio(self) -> None:
        entry = MCPServerEntry(name="t", command="python", args=["-m", "mod"])
        d = entry.to_dict()
        assert d["transport"] == "stdio"
        assert d["command"] == "python"
        assert d["args"] == ["-m", "mod"]
        assert "url" not in d

    def test_to_dict_websocket(self) -> None:
        entry = MCPServerEntry(
            name="ws", transport="websocket", url="ws://example.com/mcp"
        )
        d = entry.to_dict()
        assert d["transport"] == "websocket"
        assert d["url"] == "ws://example.com/mcp"
        assert "command" not in d

    def test_to_dict_sse_with_headers(self) -> None:
        entry = MCPServerEntry(
            name="sse",
            transport="sse",
            url="http://example.com/sse",
            headers={"X-Token": "abc"},
        )
        d = entry.to_dict()
        assert d["headers"] == {"X-Token": "abc"}

    def test_to_dict_sse_no_headers_omitted(self) -> None:
        entry = MCPServerEntry(name="sse", transport="sse", url="http://x.com/sse")
        d = entry.to_dict()
        assert "headers" not in d


# ---------------------------------------------------------------------------
# load_mcp_json — parsing websocket / sse entries
# ---------------------------------------------------------------------------

class TestLoadMcpJsonTransports:
    def _write(self, tmp_path: Path, data: dict) -> None:
        (tmp_path / ".mcp.json").write_text(json.dumps(data), encoding="utf-8")

    def test_parses_websocket_entry(self, tmp_path) -> None:
        self._write(tmp_path, {"mcpServers": {
            "ws-server": {"transport": "websocket", "url": "ws://localhost:8080/mcp"}
        }})
        entries = load_mcp_json(tmp_path)
        assert len(entries) == 1
        e = entries[0]
        assert e.name == "ws-server"
        assert e.transport == "websocket"
        assert e.url == "ws://localhost:8080/mcp"
        assert e.command == ""

    def test_parses_sse_entry_with_headers(self, tmp_path) -> None:
        self._write(tmp_path, {"mcpServers": {
            "sse-server": {
                "transport": "sse",
                "url": "http://localhost:9090/sse",
                "headers": {"Authorization": "Bearer tok"},
            }
        }})
        entries = load_mcp_json(tmp_path)
        assert len(entries) == 1
        assert entries[0].headers == {"Authorization": "Bearer tok"}

    def test_skips_websocket_entry_without_url(self, tmp_path) -> None:
        self._write(tmp_path, {"mcpServers": {
            "bad": {"transport": "websocket"}
        }})
        assert load_mcp_json(tmp_path) == []

    def test_skips_sse_entry_without_url(self, tmp_path) -> None:
        self._write(tmp_path, {"mcpServers": {
            "bad": {"transport": "sse"}
        }})
        assert load_mcp_json(tmp_path) == []

    def test_parses_mixed_stdio_and_websocket(self, tmp_path) -> None:
        self._write(tmp_path, {"mcpServers": {
            "local": {"command": "python", "args": ["-m", "srv"]},
            "remote": {"transport": "websocket", "url": "ws://x/mcp"},
        }})
        entries = load_mcp_json(tmp_path)
        assert len(entries) == 2
        names = {e.name for e in entries}
        assert names == {"local", "remote"}
        transports = {e.name: e.transport for e in entries}
        assert transports["local"] == "stdio"
        assert transports["remote"] == "websocket"

    def test_default_transport_is_stdio(self, tmp_path) -> None:
        self._write(tmp_path, {"mcpServers": {
            "srv": {"command": "python"}
        }})
        entries = load_mcp_json(tmp_path)
        assert entries[0].transport == "stdio"


# ---------------------------------------------------------------------------
# save_mcp_json — round-trip with websocket / sse entries
# ---------------------------------------------------------------------------

class TestSaveMcpJsonTransports:
    def test_saves_websocket_entry(self, tmp_path) -> None:
        entry = MCPServerEntry(
            name="ws",
            transport="websocket",
            url="ws://localhost:8080/mcp",
        )
        save_mcp_json(tmp_path, [entry])
        data = json.loads((tmp_path / ".mcp.json").read_text())
        srv = data["mcpServers"]["ws"]
        assert srv["transport"] == "websocket"
        assert srv["url"] == "ws://localhost:8080/mcp"
        assert "command" not in srv

    def test_saves_sse_entry_with_headers(self, tmp_path) -> None:
        entry = MCPServerEntry(
            name="sse",
            transport="sse",
            url="http://localhost:9090/sse",
            headers={"Authorization": "Bearer tok"},
        )
        save_mcp_json(tmp_path, [entry])
        data = json.loads((tmp_path / ".mcp.json").read_text())
        srv = data["mcpServers"]["sse"]
        assert srv["headers"] == {"Authorization": "Bearer tok"}

    def test_round_trip_websocket(self, tmp_path) -> None:
        original = MCPServerEntry(
            name="ws",
            transport="websocket",
            url="ws://remote.example.com/mcp",
        )
        save_mcp_json(tmp_path, [original])
        loaded = load_mcp_json(tmp_path)
        assert len(loaded) == 1
        assert loaded[0].url == "ws://remote.example.com/mcp"
        assert loaded[0].transport == "websocket"


# ---------------------------------------------------------------------------
# Transport module imports (structural tests — no live server needed)
# ---------------------------------------------------------------------------

class TestTransportImports:
    def test_websocket_transport_importable(self) -> None:
        from devagent.mcp.transports.websocket import connect_websocket  # noqa: F401

    def test_sse_transport_importable(self) -> None:
        from devagent.mcp.transports.sse import connect_sse  # noqa: F401

    def test_connect_entry_importable(self) -> None:
        from devagent.mcp.transports import connect_entry  # noqa: F401

    def test_connect_entry_raises_on_unknown_transport(self) -> None:
        import asyncio

        from devagent.mcp.transports import connect_entry

        entry = MCPServerEntry(name="x", transport="grpc", url="grpc://localhost")

        async def _run() -> None:
            async with connect_entry(entry):
                pass

        try:
            asyncio.run(_run())
            assert False, "should have raised"
        except ValueError as exc:
            assert "grpc" in str(exc)
