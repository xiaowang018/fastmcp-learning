"""0201 · HTTP 传输：健康检查、工具调用、stateless 模式。"""

import httpx2
from fastmcp import Client

from helpers import load_server, serve_http

SERVER = load_server("0201-http-server")


async def get_json(url: str) -> dict:
    async with httpx2.AsyncClient(timeout=5) as client:
        return (await client.get(url)).json()


async def test_health_endpoint() -> None:
    async with serve_http(SERVER.mcp) as url:
        payload = await get_json(url.removesuffix("/mcp") + "/health")
    assert payload["status"] == "ok"


async def test_http_call() -> None:
    async with serve_http(SERVER.mcp) as url:
        async with Client(url) as client:
            assert (await client.call_tool("greet", {"name": "HTTP"})).data.endswith("HTTP 传输。")
            assert (await client.call_tool("add", {"a": 1, "b": 2})).data == 3


async def test_stateless_mode_accepts_new_connections() -> None:
    async with serve_http(SERVER.mcp, stateless_http=True) as url:
        for value in (1, 2):
            async with Client(url) as client:
                assert (await client.call_tool("add", {"a": value, "b": 10})).data == value + 10
