"""0304 · 两条路径：装了 apps 组验证 Prefab UI，没装则只验证 HTML 降级。"""

import httpx2
import pytest
from fastmcp import Client

from helpers import load_server, serve_http

SERVER = load_server("0304-apps-ui")


async def test_metrics_tool() -> None:
    async with Client(SERVER.mcp) as client:
        result = await client.call_tool("get_metrics", {})
    assert result.data["services"] == 3
    assert result.data["slowest"] == "worker"


async def test_html_fallback_route() -> None:
    async with serve_http(SERVER.mcp) as url:
        async with httpx2.AsyncClient(timeout=5) as client:
            response = await client.get(url.removesuffix("/mcp") + "/dashboard")
    assert response.status_code == 200
    assert "<table>" in response.text
    assert "服务指标" in response.text


@pytest.mark.apps
async def test_prefab_app_tool() -> None:
    pytest.importorskip("prefab_ui", reason="需要 uv sync --group apps")
    assert SERVER.HAS_PREFAB is True

    async with Client(SERVER.mcp) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}
        assert "ui" in (tools["dashboard"].meta or {})

        result = await client.call_tool("dashboard", {})
    assert result.is_error is False
    assert result.data["$prefab"]["version"]
    assert result.data["view"]["type"] == "Div"
