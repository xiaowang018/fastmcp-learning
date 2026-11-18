"""0104 · 把五类失败固化成断言，避免以后「错误消息悄悄变了」。"""

import asyncio

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from helpers import load_server

SERVER = load_server("0104-tool-errors")


async def test_validation_error_is_wrapped_as_tool_error() -> None:
    async with Client(SERVER.mcp) as client:
        with pytest.raises(ToolError) as info:
            await client.call_tool("divide", {"a": "abc", "b": 2})
    assert "validation error" in str(info.value)


async def test_business_tool_error_keeps_message() -> None:
    async with Client(SERVER.mcp) as client:
        with pytest.raises(ToolError) as info:
            await client.call_tool("withdraw", {"amount": 500})
    assert "余额不足" in str(info.value)


async def test_unhandled_exception_leaks_detail_when_not_masked() -> None:
    async with Client(SERVER.mcp) as client:
        with pytest.raises(ToolError) as info:
            await client.call_tool("crash", {})
        assert "secret" in str(info.value)

        result = await client.call_tool("crash", {}, raise_on_error=False)
        assert result.is_error is True


async def test_server_side_timeout() -> None:
    async with Client(SERVER.mcp, timeout=10) as client:
        with pytest.raises(ToolError) as info:
            await client.call_tool("slow", {"seconds": 1})
    assert "timed out" in str(info.value).lower()


async def test_client_side_cancellation() -> None:
    async with Client(SERVER.mcp, timeout=10) as client:
        task = asyncio.create_task(client.call_tool("slow", {"seconds": 1}))
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


async def test_read_only_annotation_visible() -> None:
    async with Client(SERVER.mcp) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}
    assert tools["get_balance"].annotations.read_only_hint is True
