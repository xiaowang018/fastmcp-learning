"""0107 · 用异步回调接收进度与日志。

运行：uv run python client.py
"""

import asyncio

from fastmcp import Client
from server import mcp

progress_events: list[tuple[float, float | None, str | None]] = []
log_events: list[tuple[str, object]] = []


# 重要：这两个回调必须是 async def。返回 None 的同步函数会触发
# "object NoneType can't be used in 'await' expression"，而且只写进日志，很容易漏看。
async def on_progress(progress: float, total: float | None, message: str | None) -> None:
    progress_events.append((progress, total, message))
    print(f"  [progress] {progress}/{total} {message}")


async def on_log(message) -> None:
    log_events.append((message.level, message.data))
    print(f"  [log:{message.level}] {message.data}")


async def main() -> None:
    async with Client(mcp, progress_handler=on_progress, log_handler=on_log) as client:
        print("--- summarize：读资源 + 进度 ---")
        result = await client.call_tool("summarize", {"text": "FastMCP 4.2 让 MCP 开发更简单。"})
        print(f"  rule = {result.data['rule']}")
        print(f"  chars = {result.data['chars']}")

        print("\n--- long_task：3 步进度 ---")
        result = await client.call_tool("long_task", {"steps": 3})
        print(f"  {result.data}")

        print("\n--- state_demo：同一会话里的两次调用 ---")
        first = await client.call_tool("state_demo", {"value": "draft-A"})
        second = await client.call_tool("state_demo", {"value": "draft-B"})
        print(f"  第一次：{first.data}")
        print(f"  第二次：{second.data}")
        print("  结论：同一次调用内 set/get 有效；跨调用 before 仍是 None，session_id 也变了。")

        print("\n--- logging_demo：日志通知 + stderr ---")
        await client.call_tool("logging_demo", {"message": "hello"})

        print(f"\n共收到 {len(progress_events)} 条进度、{len(log_events)} 条日志")


if __name__ == "__main__":
    asyncio.run(main())
