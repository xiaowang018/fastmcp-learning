"""0101 · 用 FastMCP Client 直连服务器，不需要任何宿主。

运行：uv run python client.py
"""

import asyncio

from fastmcp import Client
from server import mcp


async def main() -> None:
    # 直接传 FastMCP 实例 = 进程内连接，不启动子进程、不占端口，最快。
    async with Client(mcp) as client:
        print(f"服务器：{client.server_info.name}")
        print(f"协议版本：{client.protocol_version}")

        tools = await client.list_tools()
        print(f"工具列表：{[tool.name for tool in tools]}")
        print(f"add 的入参 schema：{tools[0].input_schema}")

        result = await client.call_tool("add", {"a": 2, "b": 3})
        print(f"add(2, 3) = {result.data}")

        resource = await client.read_resource("info://server")
        print(f"资源 info://server = {resource[0].text}")


if __name__ == "__main__":
    asyncio.run(main())
