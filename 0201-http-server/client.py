"""0201 · 用真实 uvicorn 起服务，验证 /health、MCP 调用与 stateless 模式。

运行：uv run python client.py
"""

import asyncio
import sys
from pathlib import Path

import httpx2
from fastmcp import Client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import mcp  # noqa: E402

from helpers import serve_http  # noqa: E402


async def get_json(url: str) -> dict:
    # 必须用异步 HTTP 客户端：uvicorn 和调用方共享同一个事件循环，
    # 同步 urllib 会阻塞循环，导致请求永远等不到响应。
    async with httpx2.AsyncClient(timeout=5) as client:
        response = await client.get(url)
        return response.json()


async def main() -> None:
    print("① 有状态 HTTP 服务（默认）")
    async with serve_http(mcp) as url:
        base = url.removesuffix("/mcp")
        print(f"   MCP URL  = {url}")
        print(f"   health   = {await get_json(base + '/health')}")

        async with Client(url) as client:
            print(f"   协议版本 = {client.protocol_version}")
            print(f"   greet    = {(await client.call_tool('greet', {'name': 'MCP'})).data}")
            print(f"   add      = {(await client.call_tool('add', {'a': 20, 'b': 22})).data}")

    print("\n② stateless_http=True：不保留会话，适合多副本")
    async with serve_http(mcp, stateless_http=True) as url:
        for index in (1, 2):
            async with Client(url) as client:
                result = await client.call_tool("add", {"a": index, "b": 1})
                print(f"   第 {index} 个连接：add = {result.data}")

    print("\n③ 手动运行方式")
    print("   uv run python server.py                 # 端口 8101")
    print("   uv run uvicorn app:app --port 8101      # 带 CORS 的 ASGI 入口")


if __name__ == "__main__":
    asyncio.run(main())
