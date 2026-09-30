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
      },
      "remote-ws": {
        "transport": "websocket",
        "url": "ws://localhost:8080/mcp"
      },
      "remote-sse": {
        "transport": "sse",
        "url": "http://localhost:9090/sse",
        "headers": {"Authorization": "Bearer <token>"}
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
class OAuthConfig:
    """OAuth 2.0 config read from an MCP server's .mcp.json entry."""

    authorization_url: str
    token_url: str
    client_id: str
    scopes: list[str] = field(default_factory=list)
    type: str = "oauth2"

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "authorization_url": self.authorization_url,
            "token_url": self.token_url,
            "client_id": self.client_id,
            "scopes": self.scopes,
        }


@dataclass
class MCPServerEntry:
    name: str
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    source: str = "project"  # "project" | "global"
    transport: str = "stdio"  # "stdio" | "websocket" | "sse"
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    auth: OAuthConfig | None = None

    def to_dict(self) -> dict:
        d: dict = {"transport": self.transport, "source": self.source}
        if self.transport == "stdio":
            d["command"] = self.command
            if self.args:
                d["args"] = self.args
            if self.env:
                d["env"] = self.env
        else:
            d["url"] = self.url
            if self.headers:
                d["headers"] = self.headers
        if self.auth:
            d["auth"] = self.auth.to_dict()
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
        transport = str(cfg.get("transport", "stdio"))
        url = str(cfg.get("url", ""))
        command = str(cfg.get("command", ""))
        # stdio entries require a command; url-based entries require a url
        if transport == "stdio" and not command:
            continue
        if transport in ("websocket", "sse") and not url:
            continue
        auth: OAuthConfig | None = None
        if isinstance(cfg.get("auth"), dict):
            ac = cfg["auth"]
            if ac.get("authorization_url") and ac.get("token_url") and ac.get("client_id"):
                auth = OAuthConfig(
                    authorization_url=str(ac["authorization_url"]),
                    token_url=str(ac["token_url"]),
                    client_id=str(ac["client_id"]),
                    scopes=[str(s) for s in ac.get("scopes", [])],
                    type=str(ac.get("type", "oauth2")),
                )
        entries.append(MCPServerEntry(
            name=str(name),
            command=command,
            args=[str(a) for a in cfg.get("args", [])],
            env={str(k): str(v) for k, v in (cfg.get("env") or {}).items()},
            source=str(path.relative_to(path.parents[len(path.parts) - 2])),
            transport=transport,
            url=url,
            headers={str(k): str(v) for k, v in (cfg.get("headers") or {}).items()},
            auth=auth,
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
        if entry.transport == "stdio":
            servers[entry.name] = {
                "command": entry.command,
                **({"args": entry.args} if entry.args else {}),
                **({"env": entry.env} if entry.env else {}),
                **({"auth": entry.auth.to_dict()} if entry.auth else {}),
            }
        else:
            servers[entry.name] = {
                "transport": entry.transport,
                "url": entry.url,
                **({"headers": entry.headers} if entry.headers else {}),
                **({"auth": entry.auth.to_dict()} if entry.auth else {}),
            }

    existing["mcpServers"] = servers
    path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    return path
