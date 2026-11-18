"""0102 · 用测试锁住「schema 是契约」这件事。"""

from fastmcp import Client
from fastmcp.exceptions import ToolError

from helpers import load_server

SERVER = load_server("0102-tool-schema")


async def test_schema_has_descriptions_and_constraints() -> None:
    async with Client(SERVER.mcp) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}

    basic = tools["search_basic"].input_schema
    assert basic["required"] == ["query"]
    assert basic["properties"]["limit"]["default"] == 5
    assert "description" not in basic["properties"]["query"]

    annotated = tools["search_annotated"].input_schema
    assert annotated["properties"]["query"]["minLength"] == 2
    assert annotated["properties"]["limit"]["minimum"] == 1
    assert annotated["properties"]["limit"]["maximum"] == 20
    assert annotated["properties"]["sort"]["enum"] == ["relevance", "newest"]

    structured = tools["search_structured"].input_schema
    assert "request" in structured["properties"]
    # 默认会解引用 $ref，把嵌套模型内联进 schema
    assert "query" in structured["properties"]["request"]["properties"]


async def test_validation_rejects_short_query() -> None:
    async with Client(SERVER.mcp) as client:
        try:
            await client.call_tool("search_annotated", {"query": "a"})
        except ToolError as exc:
            assert "at least 2 characters" in str(exc) or "min_length" in str(exc)
        else:  # pragma: no cover - 校验必须失败
            raise AssertionError("过短的 query 应该被拒绝")


async def test_structured_call_with_nested_model() -> None:
    async with Client(SERVER.mcp) as client:
        result = await client.call_tool(
            "search_structured",
            {
                "request": {
                    "query": "mcp",
                    "tags": ["mcp"],
                    "date_range": {"start": "2026-10-01", "end": "2026-12-31"},
                }
            },
        )
    assert result.data["total"] == 2
