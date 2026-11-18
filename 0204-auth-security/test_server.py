"""0204 · 鉴权三态、scope 可见性与健康检查。"""

import httpx2
from fastmcp import Client

from helpers import load_server, serve_http

SERVER = load_server("0204-auth-security")

PAYLOAD = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "raw", "version": "1"},
    },
}
HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


async def status(url: str, token: str | None) -> int:
    headers = dict(HEADERS)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with httpx2.AsyncClient(timeout=5) as client:
        return (await client.post(url, json=PAYLOAD, headers=headers)).status_code


async def test_auth_three_states() -> None:
    async with serve_http(SERVER.mcp) as url:
        assert await status(url, None) == 401
        assert await status(url, "wrong") == 401
        assert await status(url, "alice-token") == 200


async def test_scope_hides_tool() -> None:
    async with serve_http(SERVER.mcp) as url:
        async with Client(url, auth="alice-token") as client:
            assert "write_data" in {tool.name for tool in await client.list_tools()}

        async with Client(url, auth="bob-token") as client:
            names = {tool.name for tool in await client.list_tools()}
            assert "write_data" not in names
            assert (await client.call_tool("whoami", {})).data["subject"] == "bob"


async def test_health_is_unprotected() -> None:
    async with serve_http(SERVER.mcp) as url:
        async with httpx2.AsyncClient(timeout=5) as client:
            response = await client.get(url.removesuffix("/mcp") + "/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
