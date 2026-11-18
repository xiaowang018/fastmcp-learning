"""0107 · Context 的进度、资源读取、请求内状态与日志。"""

from fastmcp import Client

from helpers import load_server

SERVER = load_server("0107-context")


async def test_progress_and_resource_read() -> None:
    events: list[tuple[float, float | None, str | None]] = []

    async def on_progress(progress: float, total: float | None, message: str | None) -> None:
        events.append((progress, total, message))

    async with Client(SERVER.mcp, progress_handler=on_progress) as client:
        result = await client.call_tool("summarize", {"text": "hello world"})

    assert result.data["chars"] == 11
    assert "80 字" in result.data["rule"]
    assert [(p, t) for p, t, _ in events] == [(0.0, 2.0), (1.0, 2.0), (2.0, 2.0)]


async def test_state_is_request_scoped() -> None:
    async with Client(SERVER.mcp) as client:
        first = await client.call_tool("state_demo", {"value": "A"})
        second = await client.call_tool("state_demo", {"value": "B"})

    assert first.data["before"] is None
    assert first.data["after"] == "A"
    assert second.data["before"] is None  # 跨调用不保留
    assert second.data["after"] == "B"
    assert first.data["session_id"] != second.data["session_id"]


async def test_logging_callback() -> None:
    logs: list[str] = []

    async def on_log(message) -> None:
        logs.append(message.level)

    async with Client(SERVER.mcp, log_handler=on_log) as client:
        await client.call_tool("logging_demo", {"message": "hi"})

    assert "info" in logs
    assert "warning" in logs
