"""0206 · 对比自动生成与自定义映射。

运行：uv run python client.py
"""

import asyncio

from fastmcp import Client
from server import mcp, read_mcp


async def main() -> None:
    print("① from_fastapi 默认：所有端点 → 工具")
    async with Client(mcp) as client:
        for tool in await client.list_tools():
            print(f"   - {tool.name}: {tool.description}")

        products = await client.call_tool("list_products", {"category": "electronics"})
        print(f"\n   list_products(electronics) = {products.data}")

        created = await client.call_tool(
            "create_product", {"name": "USB-C 扩展坞", "price": 299, "category": "electronics"}
        )
        print(f"   create_product = {created.data}")

        try:
            await client.call_tool("get_product", {"product_id": 999})
        except Exception as exc:
            print(f"   404 映射 → {type(exc).__name__}: {exc}")

    print("\n② 自定义 RouteMap：GET 变资源，POST 被排除")
    async with Client(read_mcp) as client:
        resources = [str(item.uri) for item in await client.list_resources()]
        templates = [item.uri_template for item in await client.list_resource_templates()]
        print(f"   资源      = {resources}")
        print(f"   资源模板  = {templates}")
        print(f"   工具      = {[tool.name for tool in await client.list_tools()]}")

        if resources:
            content = await client.read_resource(resources[0])
            print(f"   读取 {resources[0]} = {content[0].text[:120]}")


if __name__ == "__main__":
    asyncio.run(main())
