"""
MCPRegistry — manage MCP server connections for code-crew agents.

Config: ~/.code-crew/mcp.yaml

  servers:
    figma:
      command: npx @figma/mcp-server
      env:
        FIGMA_TOKEN: ${FIGMA_TOKEN}
      agents: [ux_lead]          # omit → all agents
    linear:
      command: npx @linear/mcp-server
      agents: [architect, scrum_master]

Usage:
  registry = MCPRegistry.get()
  tools = registry.connect("figma")          # list[mcp.types.Tool]
  result = registry.call_tool("figma", "get_file", {"file_key": "abc"})
  registry.disconnect("figma")
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Async bridge — one event loop thread for all MCP I/O
# ---------------------------------------------------------------------------

class _AsyncBridge:
    _instance: "_AsyncBridge | None" = None
    _lock = threading.Lock()

    @classmethod
    def get(cls) -> "_AsyncBridge":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop.run_forever, daemon=True, name="mcp-event-loop"
        )
        self._thread.start()

    def run(self, coro, timeout: float = 60.0):
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return fut.result(timeout=timeout)

    def stop(self) -> None:
        self._loop.call_soon_threadsafe(self._loop.stop)


# ---------------------------------------------------------------------------
# Connection state
# ---------------------------------------------------------------------------

@dataclass
class _Connection:
    server_name: str
    session: object                    # mcp.ClientSession
    exit_stack: object                 # contextlib.AsyncExitStack
    tools: list = field(default_factory=list)   # list[mcp.types.Tool]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class MCPRegistry:
    """Singleton that manages MCP server connections."""

    _instance: "MCPRegistry | None" = None
    _cls_lock = threading.Lock()

    @classmethod
    def get(cls) -> "MCPRegistry":
        with cls._cls_lock:
            if cls._instance is None:
                cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        self._connections: dict[str, _Connection] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    @staticmethod
    def config_path() -> Path:
        return Path.home() / ".code-crew" / "mcp.yaml"

    @staticmethod
    def load_config() -> dict:
        path = MCPRegistry.config_path()
        if not path.exists():
            return {}
        try:
            return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            raise RuntimeError(f"Failed to load mcp.yaml: {exc}") from exc

    def server_names(self) -> list[str]:
        return list(self.load_config().get("servers", {}).keys())

    def connected_names(self) -> list[str]:
        with self._lock:
            return list(self._connections.keys())

    def server_config(self, name: str) -> dict:
        cfg = self.load_config().get("servers", {})
        if name not in cfg:
            raise KeyError(
                f"MCP server '{name}' not in mcp.yaml. "
                f"Available: {list(cfg)} — add it at {self.config_path()}"
            )
        return cfg[name]

    # ------------------------------------------------------------------
    # Connect / disconnect
    # ------------------------------------------------------------------

    def connect(self, name: str) -> list:
        """Start an MCP server and return its tool list. No-op if already connected."""
        with self._lock:
            if name in self._connections:
                return self._connections[name].tools

        server_cfg = self.server_config(name)
        bridge = _AsyncBridge.get()
        conn = bridge.run(self._async_connect(name, server_cfg), timeout=90.0)

        with self._lock:
            self._connections[name] = conn
        return conn.tools

    async def _async_connect(self, name: str, cfg: dict) -> _Connection:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        command, args = _parse_command(cfg)
        env = _resolve_env(cfg.get("env", {})) or None

        params = StdioServerParameters(command=command, args=args, env=env)
        stack = contextlib.AsyncExitStack()
        read, write = await stack.enter_async_context(stdio_client(params))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        result = await session.list_tools()
        return _Connection(server_name=name, session=session, exit_stack=stack, tools=result.tools)

    def disconnect(self, name: str) -> None:
        with self._lock:
            conn = self._connections.pop(name, None)
        if conn is None:
            return
        try:
            _AsyncBridge.get().run(conn.exit_stack.aclose(), timeout=10.0)
        except Exception:
            pass

    def disconnect_all(self) -> None:
        for name in list(self._connections):
            self.disconnect(name)

    # ------------------------------------------------------------------
    # Tool invocation
    # ------------------------------------------------------------------

    def call_tool(self, server_name: str, tool_name: str, arguments: dict) -> str:
        with self._lock:
            conn = self._connections.get(server_name)
        if conn is None:
            raise RuntimeError(
                f"MCP server '{server_name}' is not connected. "
                f"Run /mcp connect {server_name} first."
            )
        result = _AsyncBridge.get().run(
            conn.session.call_tool(tool_name, arguments), timeout=60.0
        )
        parts: list[str] = []
        for item in result.content:
            if hasattr(item, "text"):
                parts.append(item.text)
            elif hasattr(item, "data"):
                parts.append(f"[binary {len(item.data)} bytes]")
            else:
                parts.append(str(item))
        return "\n".join(parts) if parts else "(empty response)"

    # ------------------------------------------------------------------
    # Agent routing
    # ------------------------------------------------------------------

    def tools_for_agent(self, agent_name: str) -> list:
        """
        Return (server_name, mcp_tool) pairs for tools available to this agent.
        Checks the `agents:` list in each server's config; omitting `agents:` means all agents.
        Only returns tools from currently connected servers.
        """
        try:
            config = self.load_config().get("servers", {})
        except Exception:
            return []

        pairs: list[tuple[str, object]] = []
        with self._lock:
            connected = dict(self._connections)

        for server_name, conn in connected.items():
            server_cfg = config.get(server_name, {})
            allowed = server_cfg.get("agents")
            if allowed is not None and agent_name not in allowed:
                continue
            for tool in conn.tools:
                pairs.append((server_name, tool))
        return pairs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_command(cfg: dict) -> tuple[str, list[str]]:
    """Return (executable, args_list) from server config."""
    command = cfg.get("command", "")
    args = cfg.get("args", [])
    if isinstance(args, str):
        args = args.split()
    # "npx @figma/mcp-server" shorthand — split on first space if no args provided
    if isinstance(command, str) and " " in command and not args:
        parts = command.split()
        return parts[0], parts[1:]
    return command, list(args)


def _resolve_env(env_cfg: dict) -> dict:
    """Expand ${VAR} placeholders from os.environ."""
    out: dict[str, str] = {}
    for key, value in env_cfg.items():
        if isinstance(value, str):
            value = re.sub(
                r"\$\{([^}]+)\}",
                lambda m: os.environ.get(m.group(1), ""),
                value,
            )
        out[key] = str(value)
    return out
