"""0302 · 正常、404、5xx、不可达四类上游行为。"""

import pytest

pytest.importorskip("fastapi", reason="mock API 需要 uv sync --group api")

from fastmcp import Client  # noqa: E402

from helpers import load_server, serve_asgi  # noqa: E402

SERVER = load_server("0302-rest-api-wrapper")
MOCK = load_server("0302-rest-api-wrapper", "mock_api.py")


@pytest.fixture
async def api_url(monkeypatch):
    async with serve_asgi(MOCK.app) as url:
        monkeypatch.setenv("WEATHER_API", url)
        yield url


async def test_current_weather(api_url) -> None:
    async with Client(SERVER.mcp) as client:
        result = await client.call_tool("current_weather", {"city": "深圳"})
    assert result.data["temperature"] == 27


async def test_404_becomes_actionable_tool_error(api_url) -> None:
    async with Client(SERVER.mcp) as client:
        result = await client.call_tool("current_weather", {"city": "杭州"}, raise_on_error=False)
    assert result.is_error is True
    assert "未收录城市：杭州" in result.content[0].text


async def test_500_is_mapped(api_url) -> None:
    async with Client(SERVER.mcp) as client:
        result = await client.call_tool("debug_upstream_error", {}, raise_on_error=False)
    assert result.is_error is True
    assert "上游服务错误（500）" in result.content[0].text


async def test_unreachable_is_mapped(monkeypatch) -> None:
    monkeypatch.setenv("WEATHER_API", "http://127.0.0.1:9")
    async with Client(SERVER.mcp) as client:
        result = await client.call_tool("current_weather", {"city": "北京"}, raise_on_error=False)
    assert result.is_error is True
    assert "不可达" in result.content[0].text
