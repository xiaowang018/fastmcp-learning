"""0108 · 三种连接方式都能跑通，且协议协商符合预期。"""

from pathlib import Path

from fastmcp import Client

from helpers import load_server, serve_http

CASE_DIR = Path(__file__).parent
SERVER = load_server("0108-client-transports")


async def test_in_memory() -> None:
    async with Client(SERVER.mcp) as client:
        assert (await client.call_tool("ping", {})).data == "pong"
        assert client.protocol_version is not None


async def test_stdio_subprocess() -> None:
    async with Client(CASE_DIR / "server.py", timeout=20) as client:
        assert (await client.call_tool("ping", {})).data == "pong"


async def test_http_auto_and_legacy() -> None:
    async with serve_http(SERVER.mcp) as url:
        async with Client(url) as client:
            assert (await client.call_tool("ping", {})).data == "pong"
            modern = client.protocol_version

        async with Client(url, mode="legacy") as client:
            assert (await client.call_tool("ping", {})).data == "pong"
            legacy = client.protocol_version

    assert modern != legacy


async def test_state_does_not_cross_calls() -> None:
    async with serve_http(SERVER.mcp) as url:
        async with Client(url) as client:
            first = await client.call_tool("state_demo", {"value": "A"})
            second = await client.call_tool("state_demo", {"value": "B"})

    assert first.data["after"] == "A"
    assert second.data["before"] is None
    assert first.data["session_id"] != second.data["session_id"]
