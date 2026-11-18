"""0202 · 观察连接池的启动、复用与关闭。

运行：uv run python client.py
"""

import asyncio

from fastmcp import Client
from fastmcp.exceptions import ToolError
from server import STATE, mcp


async def main() -> None:
    print(f"连接前：started={STATE['started']} stopped={STATE['stopped']}")

    async with Client(mcp) as client:
        print(f"连接后：started={STATE['started']} stopped={STATE['stopped']}")

        for user in ("alice", "bob"):
            result = await client.call_tool("acquire", {"user": user})
            print(f"acquire({user}) = {result.data}")

        status = await client.call_tool("pool_status", {})
        print(f"pool_status = {status.data}")

        released = await client.call_tool("release", {"user": "alice"})
        print(f"release(alice) = {released.data}")

        settings = await client.call_tool("effective_settings", {})
        print(f"effective_settings = {settings.data}")

        tools = await client.list_tools()
        settings_tool = {tool.name: tool for tool in tools}["effective_settings"]
        print(f"effective_settings 的参数 = {list(settings_tool.input_schema['properties'])}")

        try:
            await client.call_tool("crash", {})
        except ToolError as exc:
            print(f"crash = {exc}")

    print(f"断开后：started={STATE['started']} stopped={STATE['stopped']} closed={STATE['pool'].closed}")
    print(f"池历史 = {STATE['pool'].history}")


if __name__ == "__main__":
    asyncio.run(main())
