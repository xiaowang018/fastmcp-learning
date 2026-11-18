"""0303 · 检索、读原文、生成带引用的回答模板。

运行：uv run python client.py
"""

import asyncio
import json

from fastmcp import Client
from server import mcp


async def main() -> None:
    async with Client(mcp) as client:
        index = await client.read_resource("kb://index")
        print("--- 知识库目录 ---")
        for item in json.loads(index[0].text):
            print(f"  {item['name']}: {item['title']} ({item['chars']} 字)")

        for query in ("工具设计", "路径穿越", "stdio 传输"):
            result = await client.call_tool("search", {"query": query, "limit": 2})
            print(f"\n--- search({query!r}) ---")
            for hit in result.data["hits"]:
                print(f"  [{hit['score']}] {hit['title']} → {hit['source']}")
                print(f"      {hit['snippet']}")

        print("\n--- 读原文 kb://security ---")
        content = await client.read_resource("kb://security")
        print(content[0].text.splitlines()[0])

        print("\n--- 回答模板 ---")
        prompt = await client.get_prompt("answer_with_citations", {"question": "如何做资源路径安全？"})
        print(prompt.messages[0].content.text)


if __name__ == "__main__":
    asyncio.run(main())
