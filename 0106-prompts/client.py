"""0106 · 列出并渲染三个 Prompt。

运行：uv run python client.py
"""

import asyncio

from fastmcp import Client
from server import mcp


async def main() -> None:
    async with Client(mcp) as client:
        prompts = await client.list_prompts()
        for prompt in prompts:
            print(f"\nPrompt：{prompt.name}")
            print(f"  描述：{prompt.description}")
            print(f"  参数：{[(arg.name, arg.required) for arg in prompt.arguments or []]}")

        print("\n" + "=" * 60)
        result = await client.get_prompt("explain", {"topic": "MCP 的 stdio 传输"})
        print(f"explain → {result.messages[0].role}: {result.messages[0].content.text}")

        result = await client.get_prompt(
            "code_review", {"code": "def div(a, b):\n    return a / b", "language": "python"}
        )
        for message in result.messages:
            print(f"\ncode_review → {message.role}: {message.content.text[:80]}...")

        result = await client.get_prompt("summarize", {"text": "FastMCP 让 MCP 服务器开发变得简单。", "max_words": 30})
        print(f"\nsummarize → meta={result.meta}")
        print(f"  {result.messages[0].content.text}")


if __name__ == "__main__":
    asyncio.run(main())
