"""Tests for Phase 35 — .mcp.json project MCP server config."""

from __future__ import annotations

import json
import pathlib

from devagent.mcp.project_config import (
    MCPServerEntry,
    find_mcp_json,
    load_mcp_json,
    save_mcp_json,
)

# ---------------------------------------------------------------------------
# load_mcp_json
# ---------------------------------------------------------------------------

class TestLoadMcpJson:
    def test_returns_empty_when_no_file(self, tmp_path: pathlib.Path) -> None:
        assert load_mcp_json(tmp_path) == []

    def test_loads_basic_server(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / ".mcp.json").write_text(json.dumps({
            "mcpServers": {
                "my-tool": {"command": "python", "args": ["-m", "my_tool"]}
            }
        }))
        entries = load_mcp_json(tmp_path)
        assert len(entries) == 1
        assert entries[0].name == "my-tool"
        assert entries[0].command == "python"
        assert entries[0].args == ["-m", "my_tool"]

    def test_loads_multiple_servers(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / ".mcp.json").write_text(json.dumps({
            "mcpServers": {
                "server-a": {"command": "node", "args": ["a.js"]},
                "server-b": {"command": "python", "args": ["-m", "b"]},
            }
        }))
        entries = load_mcp_json(tmp_path)
        names = {e.name for e in entries}
        assert names == {"server-a", "server-b"}

    def test_loads_env_dict(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / ".mcp.json").write_text(json.dumps({
            "mcpServers": {
                "s": {"command": "python", "env": {"MY_KEY": "abc", "OTHER": "xyz"}}
            }
        }))
        entries = load_mcp_json(tmp_path)
        assert entries[0].env == {"MY_KEY": "abc", "OTHER": "xyz"}

    def test_skips_entries_without_command(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / ".mcp.json").write_text(json.dumps({
            "mcpServers": {
                "good": {"command": "python"},
                "bad": {"args": ["-m", "something"]},  # no command
            }
        }))
        entries = load_mcp_json(tmp_path)
        assert len(entries) == 1
        assert entries[0].name == "good"

    def test_returns_empty_on_malformed_json(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / ".mcp.json").write_text("{invalid json}")
        assert load_mcp_json(tmp_path) == []

    def test_returns_empty_on_empty_servers(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / ".mcp.json").write_text(json.dumps({"mcpServers": {}}))
        assert load_mcp_json(tmp_path) == []

    def test_falls_back_to_devagent_mcp_json(self, tmp_path: pathlib.Path) -> None:
        devagent_dir = tmp_path / ".devagent"
        devagent_dir.mkdir()
        (devagent_dir / "mcp.json").write_text(json.dumps({
            "mcpServers": {"fallback": {"command": "echo"}}
        }))
        entries = load_mcp_json(tmp_path)
        assert len(entries) == 1
        assert entries[0].name == "fallback"

    def test_primary_mcp_json_takes_precedence(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / ".mcp.json").write_text(json.dumps({
            "mcpServers": {"primary": {"command": "python"}}
        }))
        devagent_dir = tmp_path / ".devagent"
        devagent_dir.mkdir()
        (devagent_dir / "mcp.json").write_text(json.dumps({
            "mcpServers": {"secondary": {"command": "node"}}
        }))
        entries = load_mcp_json(tmp_path)
        names = {e.name for e in entries}
        assert "primary" in names
        assert "secondary" not in names


# ---------------------------------------------------------------------------
# find_mcp_json
# ---------------------------------------------------------------------------

class TestFindMcpJson:
    def test_returns_none_when_absent(self, tmp_path: pathlib.Path) -> None:
        assert find_mcp_json(tmp_path) is None

    def test_returns_path_when_present(self, tmp_path: pathlib.Path) -> None:
        p = tmp_path / ".mcp.json"
        p.write_text("{}")
        assert find_mcp_json(tmp_path) == p


# ---------------------------------------------------------------------------
# save_mcp_json
# ---------------------------------------------------------------------------

class TestSaveMcpJson:
    def test_creates_file_with_server(self, tmp_path: pathlib.Path) -> None:
        entry = MCPServerEntry(name="my-server", command="python", args=["-m", "srv"])
        path = save_mcp_json(tmp_path, [entry])
        assert path.exists()
        data = json.loads(path.read_text())
        assert "my-server" in data["mcpServers"]
        assert data["mcpServers"]["my-server"]["command"] == "python"

    def test_preserves_existing_servers(self, tmp_path: pathlib.Path) -> None:
        existing = {"mcpServers": {"old": {"command": "node"}}}
        (tmp_path / ".mcp.json").write_text(json.dumps(existing))
        entry = MCPServerEntry(name="new", command="python")
        save_mcp_json(tmp_path, [entry])
        data = json.loads((tmp_path / ".mcp.json").read_text())
        assert "old" in data["mcpServers"]
        assert "new" in data["mcpServers"]

    def test_overwrites_existing_entry(self, tmp_path: pathlib.Path) -> None:
        existing = {"mcpServers": {"s": {"command": "node", "args": ["old.js"]}}}
        (tmp_path / ".mcp.json").write_text(json.dumps(existing))
        entry = MCPServerEntry(name="s", command="python", args=["-m", "new"])
        save_mcp_json(tmp_path, [entry])
        data = json.loads((tmp_path / ".mcp.json").read_text())
        assert data["mcpServers"]["s"]["command"] == "python"

    def test_env_saved_when_present(self, tmp_path: pathlib.Path) -> None:
        entry = MCPServerEntry(name="s", command="python", env={"KEY": "val"})
        save_mcp_json(tmp_path, [entry])
        data = json.loads((tmp_path / ".mcp.json").read_text())
        assert data["mcpServers"]["s"]["env"] == {"KEY": "val"}

    def test_env_omitted_when_empty(self, tmp_path: pathlib.Path) -> None:
        entry = MCPServerEntry(name="s", command="python")
        save_mcp_json(tmp_path, [entry])
        data = json.loads((tmp_path / ".mcp.json").read_text())
        assert "env" not in data["mcpServers"]["s"]

    def test_args_omitted_when_empty(self, tmp_path: pathlib.Path) -> None:
        entry = MCPServerEntry(name="s", command="python")
        save_mcp_json(tmp_path, [entry])
        data = json.loads((tmp_path / ".mcp.json").read_text())
        assert "args" not in data["mcpServers"]["s"]


# ---------------------------------------------------------------------------
# MCPServerEntry.to_dict
# ---------------------------------------------------------------------------

class TestMCPServerEntryToDict:
    def test_to_dict_basic(self) -> None:
        e = MCPServerEntry(name="s", command="python", args=["-m", "x"])
        d = e.to_dict()
        assert d["command"] == "python"
        assert d["args"] == ["-m", "x"]
        assert "source" in d

    def test_to_dict_no_env_when_empty(self) -> None:
        e = MCPServerEntry(name="s", command="python")
        d = e.to_dict()
        assert "env" not in d

    def test_to_dict_includes_env(self) -> None:
        e = MCPServerEntry(name="s", command="python", env={"K": "v"})
        d = e.to_dict()
        assert d["env"] == {"K": "v"}
