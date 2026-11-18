"""0305 · 校验配置、跑通服务、生成宿主配置。

运行：uv run python client.py
"""

import asyncio
import json
import shutil
import subprocess
import sys
from pathlib import Path

import httpx2
from fastmcp import Client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import mcp  # noqa: E402

from helpers import serve_http  # noqa: E402

CASE_DIR = Path(__file__).parent


async def main() -> None:
    config = json.loads((CASE_DIR / "fastmcp.json").read_text(encoding="utf-8"))
    print("--- fastmcp.json ---")
    print(json.dumps(config, ensure_ascii=False, indent=2))

    async with serve_http(mcp) as url:
        async with Client(url) as client:
            print(f"\nMCP 调用：server_time = {(await client.call_tool('server_time', {})).data}")
            print(f"          roll_dice  = {(await client.call_tool('roll_dice', {'sides': 20})).data}")

        async with httpx2.AsyncClient(timeout=5) as http:
            health = await http.get(url.removesuffix("/mcp") + "/health")
            print(f"/health = {health.json()}")

    print("\n--- 手动运行 ---")
    print("  uv run fastmcp run fastmcp.json")
    print("  uv run fastmcp inspect fastmcp.json")

    print("\n--- 生成宿主配置（只打印，不改本机）---")
    exe = shutil.which("fastmcp")
    if exe:
        proc = subprocess.run(
            [exe, "install", "mcp-json", "server.py", "--name", "deploy-demo"],
            cwd=CASE_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        print(proc.stdout.strip() or proc.stderr.strip())
    else:  # pragma: no cover
        print("  未找到 fastmcp 命令，跳过")

    print("\n--- 容器 ---")
    print("  docker build -t fastmcp-demo .")
    print("  docker run --rm -p 8109:8109 fastmcp-demo")


if __name__ == "__main__":
    asyncio.run(main())
