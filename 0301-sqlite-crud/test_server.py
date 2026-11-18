"""0301 · 每个测试用独立的临时数据库，覆盖 CRUD、分页、状态机与资源。"""

import pytest
from fastmcp import Client

from helpers import load_server

SERVER = load_server("0301-sqlite-crud")


@pytest.fixture(autouse=True)
def _temp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("TASK_DB", str(tmp_path / "test.db"))
    yield


async def test_create_and_list_pagination() -> None:
    async with Client(SERVER.mcp) as client:
        for index in range(3):
            await client.call_tool("create_task", {"title": f"任务 {index}", "priority": "normal"})

        page = await client.call_tool("list_tasks", {"limit": 2, "offset": 0})
        assert page.data["total"] == 3
        assert len(page.data["items"]) == 2

        second = await client.call_tool("list_tasks", {"limit": 2, "offset": 2})
        assert len(second.data["items"]) == 1


async def test_status_machine_rejects_skip() -> None:
    async with Client(SERVER.mcp) as client:
        task = await client.call_tool("create_task", {"title": "状态机"})
        task_id = task.data["id"]

        # todo → done 是跳步，必须拒绝
        skipped = await client.call_tool(
            "set_status", {"task_id": task_id, "status": "done"}, raise_on_error=False
        )
        assert skipped.is_error is True
        assert "不能从 todo 直接改为 done" in skipped.content[0].text

        # todo → doing 合法
        moved = await client.call_tool("set_status", {"task_id": task_id, "status": "doing"})
        assert moved.data["status"] == "doing"


async def test_delete_and_stats() -> None:
    async with Client(SERVER.mcp) as client:
        first = await client.call_tool("create_task", {"title": "A"})
        await client.call_tool("create_task", {"title": "B"})
        await client.call_tool("delete_task", {"task_id": first.data["id"]})

        stats = await client.call_tool("task_stats", {})
        assert stats.data.get("todo") == 1


async def test_resource_and_prompt() -> None:
    async with Client(SERVER.mcp) as client:
        await client.call_tool("create_task", {"title": "资源测试"})

        schema = await client.read_resource("db://schema")
        assert "CREATE TABLE" in schema[0].text

        todo = await client.read_resource("tasks://todo")
        assert "资源测试" in todo[0].text

        prompt = await client.get_prompt("daily_plan", {"status": "todo"})
        assert "tasks://todo" in prompt.messages[0].content.text


async def test_unknown_task_returns_tool_error() -> None:
    async with Client(SERVER.mcp) as client:
        result = await client.call_tool("delete_task", {"task_id": 999}, raise_on_error=False)
    assert result.is_error is True
    assert "不存在" in result.content[0].text
