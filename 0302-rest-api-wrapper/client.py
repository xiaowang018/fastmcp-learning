"""0302 · 先起 mock API，再让 MCP 服务器去调用它。

运行：uv run python client.py
"""

import asyncio
import os
import sys
from pathlib import Path

from fastmcp import Client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mock_api  # noqa: E402
from server import mcp  # noqa: E402

from helpers import serve_asgi  # noqa: E402


async def main() -> None:
    async with serve_asgi(mock_api.app) as api_url:
        os.environ["WEATHER_API"] = api_url
        print(f"mock API = {api_url}")

        async with Client(mcp) as client:
            print(f"current_weather(北京) = {(await client.call_tool('current_weather', {'city': '北京'})).data}")
            print(f"forecast(上海, 2)     = {(await client.call_tool('forecast', {'city': '上海', 'days': 2})).data}")

            missing = await client.call_tool("current_weather", {"city": "杭州"}, raise_on_error=False)
            print(f"未收录城市 → is_error={missing.is_error} {missing.content[0].text}")

            print(f"upstream_health = {(await client.call_tool('upstream_health', {})).data}")

        os.environ["WEATHER_API"] = "http://127.0.0.1:9"
        async with Client(mcp) as client:
            down = await client.call_tool("current_weather", {"city": "北京"}, raise_on_error=False)
            print(f"上游不可达 → is_error={down.is_error} {down.content[0].text}")


if __name__ == "__main__":
    asyncio.run(main())
