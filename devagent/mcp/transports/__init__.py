"""MCP transport layer — websocket and SSE client wrappers."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from devagent.mcp.client import MCPClient
    from devagent.mcp.project_config import MCPServerEntry


@asynccontextmanager
async def connect_entry(entry: MCPServerEntry) -> AsyncGenerator[MCPClient, None]:
    """Connect to an MCP server described by MCPServerEntry, dispatching on transport."""
    if entry.transport == "websocket":
        from devagent.mcp.transports.websocket import connect_websocket
        async with connect_websocket(entry.name, entry.url) as client:
            yield client
    elif entry.transport == "sse":
        from devagent.mcp.transports.sse import connect_sse
        headers = entry.headers if entry.headers else None
        async with connect_sse(entry.name, entry.url, headers=headers) as client:
            yield client
    else:
        raise ValueError(f"Unsupported transport {entry.transport!r} for entry {entry.name!r}")
