"""0108 · 三种连接方式 + 两个协议纪元。

运行：uv run python client.py
"""

import asyncio
import sys
from pathlib import Path

from fastmcp import Client

# 直接运行 client.py 时，sys.path[0] 是本案例目录；helpers.py 在项目根目录。
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import mcp  # noqa: E402

from helpers import serve_http  # noqa: E402

CASE_DIR = Path(__file__).parent


async def main() -> None:
    print("① 进程内连接 Client(mcp)")
    async with Client(mcp) as client:
        print(f"   protocol_version = {client.protocol_version}")
        print(f"   ping = {(await client.call_tool('ping', {})).data}")

    print("\n② stdio 子进程 Client(Path('server.py'))")
    async with Client(CASE_DIR / "server.py", timeout=20) as client:
        print(f"   protocol_version = {client.protocol_version}")
        print(f"   ping = {(await client.call_tool('ping', {})).data}")

    print("\n③ HTTP：后台起 uvicorn，再按 URL 连接")
    async with serve_http(mcp) as url:
        print(f"   url = {url}")
        async with Client(url) as client:
            print(f"   protocol_version = {client.protocol_version}（auto，协商到现代协议）")
            print(f"   ping = {(await client.call_tool('ping', {})).data}")

        async with Client(url, mode="legacy") as client:
            print(f"   protocol_version = {client.protocol_version}（强制 legacy）")
            print(f"   ping = {(await client.call_tool('ping', {})).data}")

        print("\n④ 同一 URL、两种协议下的 session_id")
        for mode in ("auto", "legacy"):
            async with Client(url, mode=mode) as client:
                first = await client.call_tool("state_demo", {"value": "A"})
                second = await client.call_tool("state_demo", {"value": "B"})
                print(f"   {mode:6s} first={first.data['session_id'][:8]} second={second.data['session_id'][:8]}")
                print(f"          before(second)={second.data['before']}")


if __name__ == "__main__":
    asyncio.run(main())
