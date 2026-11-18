"""0109 · 完整调用面、ClientGroup 与最小 Host。"""

import json

import pytest
from fastmcp import Client, ClientGroup

from helpers import load_server

CASE = load_server("0109-client-advanced")
MATH = load_server("0109-client-advanced", "math_server.py").math_mcp


@pytest.fixture(autouse=True)
def _reset_tickets():
    """每个测试前清空内存工单，避免测试之间互相污染。"""
    CASE.TICKETS.clear()
    yield


async def test_full_call_surface() -> None:
    async with Client(CASE.mcp) as client:
        assert {tool.name for tool in await client.list_tools()} == {
            "create_ticket",
            "list_tickets",
            "close_ticket",
        }

        created = await client.call_tool("create_ticket", {"title": "测试工单", "priority": "high"})
        assert created.data["id"] >= 1

        payload = await client.read_resource("tickets://all")
        assert json.loads(payload[0].text)[0]["title"] == "测试工单"

        prompt = await client.get_prompt("triage", {"ticket_id": created.data["id"]})
        assert "前端、后端还是运维" in prompt.messages[0].content.text


async def test_error_without_raising() -> None:
    async with Client(CASE.mcp) as client:
        result = await client.call_tool("close_ticket", {"ticket_id": 9999}, raise_on_error=False)
    assert result.is_error is True
    assert "不存在" in result.content[0].text


async def test_client_group_prefixes_and_routes() -> None:
    group = ClientGroup({"ticket": Client(CASE.mcp), "math": Client(MATH)})
    async with group:
        names = {tool.name for tool in await group.list_tools()}
        assert {"ticket_create_ticket", "math_multiply"} <= names

        assert (await group.call_tool("math_multiply", {"a": 6, "b": 7})).data == 42
        assert (await group.call_tool("ticket_list_tickets", {})).data is not None


async def test_mini_host_resolves_names_and_errors() -> None:
    plan = [
        ("math_power", {"base": 2, "exponent": 3}),
        ("math_power", {"base": 2, "exponent": 99}),  # 业务错误
        ("unknown_tool", {}),                          # 不存在
    ]
    group = ClientGroup({"ticket": Client(CASE.mcp), "math": Client(MATH)})
    results = []

    async with group:
        schemas = {tool.name: tool.input_schema for tool in await group.list_tools()}
        for name, arguments in plan:
            if name not in schemas:
                results.append(("skip", name))
                continue
            result = await group.call_tool(name, arguments, raise_on_error=False)
            results.append(("error" if result.is_error else "ok", name))

    assert results == [("ok", "math_power"), ("error", "math_power"), ("skip", "unknown_tool")]
