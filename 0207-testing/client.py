"""0207 · 不用宿主，直接对服务器做一组快速自检。

运行：uv run python client.py
"""

import asyncio

from fastmcp import Client
from server import mcp


async def main() -> None:
    async with Client(mcp) as client:
        assert (await client.call_tool("divide", {"a": 9, "b": 3})).data == 3
        assert (await client.call_tool("echo", {"text": "ab", "repeat": 2})).data == "abab"

        result = await client.call_tool("divide", {"a": 1, "b": 0}, raise_on_error=False)
        assert result.is_error is True

        content = await client.read_resource("config://flags")
        assert '"beta"' in content[0].text

        tools = {tool.name: tool for tool in await client.list_tools()}
        assert tools["divide"].input_schema["required"] == ["a", "b"]

    print("4 组自检通过。真正的测试在 test_server.py，运行：uv run pytest . -q")


if __name__ == "__main__":
    asyncio.run(main())
