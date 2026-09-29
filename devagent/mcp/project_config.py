"""Phase 35 — .mcp.json project-level MCP server config.

Loads server declarations from .mcp.json (or .devagent/mcp.json) in the
project root and merges them with any globally configured servers.

Config format (same schema Claude Code uses):
  {
    "mcpServers": {
      "my-tool": {
        "command": "python",
        "args": ["-m", "my_tool.server"],
        "env": {"MY_KEY": "value"}   (optional)
      }
    }
  }
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# Candidate paths searched in order
_CANDIDATES = [".mcp.json", ".devagent/mcp.json"]


@dataclass
class MCPServerEntry:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    source: str = "project"  # "project" | "global"

    def to_dict(self) -> dict:
        d: dict = {"command": self.command, "args": self.args, "source": self.source}
        if self.env:
            d["env"] = self.env
        return d


def load_mcp_json(project_root: str | Path) -> list[MCPServerEntry]:
    """Parse .mcp.json (or .devagent/mcp.json) from the project root.

    Returns a list of MCPServerEntry objects, one per declared server.
    Returns an empty list when no config file is found or the file is malformed.
    """
    root = Path(project_root)
    for candidate in _CANDIDATES:
        path = root / candidate
        if path.exists():
            return _parse(path)
    return []


def _parse(path: Path) -> list[MCPServerEntry]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    servers = data.get("mcpServers") or {}
    entries: list[MCPServerEntry] = []
    for name, cfg in servers.items():
        if not isinstance(cfg, dict):
            continue
        command = cfg.get("command", "")
        if not command:
            continue
        entries.append(MCPServerEntry(
            name=str(name),
            command=str(command),
            args=[str(a) for a in cfg.get("args", [])],
            env={str(k): str(v) for k, v in (cfg.get("env") or {}).items()},
            source=str(path.relative_to(path.parents[len(path.parts) - 2])),
        ))
    return entries


def find_mcp_json(project_root: str | Path) -> Path | None:
    """Return the path of the first .mcp.json found, or None."""
    root = Path(project_root)
    for candidate in _CANDIDATES:
        p = root / candidate
        if p.exists():
            return p
    return None


def save_mcp_json(project_root: str | Path, entries: list[MCPServerEntry]) -> Path:
    """Write entries to .mcp.json in the project root.

    Always writes to the primary candidate (.mcp.json), merging with any
    existing entries from that file so existing servers are preserved.
    """
    root = Path(project_root)
    path = root / _CANDIDATES[0]

    existing: dict = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}

    servers: dict = existing.get("mcpServers") or {}
    for entry in entries:
        servers[entry.name] = {
            "command": entry.command,
            **({"args": entry.args} if entry.args else {}),
            **({"env": entry.env} if entry.env else {}),
        }

    existing["mcpServers"] = servers
    path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    return path
