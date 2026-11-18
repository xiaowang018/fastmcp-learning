"""0205 · 组合、namespace 消歧、代理子进程。"""

import json

from fastmcp import Client

from helpers import load_server

SERVER = load_server("0205-compose-proxy")


async def test_namespaced_tools_are_all_visible() -> None:
    async with Client(SERVER.mcp) as client:
        names = {tool.name for tool in await client.list_tools()}

    assert {"weather_get_weather", "calendar_get_weather", "calendar_add_event"} <= names
    assert "math_multiply" in names


async def test_same_name_tools_route_to_different_servers() -> None:
    async with Client(SERVER.mcp) as client:
        weather_result = await client.call_tool("weather_get_weather", {"city": "上海"})
        calendar_result = await client.call_tool("calendar_get_weather", {"date": "2026-11-15"})

    assert weather_result.data["temperature"] == 22
    assert calendar_result.data["meetings"] == 3


async def test_proxy_spawns_subprocess() -> None:
    async with Client(SERVER.mcp) as client:
        result = await client.call_tool("math_multiply", {"a": 6, "b": 7})
    assert result.data == 42


async def test_resources_and_prompts_are_namespaced() -> None:
    async with Client(SERVER.mcp) as client:
        resources = {str(item.uri) for item in await client.list_resources()}
        prompts = {item.name for item in await client.list_prompts()}
        content = await client.read_resource("weather://weather/cities")

    assert "weather://weather/cities" in resources
    assert "weather_weather_brief" in prompts
    assert "北京" in json.loads(content[0].text)
