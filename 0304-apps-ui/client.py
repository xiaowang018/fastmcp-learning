"""0304 · 检查 Apps 是否可用，并验证两条路径。

运行：uv run python client.py
"""

import asyncio
import sys
from pathlib import Path

import httpx2
from fastmcp import Client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server  # noqa: E402

from helpers import serve_http  # noqa: E402


async def main() -> None:
    print(f"prefab-ui 可用：{server.HAS_PREFAB}")

    async with Client(server.mcp) as client:
        tools = [tool.name for tool in await client.list_tools()]
        print(f"工具列表：{tools}")
        print(f"get_metrics = {(await client.call_tool('get_metrics', {})).data}")

        if server.HAS_PREFAB:
            result = await client.call_tool("dashboard", {})
            print(f"dashboard: is_error={result.is_error}")
            print(f"  view 根节点 = {result.data['view']['type']}")
            print(f"  子节点数   = {len(result.data['view']['children'])}")
            print("  在支持 MCP Apps 的宿主里，这会渲染成可排序、可搜索的表格。")

    async with serve_http(server.mcp) as url:
        async with httpx2.AsyncClient(timeout=5) as http:
            html = await http.get(url.removesuffix("/mcp") + "/dashboard")
        print(f"\n/dashboard 降级页：status={html.status_code}，长度={len(html.text)}")
        print(f"  含表格：{'<table>' in html.text}")


if __name__ == "__main__":
    asyncio.run(main())
