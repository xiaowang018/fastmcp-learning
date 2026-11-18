"""0207 · 五类测试：正常路径、参数化、业务错误、schema 契约、真实 stdio。

运行：
    uv run pytest . -q
    uv run pytest . -q -m "not slow"
"""

from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from helpers import load_server

CASE_DIR = Path(__file__).parent
SERVER = load_server("0207-testing")


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [(9, 3, 3.0), (1, 2, 0.5), (-4, 2, -2.0), (0, 5, 0.0)],
)
async def test_divide_normal_cases(a: float, b: float, expected: float) -> None:
    async with Client(SERVER.mcp) as client:
        assert (await client.call_tool("divide", {"a": a, "b": b})).data == expected


async def test_business_error_is_visible_to_model() -> None:
    async with Client(SERVER.mcp) as client:
        with pytest.raises(ToolError) as info:
            await client.call_tool("divide", {"a": 1, "b": 0})
    assert "除数不能为 0" in str(info.value)


async def test_schema_contract() -> None:
    """schema 是模型看到的契约，改动它等于改 API，必须有测试兜住。"""
    async with Client(SERVER.mcp) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}

    divide = tools["divide"].input_schema
    assert divide["required"] == ["a", "b"]
    assert divide["properties"]["a"]["type"] == "number"

    echo = tools["echo"].input_schema
    assert echo["properties"]["repeat"]["default"] == 1
    assert echo["required"] == ["text"]


async def test_resource_payload() -> None:
    async with Client(SERVER.mcp) as client:
        content = await client.read_resource("config://flags")
    assert content[0].mime_type == "application/json"
    assert '"max_items": 20' in content[0].text


@pytest.mark.slow
async def test_stdio_transport() -> None:
    """真实宿主走的是 stdio，别只测进程内。"""
    async with Client(CASE_DIR / "server.py", timeout=20) as client:
        assert (await client.call_tool("echo", {"text": "hi"})).data == "hi"


async def test_validation_rejects_bad_repeat() -> None:
    async with Client(SERVER.mcp) as client:
        result = await client.call_tool("echo", {"text": "x", "repeat": 9}, raise_on_error=False)
    assert result.is_error is True
    assert "1-5" in result.content[0].text
