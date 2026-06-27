"""
MCPClientTool — wraps a single MCP server tool as a CrewAI BaseTool.

Created by MCPRegistry.tools_for_agent(); one instance per (server, tool) pair.
The args_schema is generated from the MCP tool's JSON Schema inputSchema so the
LLM gets proper field names, types, and descriptions.
"""

from __future__ import annotations

from typing import Any, Optional

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, create_model


_TYPE_MAP: dict[str, type] = {
    "string":  str,
    "integer": int,
    "number":  float,
    "boolean": bool,
    "array":   list,
    "object":  dict,
}


def _make_schema(input_schema: dict) -> type[BaseModel]:
    """Build a Pydantic model from a JSON Schema dict (subset used by MCP)."""
    properties: dict = input_schema.get("properties") or {}
    required: set[str] = set(input_schema.get("required") or [])
    fields: dict[str, Any] = {}

    for prop_name, prop_info in properties.items():
        py_type = _TYPE_MAP.get(prop_info.get("type", "string"), str)
        desc = prop_info.get("description", "")
        if prop_name in required:
            fields[prop_name] = (py_type, Field(description=desc))
        else:
            fields[prop_name] = (Optional[py_type], Field(default=None, description=desc))

    if not fields:
        fields["_noop"] = (Optional[str], Field(default=None, description="No arguments."))

    return create_model("MCPInput", **fields)


class MCPClientTool(BaseTool):
    """Proxy to one tool exposed by a connected MCP server."""

    name: str
    description: str
    args_schema: type[BaseModel]

    server_name: str = ""
    mcp_tool_name: str = ""

    def _run(self, **kwargs: Any) -> str:
        from shared.mcp_registry import MCPRegistry
        # Drop None values from optional fields
        args = {k: v for k, v in kwargs.items() if v is not None and k != "_noop"}
        try:
            return MCPRegistry.get().call_tool(self.server_name, self.mcp_tool_name, args)
        except Exception as exc:
            return f"ERROR: MCP {self.server_name}/{self.mcp_tool_name} — {exc}"


def make_mcp_tools(server_name: str, mcp_tools: list) -> list[MCPClientTool]:
    """
    Convert a list of mcp.types.Tool into MCPClientTool instances.
    Prefixes tool names with server name to avoid collisions across servers.
    """
    result: list[MCPClientTool] = []
    for tool in mcp_tools:
        input_schema = {}
        if hasattr(tool, "inputSchema"):
            s = tool.inputSchema
            # mcp.types.Tool.inputSchema may be a dict or a Pydantic model
            input_schema = s.model_dump() if hasattr(s, "model_dump") else (s or {})

        safe_name = f"mcp_{server_name}_{tool.name}".replace("-", "_").replace(".", "_")[:64]
        desc = (tool.description or f"MCP tool: {tool.name} from {server_name}")[:500]

        result.append(MCPClientTool(
            name=safe_name,
            description=desc,
            args_schema=_make_schema(input_schema),
            server_name=server_name,
            mcp_tool_name=tool.name,
        ))
    return result
