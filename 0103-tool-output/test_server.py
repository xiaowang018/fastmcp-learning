"""0103 · 锁住返回类型到 content / structuredContent 的映射。"""

from fastmcp import Client

from helpers import load_server

SERVER = load_server("0103-tool-output")


async def test_pydantic_returns_structured_content() -> None:
    async with Client(SERVER.mcp) as client:
        result = await client.call_tool("analyze", {"text": "hello fastmcp world"})

    assert result.data.words == 3
    assert result.structured_content is not None
    assert result.structured_content["words"] == 3
    assert result.content[0].type == "text"


async def test_int_is_wrapped_only_with_annotation() -> None:
    async with Client(SERVER.mcp) as client:
        result = await client.call_tool("word_count", {"text": "a b c"})

    assert result.data == 3
    assert result.structured_content == {"result": 3}


async def test_tool_result_controls_meta() -> None:
    async with Client(SERVER.mcp) as client:
        result = await client.call_tool("analyze_verbose", {"text": "a b"})

    assert result.data == {"words": 2, "chars": 3}
    assert result.meta["analyzer"] == "rule-based"
    assert "2 个词" in result.content[0].text


async def test_image_content_block() -> None:
    async with Client(SERVER.mcp) as client:
        result = await client.call_tool("badge", {"text": "ok"})

    assert result.content[0].type == "image"
    assert result.content[0].mime_type == "image/png"
    assert result.data is None
