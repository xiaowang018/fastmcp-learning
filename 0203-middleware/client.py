"""0203 · 观察中间件的顺序、配额与响应截断。

运行：uv run python client.py
"""

import asyncio

from fastmcp import Client
from server import AUDIT, mcp, reset


async def main() -> None:
    reset()

    async with Client(mcp) as client:
        print("--- add 的配额是 2 次 ---")
        for index in range(3):
            result = await client.call_tool("add", {"a": index, "b": 1}, raise_on_error=False)
            print(f"  第 {index + 1} 次：is_error={result.is_error} data={result.data}")

        print("\n--- big：200 字符会被截断到 300 字节以内 ---")
        result = await client.call_tool("big", {}, raise_on_error=False)
        print(f"  长度={len(result.content[0].text)}")
        print(f"  结尾={result.content[0].text[-45:]!r}")

        print("\n--- slow：TimingMiddleware 会打日志 ---")
        result = await client.call_tool("slow", {"seconds": 0.1})
        print(f"  {result.data}")

    print(f"\n--- 审计记录（{len(AUDIT)} 条）---")
    for item in AUDIT:
        print(f"  {item['tool']} {item['arguments']}")


if __name__ == "__main__":
    asyncio.run(main())
