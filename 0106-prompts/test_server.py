"""0106 · Prompt 的三种返回形态与参数校验。"""

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from helpers import load_server

SERVER = load_server("0106-prompts")


async def test_list_prompts_with_arguments() -> None:
    async with Client(SERVER.mcp) as client:
        prompts = {prompt.name: prompt for prompt in await client.list_prompts()}

    assert set(prompts) == {"explain", "code_review", "summarize"}
    assert prompts["explain"].arguments[0].name == "topic"
    assert prompts["explain"].arguments[0].required is True
    assert prompts["code_review"].arguments[1].required is False


async def test_string_return_becomes_user_message() -> None:
    async with Client(SERVER.mcp) as client:
        result = await client.get_prompt("explain", {"topic": "resources"})
    assert len(result.messages) == 1
    assert result.messages[0].role == "user"
    assert "resources" in result.messages[0].content.text


async def test_message_list_keeps_roles() -> None:
    async with Client(SERVER.mcp) as client:
        result = await client.get_prompt("code_review", {"code": "print(1)"})
    assert [message.role for message in result.messages] == ["user", "assistant"]


async def test_prompt_result_meta() -> None:
    async with Client(SERVER.mcp) as client:
        result = await client.get_prompt("summarize", {"text": "你好", "max_words": 50})
    assert result.meta["template"] == "summarize"
    assert result.meta["max_words"] == 50
    assert "50" in result.messages[0].content.text


async def test_argument_validation() -> None:
    async with Client(SERVER.mcp) as client:
        with pytest.raises((ToolError, Exception)) as info:
            await client.get_prompt("summarize", {"text": "你好", "max_words": 5})
    assert "greater than or equal to 20" in str(info.value) or "validation" in str(info.value).lower()
