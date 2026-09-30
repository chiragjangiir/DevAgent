"""SSE (Server-Sent Events) MCP transport.

Wraps mcp.client.sse.sse_client so MCPManager can connect to remote MCP
servers that expose an HTTP+SSE endpoint.

Usage in .mcp.json:
  {
    "mcpServers": {
      "my-server": {
        "transport": "sse",
        "url": "http://localhost:9090/sse",
        "headers": {"Authorization": "Bearer <token>"}
      }
    }
  }
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.sse import sse_client

from devagent.mcp.client import MCPClient


@asynccontextmanager
async def connect_sse(
    name: str,
    url: str,
    headers: dict[str, str] | None = None,
    timeout: float = 10.0,
) -> AsyncGenerator[MCPClient, None]:
    """Open an SSE MCP connection and yield a ready-to-use MCPClient."""
    async with sse_client(url, headers=headers, timeout=timeout) as (read_stream, write_stream):  # noqa: SIM117
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield MCPClient(session, name)
