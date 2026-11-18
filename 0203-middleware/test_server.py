"""0203 · 中间件顺序、配额限制、响应截断与审计。"""

import pytest
from fastmcp import Client

from helpers import load_server

SERVER = load_server("0203-middleware")


@pytest.fixture(autouse=True)
def _reset():
    SERVER.reset()
    yield


async def test_quota_returns_business_error() -> None:
    async with Client(SERVER.mcp) as client:
        first = await client.call_tool("add", {"a": 1, "b": 1}, raise_on_error=False)
        second = await client.call_tool("add", {"a": 2, "b": 2}, raise_on_error=False)
        third = await client.call_tool("add", {"a": 3, "b": 3}, raise_on_error=False)

    assert first.data == 2
    assert second.data == 4
    assert third.is_error is True
    assert "配额用尽" in third.content[0].text


async def test_response_is_truncated() -> None:
    async with Client(SERVER.mcp) as client:
        result = await client.call_tool("big", {}, raise_on_error=False)

    text = result.content[0].text
    assert len(text.encode("utf-8")) <= 300
    assert len(text) < 300
    assert "[Response truncated due to size limit]" in text


async def test_audit_records_every_call() -> None:
    async with Client(SERVER.mcp) as client:
        await client.call_tool("slow", {"seconds": 0.01})
        await client.call_tool("big", {})

    assert [item["tool"] for item in SERVER.AUDIT] == ["slow", "big"]
    assert SERVER.AUDIT[0]["arguments"] == {"seconds": 0.01}
