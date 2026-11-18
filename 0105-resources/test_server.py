"""0105 · 资源读取与路径安全。"""

import json

import pytest
from fastmcp import Client

from helpers import load_server

SERVER = load_server("0105-resources")


async def test_list_shows_resources_and_templates() -> None:
    async with Client(SERVER.mcp) as client:
        resources = {str(item.uri) for item in await client.list_resources()}
        templates = {item.uri_template for item in await client.list_resource_templates()}

    assert "docs://guide" in resources
    assert "report://summary" in resources
    assert "docs://{filename}" in templates
    assert "files://{path*}" in templates


async def test_static_resource() -> None:
    async with Client(SERVER.mcp) as client:
        content = await client.read_resource("docs://guide")
    assert "资源使用指南" in content[0].text


async def test_template_reads_markdown_from_disk() -> None:
    async with Client(SERVER.mcp) as client:
        content = await client.read_resource("docs://intro")
    assert content[0].text.startswith("# 资源示例")


async def test_wildcard_reads_nested_path() -> None:
    async with Client(SERVER.mcp) as client:
        content = await client.read_resource("files://advanced/tips")
    assert "进阶技巧" in content[0].text


async def test_query_parameters() -> None:
    async with Client(SERVER.mcp) as client:
        content = await client.read_resource("items://catalog?limit=1&tag=mcp")
    payload = json.loads(content[0].text)
    assert payload["total"] == 2
    assert len(payload["items"]) == 1
    assert payload["items"][0]["tag"] == "mcp"


async def test_multiple_contents() -> None:
    async with Client(SERVER.mcp) as client:
        content = await client.read_resource("report://summary")
    assert len(content) == 2
    assert content[0].mime_type == "text/markdown"
    assert content[1].mime_type == "application/json"


async def test_path_traversal_is_rejected() -> None:
    async with Client(SERVER.mcp) as client:
        with pytest.raises(Exception) as info:
            await client.read_resource("files://../secret")
    # 服务端是 ResourceError，客户端经过协议层后看到的是 MCPError / ToolError 一类
    assert "not found" in str(info.value).lower()
