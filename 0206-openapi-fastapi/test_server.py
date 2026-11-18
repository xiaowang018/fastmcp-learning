"""0206 · FastAPI 自动生成工具与 RouteMap 映射。"""

import pytest

pytest.importorskip("fastapi", reason="需要 uv sync --group api")

from fastmcp import Client  # noqa: E402

from helpers import load_server  # noqa: E402

CASE = load_server("0206-openapi-fastapi")


async def test_default_tools_follow_operation_id() -> None:
    async with Client(CASE.mcp) as client:
        names = {tool.name for tool in await client.list_tools()}

    assert {"list_products", "get_product", "create_product", "list_orders"} <= names


async def test_filter_and_create() -> None:
    async with Client(CASE.mcp) as client:
        filtered = await client.call_tool("list_products", {"category": "electronics"})
        # 自动生成的返回模型是 Pydantic 对象，不是 dict
        assert filtered.data[0].category == "electronics"

        created = await client.call_tool(
            "create_product", {"name": "测试商品", "price": 9.9, "category": "test"}
        )
        assert created.data.id >= 4


async def test_route_maps_convert_get_to_resources() -> None:
    async with Client(CASE.read_mcp) as client:
        resources = [str(item.uri) for item in await client.list_resources()]
        templates = [item.uri_template for item in await client.list_resource_templates()]
        tools = [tool.name for tool in await client.list_tools()]

    assert resources
    assert templates
    assert tools == []
