"""0101 · 两条测试覆盖两种连接方式：进程内 + 真实 stdio 子进程。"""

from pathlib import Path

from fastmcp import Client

from helpers import load_server

CASE_DIR = Path(__file__).parent
SERVER = load_server("0101-hello-mcp")


async def test_in_memory_call() -> None:
    async with Client(SERVER.mcp) as client:
        tools = await client.list_tools()
        assert [tool.name for tool in tools] == ["add"]

        result = await client.call_tool("add", {"a": 2, "b": 3})
        assert result.data == 5
        # -> int 会自动包成 {"result": 5}，这是结构化输出的一部分
        assert result.structured_content == {"result": 5}


async def test_resource_read() -> None:
    async with Client(SERVER.mcp) as client:
        resource = await client.read_resource("info://server")
        assert "HelloMCP" in resource[0].text


async def test_stdio_subprocess() -> None:
    """验证宿主真正使用的通路：客户端拉起 python server.py，通过 stdin/stdout 通信。"""
    async with Client(CASE_DIR / "server.py", timeout=20) as client:
        assert client.protocol_version is not None
        result = await client.call_tool("add", {"a": 40, "b": 2})
        assert result.data == 42
