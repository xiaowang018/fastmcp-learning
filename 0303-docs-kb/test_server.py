"""0303 · 检索质量、资源读取、路径安全与提示模板。"""

import json

import pytest
from fastmcp import Client

from helpers import load_server

SERVER = load_server("0303-docs-kb")


async def test_index_lists_all_docs() -> None:
    async with Client(SERVER.mcp) as client:
        content = await client.read_resource("kb://index")
    index = json.loads(content[0].text)
    assert {item["name"] for item in index} == {
        "tool-design",
        "resource-vs-prompt",
        "transports",
        "security",
    }


async def test_search_returns_ranked_hits_with_sources() -> None:
    async with Client(SERVER.mcp) as client:
        result = await client.call_tool("search", {"query": "工具 设计", "limit": 2})

    hits = result.data["hits"]
    assert hits
    assert hits[0]["source"].startswith("kb://")
    assert hits[0]["score"] >= hits[-1]["score"]


async def test_search_rejects_bad_limit() -> None:
    async with Client(SERVER.mcp) as client:
        result = await client.call_tool("search", {"query": "工具", "limit": 9}, raise_on_error=False)
    assert result.is_error is True
    assert "1-5" in result.content[0].text


async def test_read_doc_and_traversal() -> None:
    async with Client(SERVER.mcp) as client:
        content = await client.read_resource("kb://security")
        assert "安全清单" in content[0].text

        with pytest.raises(Exception) as info:
            await client.read_resource("kb://../server")
    assert "not found" in str(info.value).lower()


async def test_prompt_requires_citations() -> None:
    async with Client(SERVER.mcp) as client:
        prompt = await client.get_prompt("answer_with_citations", {"question": "工具怎么设计？"})
    text = prompt.messages[0].content.text
    assert "search" in text
    assert "出处" in text
