"""0204 · 鉴权三态 + scope 可见性。

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


async def raw_status(url: str, token: str | None) -> int:
    headers = dict(HEADERS)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with httpx2.AsyncClient(timeout=5) as client:
        response = await client.post(url, json=PAYLOAD, headers=headers)
        return response.status_code


async def main() -> None:
    async with serve_http(mcp) as url:
        print("① 原始 HTTP 状态码（不带 / 错 / 对 token）")
        print(f"   无 token   → {await raw_status(url, None)}")
        print(f"   错误 token → {await raw_status(url, 'wrong')}")
        print(f"   正确 token → {await raw_status(url, 'alice-token')}")

        print("\n② alice（read + write）")
        async with Client(url, auth="alice-token") as client:
            print(f"   可见工具 = {[tool.name for tool in await client.list_tools()]}")
            print(f"   whoami   = {(await client.call_tool('whoami', {})).data}")
            print(f"   write    = {(await client.call_tool('write_data', {'item': 'gamma'})).data}")

        print("\n③ bob（只有 read）")
        async with Client(url, auth="bob-token") as client:
            print(f"   可见工具 = {[tool.name for tool in await client.list_tools()]}")
            print(f"   whoami   = {(await client.call_tool('whoami', {})).data}")
            try:
                await client.call_tool("write_data", {"item": "delta"})
            except Exception as exc:
                print(f"   调用 write_data → {type(exc).__name__}: {exc}")

        print("\n④ /health 不需要 token")
        async with httpx2.AsyncClient(timeout=5) as client:
            health = await client.get(url.removesuffix("/mcp") + "/health")
            print(f"   status={health.status_code} body={health.json()}")


if __name__ == "__main__":
    asyncio.run(main())
