"""0103 · 对比四种返回类型在客户端侧的差异。

运行：uv run python client.py
"""

import asyncio

from fastmcp import Client
from server import mcp


def show(label: str, result) -> None:
    print(f"\n{label}")
    print(f"  data               = {result.data!r}")
    print(f"  structured_content = {result.structured_content!r}")
    print(f"  content blocks     = {[(block.type, getattr(block, 'mime_type', None)) for block in result.content]}")
    print(f"  meta               = {result.meta!r}")


async def main() -> None:
    async with Client(mcp) as client:
        show("analyze（Pydantic 模型）", await client.call_tool("analyze", {"text": "hello fastmcp world"}))
        print("  注意：data 是重新校验后的模型对象，用 data.words 访问；原始字典看 structured_content")
        show("word_count（int）", await client.call_tool("word_count", {"text": "hello fastmcp world"}))
        show("analyze_verbose（ToolResult）", await client.call_tool("analyze_verbose", {"text": "hello fastmcp"}))
        image = await client.call_tool("badge", {"text": "ok"})
        print("\nbadge（Image）")
        print(f"  content blocks     = {[(block.type, getattr(block, 'mime_type', None)) for block in image.content]}")
        print(f"  base64 长度        = {len(image.content[0].data)}")


if __name__ == "__main__":
    asyncio.run(main())
