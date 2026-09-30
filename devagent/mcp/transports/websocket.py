"""WebSocket MCP transport.

Wraps mcp.client.websocket.websocket_client so MCPManager can connect to
remote MCP servers that expose a WebSocket endpoint.

Usage in .mcp.json:
  {
    "mcpServers": {
      "my-server": {
        "transport": "websocket",
        "url": "ws://localhost:8080/mcp"
      }
    }
  }
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from mcp import ClientSession

from devagent.mcp.client import MCPClient


@asynccontextmanager
async def connect_websocket(
    name: str,
    url: str,
) -> AsyncGenerator[MCPClient, None]:
    """Open a WebSocket MCP connection and yield a ready-to-use MCPClient.

    Requires mcp>=1.2 (mcp.client.websocket). Raises ImportError on older versions.
    """
    from mcp.client.websocket import websocket_client  # lazy: not all mcp builds include this
    async with websocket_client(url) as (read_stream, write_stream):  # noqa: SIM117
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield MCPClient(session, name)
