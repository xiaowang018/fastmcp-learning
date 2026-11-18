"""0205 · 通过网关访问三个子服务器。

运行：uv run python client.py
"""

import asyncio

from fastmcp import Client
from server import mcp


async def main() -> None:
    async with Client(mcp) as client:
        tools = sorted(tool.name for tool in await client.list_tools())
        print("网关工具：")
        for name in tools:
            print(f"  - {name}")

        print("\n同名工具已被 namespace 消歧：")
        print(f"  weather_get_weather(北京) = {(await client.call_tool('weather_get_weather', {'city': '北京'})).data}")
        print(f"  calendar_get_weather(2026-11-15) = {(await client.call_tool('calendar_get_weather', {'date': '2026-11-15'})).data}")

        print("\n代理的独立进程工具：")
        print(f"  math_multiply(6, 7) = {(await client.call_tool('math_multiply', {'a': 6, 'b': 7})).data}")

        resources = [str(item.uri) for item in await client.list_resources()]
        print(f"\n资源也被 namespace 了：{resources}")
        content = await client.read_resource("weather://weather/cities")
        print(f"  weather://weather/cities = {content[0].text}")

        prompts = [item.name for item in await client.list_prompts()]
        print(f"提示：{prompts}")


if __name__ == "__main__":
    asyncio.run(main())
