"""0202 · lifespan 的资源复用与清理，以及 Depends 的参数隐藏。"""

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from helpers import load_server

SERVER = load_server("0202-lifespan-di")


@pytest.fixture(autouse=True)
def _reset_state():
    SERVER.STATE.update({"started": 0, "stopped": 0, "pool": None})
    yield


async def test_pool_is_shared_across_calls() -> None:
    async with Client(SERVER.mcp) as client:
        first = await client.call_tool("acquire", {"user": "alice"})
        second = await client.call_tool("acquire", {"user": "bob"})
        status = await client.call_tool("pool_status", {})

    assert first.data["in_use"] == 1
    assert second.data["in_use"] == 2
    assert status.data["calls"] == 2
    assert first.data["pool"] == second.data["pool"]


async def test_lifespan_cleanup_runs_after_client_disconnect() -> None:
    async with Client(SERVER.mcp) as client:
        await client.call_tool("acquire", {"user": "alice"})

    assert SERVER.STATE["started"] == 1
    assert SERVER.STATE["stopped"] == 1
    assert SERVER.STATE["pool"].closed is True


async def test_cleanup_runs_even_after_tool_crash() -> None:
    async with Client(SERVER.mcp) as client:
        with pytest.raises(ToolError):
            await client.call_tool("crash", {})

    assert SERVER.STATE["pool"].closed is True
    assert "crash" in SERVER.STATE["pool"].history


async def test_depends_hides_parameter_from_schema() -> None:
    async with Client(SERVER.mcp) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}
        result = await client.call_tool("effective_settings", {})

    assert tools["effective_settings"].input_schema["properties"] == {}
    assert result.data["region"] == "cn-north"
