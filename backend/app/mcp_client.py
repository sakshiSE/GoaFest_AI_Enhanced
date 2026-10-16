"""MCP client bridge used by the LangGraph retrieval node and diagnostic API.

The web app starts the real stdio MCP server as a child process, initializes an MCP
session, and calls registered tools over the MCP protocol. A direct CSV fallback is
kept by the graph so a missing optional runtime does not make planning unavailable.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]

async def _with_session(operation):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.mcp_server"],
        cwd=str(BACKEND_DIR),
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            return await operation(session)

async def _call_tools_async(calls: list[tuple[str, dict]]) -> dict:
    async def operation(session):
        output = {}
        for name, arguments in calls:
            result = await session.call_tool(name, arguments)
            if getattr(result, "isError", False):
                raise RuntimeError(f"MCP tool {name} returned an error")
            parsed = None
            for content in getattr(result, "content", []):
                if getattr(content, "type", None) == "text":
                    try:
                        parsed = json.loads(content.text)
                        break
                    except (TypeError, json.JSONDecodeError):
                        parsed = content.text
            if parsed is None:
                parsed = getattr(result, "structuredContent", None)
            output[name] = parsed
        return output
    return await _with_session(operation)

def call_tourism_tools(festival: str, interests: list[str], food_preferences: list[str]) -> dict:
    """Invoke three registered MCP tools through a real MCP client session."""
    return asyncio.run(_call_tools_async([
        ("festival_information", {"festival": festival}),
        ("attractions", {"interests": interests}),
        ("food_options", {"preferences": food_preferences}),
    ]))

async def list_mcp_tools() -> list[dict]:
    async def operation(session):
        result = await session.list_tools()
        return [{"name": item.name, "description": item.description, "inputSchema": item.inputSchema}
                for item in result.tools]
    return await _with_session(operation)

async def call_single_mcp_tool(name: str, arguments: dict) -> dict:
    async def operation(session):
        available = await session.list_tools()
        if name not in {item.name for item in available.tools}:
            raise ValueError(f"Unknown MCP tool: {name}")
        result = await session.call_tool(name, arguments)
        content = []
        for item in getattr(result, "content", []):
            if getattr(item, "type", None) == "text":
                try: content.append(json.loads(item.text))
                except (TypeError, json.JSONDecodeError): content.append(item.text)
        return {"tool": name, "is_error": bool(getattr(result, "isError", False)),
                "result": content[0] if len(content) == 1 else content}
    return await _with_session(operation)
