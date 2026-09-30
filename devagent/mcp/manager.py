"""MCP Manager — launches and manages MCP server processes.

Phase 0: code_search server removed (replaced by codeprism-ai).
         spec_analysis server path updated to legacy location.
"""

from __future__ import annotations

import os
import subprocess
import sys
from contextlib import AsyncExitStack
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from devagent.core.config import DevAgentConfig
from devagent.core.storage import get_config_path
from devagent.mcp.client import MCPClient
from devagent.mcp.clients.brave_client import BraveClient
from devagent.mcp.clients.filesystem_client import FilesystemClient
from devagent.mcp.clients.github_client import GitHubClient
from devagent.mcp.clients.searchx_client import SearchXClient
from devagent.mcp.clients.spec_analysis_client import SpecAnalysisClient
from devagent.mcp.project_config import load_mcp_json


class NodeNotFoundError(Exception):
    """Raised when Node.js is not found in PATH."""


class MCPManager:
    """Async context manager that launches and manages all MCP servers."""

    def __init__(self, config: DevAgentConfig, project_root: Path):
        self.config = config
        self.project_root = project_root
        self._exit_stack = AsyncExitStack()

        # Clients
        self.github: GitHubClient | None = None
        self.filesystem: FilesystemClient | None = None
        self.brave: BraveClient | None = None
        self.searchx: SearchXClient | None = None
        self.spec_analysis: SpecAnalysisClient | None = None
        # Remote servers loaded from .mcp.json (websocket / sse)
        self.remote: dict[str, MCPClient] = {}

    def _check_node(self) -> None:
        """Verify Node.js is installed."""
        try:
            subprocess.run(["node", "--version"], check=True, capture_output=True, text=True, shell=True)
            subprocess.run(["npx", "--version"], check=True, capture_output=True, text=True, shell=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise NodeNotFoundError(
                "Node.js and npx are required for the official MCP servers. "
                "Please download and install Node.js from https://nodejs.org/"
            )

    async def __aenter__(self) -> MCPManager:  # noqa: PYI034
        self._check_node()
        
        env = os.environ.copy()
        env["DEVAGENT_CONFIG_PATH"] = str(get_config_path())
        
        # 1. GitHub Server (Node.js)
        if self.config.github.token:
            gh_env = env.copy()
            gh_env["GITHUB_PERSONAL_ACCESS_TOKEN"] = self.config.github.token
            gh_params = StdioServerParameters(
                command="npx" if sys.platform != "win32" else "npx.cmd",
                args=["-y", "@modelcontextprotocol/server-github"],
                env=gh_env
            )
            gh_transport = await self._exit_stack.enter_async_context(stdio_client(gh_params))
            gh_session = await self._exit_stack.enter_async_context(ClientSession(*gh_transport))
            await gh_session.initialize()
            self.github = GitHubClient(MCPClient(gh_session, "GitHub"))
            
        # 2. Filesystem Server (Node.js)
        fs_params = StdioServerParameters(
            command="npx" if sys.platform != "win32" else "npx.cmd",
            args=["-y", "@modelcontextprotocol/server-filesystem", str(self.project_root.resolve())],
            env=env
        )
        fs_transport = await self._exit_stack.enter_async_context(stdio_client(fs_params))
        fs_session = await self._exit_stack.enter_async_context(ClientSession(*fs_transport))
        await fs_session.initialize()
        self.filesystem = FilesystemClient(MCPClient(fs_session, "Filesystem"))
        
        # 3. Search Server (Brave or SearchX) (Node.js)
        if self.config.search_provider == "brave" and self.config.brave.api_key:
            b_env = env.copy()
            b_env["BRAVE_API_KEY"] = self.config.brave.api_key
            b_params = StdioServerParameters(
                command="npx" if sys.platform != "win32" else "npx.cmd",
                args=["-y", "@modelcontextprotocol/server-brave-search"],
                env=b_env
            )
            b_transport = await self._exit_stack.enter_async_context(stdio_client(b_params))
            b_session = await self._exit_stack.enter_async_context(ClientSession(*b_transport))
            await b_session.initialize()
            self.brave = BraveClient(MCPClient(b_session, "Brave"))
        
        elif self.config.search_provider == "searchx" and self.config.searchx.api_key:
            # Use local SearchX MCP server (Python)
            sx_env = env.copy()
            sx_env["SEARCHX_API_KEY"] = self.config.searchx.api_key
            sx_params = StdioServerParameters(
                command=sys.executable,
                args=["-m", "devagent.mcp.servers.searchx.server"],
                env=sx_env
            )
            sx_transport = await self._exit_stack.enter_async_context(stdio_client(sx_params))
            sx_session = await self._exit_stack.enter_async_context(ClientSession(*sx_transport))
            await sx_session.initialize()
            self.searchx = SearchXClient(MCPClient(sx_session, "SearchX"))
            
        # 4. SpecAnalysis Server — legacy Python MCP (used by devagent analyze)
        sa_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "devagent.legacy.mcp.servers.spec_analysis.server"],
            env=env
        )
        sa_transport = await self._exit_stack.enter_async_context(stdio_client(sa_params))
        sa_session = await self._exit_stack.enter_async_context(ClientSession(*sa_transport))
        await sa_session.initialize()
        self.spec_analysis = SpecAnalysisClient(MCPClient(sa_session, "SpecAnalysis"))

        # Connect any websocket / sse servers declared in .mcp.json
        await self._connect_remote_servers()

        return self

    async def _connect_remote_servers(self) -> None:
        """Connect non-stdio servers declared in the project's .mcp.json."""
        from devagent.mcp.transports import connect_entry
        entries = load_mcp_json(self.project_root)
        for entry in entries:
            if entry.transport == "stdio":
                continue  # stdio servers are managed separately
            try:
                client = await self._exit_stack.enter_async_context(connect_entry(entry))
                self.remote[entry.name] = client
            except Exception:
                pass  # best-effort: don't abort startup for unreachable remote servers

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        await self._exit_stack.aclose()
