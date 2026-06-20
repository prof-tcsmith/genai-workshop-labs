"""Tiny SYNC client for the Course Content Studio MCP server.

The whole point of the MCP unit is *decoupling*: the app no longer imports
``pinecone`` / ``psycopg`` (and their credentials) directly — it speaks one
standard protocol to a server that owns the tools. This module is that single
seam.

It connects to :data:`lib.config.MCP_SERVER_URL` over **streamable-http**, calls
a tool, and returns the parsed result. The MCP SDK is async, so we wrap each
round-trip in :func:`asyncio.run` and expose plain synchronous helpers that a
Streamlit page can call directly.

Public API:
    call_tool(name, args) -> any        # invoke one tool, return its parsed result
    list_tools()          -> list[dict] # the server's advertised tool catalog

Both raise :class:`MCPUnavailable` (a friendly ``RuntimeError``) if the server
can't be reached — so the page can show the local-Docker run instructions
instead of a raw traceback.
"""
from __future__ import annotations

import asyncio
from typing import Any

from lib import config


class MCPUnavailable(RuntimeError):
    """Raised when the MCP server can't be reached or the call fails."""


def _friendly(exc: Exception) -> "MCPUnavailable":
    return MCPUnavailable(
        f"Could not reach the MCP server at {config.MCP_SERVER_URL!r}. "
        "It runs locally in Docker for now — build and run it first "
        "(see mcp-server/README.md), then set the 'mcp_server_url' secret. "
        f"[{type(exc).__name__}: {exc}]"
    )


def _parse_result(result: Any) -> Any:
    """Pull the useful payload out of an MCP ``CallToolResult``.

    Prefer ``structuredContent`` (tools that return dicts/lists come back here);
    otherwise fall back to the text content blocks.
    """
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        # FastMCP wraps non-dict returns (e.g. a list) under a "result" key.
        if isinstance(structured, dict) and set(structured.keys()) == {"result"}:
            return structured["result"]
        return structured

    blocks = getattr(result, "content", None) or []
    texts = [getattr(b, "text", None) for b in blocks]
    texts = [t for t in texts if t is not None]
    if len(texts) == 1:
        return texts[0]
    return texts or None


async def _call_async(name: str, args: dict) -> Any:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async with streamablehttp_client(config.MCP_SERVER_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(name, args or {})
    if getattr(result, "isError", False):
        raise MCPUnavailable(f"Tool {name!r} returned an error: {_parse_result(result)}")
    return _parse_result(result)


async def _list_async() -> list[dict]:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async with streamablehttp_client(config.MCP_SERVER_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listing = await session.list_tools()
    out: list[dict] = []
    for t in getattr(listing, "tools", []) or []:
        out.append({
            "name": getattr(t, "name", ""),
            "description": getattr(t, "description", "") or "",
            "input_schema": getattr(t, "inputSchema", None),
        })
    return out


def call_tool(name: str, args: dict | None = None) -> Any:
    """Invoke an MCP tool by name and return its parsed result.

    Raises :class:`MCPUnavailable` with a friendly message if the server is
    unreachable.
    """
    try:
        return asyncio.run(_call_async(name, args or {}))
    except MCPUnavailable:
        raise
    except Exception as exc:  # connection refused, timeout, import error, etc.
        raise _friendly(exc) from exc


def list_tools() -> list[dict]:
    """Return the server's advertised tool catalog as a list of dicts.

    Each entry is ``{"name", "description", "input_schema"}``. Raises
    :class:`MCPUnavailable` if the server is unreachable.
    """
    try:
        return asyncio.run(_list_async())
    except MCPUnavailable:
        raise
    except Exception as exc:
        raise _friendly(exc) from exc
