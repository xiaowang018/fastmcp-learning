"""0102 · 打印三种签名的 JSON Schema，并演示参数校验失败。

运行：uv run python client.py
"""

import asyncio
import json

from fastmcp import Client
from fastmcp.exceptions import ToolError
from server import mcp


async def main() -> None:
    async with Client(mcp) as client:
        tools = await client.list_tools()

        for tool in tools:
            print(f"\n{'=' * 60}\n工具：{tool.name}\n描述：{tool.description}")
            print(json.dumps(tool.input_schema, ensure_ascii=False, indent=2))

        print(f"\n{'=' * 60}\n调用示例")
        basic = await client.call_tool("search_basic", {"query": "mcp"})
        print(f"search_basic → {basic.data}")

        annotated = await client.call_tool(
            "search_annotated", {"query": "mcp", "limit": 1, "sort": "newest"}
        )
        print(f"search_annotated → {annotated.data}")

        structured = await client.call_tool(
            "search_structured",
            {
                "request": {
                    "query": "mcp",
                    "tags": ["mcp"],
                    "date_range": {"start": "2026-10-01", "end": "2026-12-31"},
                    "limit": 2,
                }
            },
        )
        print(f"search_structured → {structured.data}")

        print(f"\n{'=' * 60}\n校验失败长什么样")
        try:
            await client.call_tool("search_annotated", {"query": "a"})
        except ToolError as exc:
            print(f"query 太短 → {exc}")


if __name__ == "__main__":
    asyncio.run(main())
