"""0301 · 走一遍完整业务：创建 → 流转 → 统计 → 删除。

运行：uv run python client.py
"""

import asyncio
import os
import tempfile
from pathlib import Path

from fastmcp import Client

# 每次运行用全新的临时库，保证 client.py 可以重复执行
os.environ["TASK_DB"] = str(Path(tempfile.mkdtemp(prefix="taskdb-")) / "demo.db")

from server import mcp  # noqa: E402


async def main() -> None:
    async with Client(mcp) as client:
        print("--- 建表语句 ---")
        schema = await client.read_resource("db://schema")
        print(schema[0].text.splitlines()[0], "...")

        print("\n--- 创建三张任务 ---")
        for title, priority in [("写周报", "high"), ("修 bug", "high"), ("看文档", "low")]:
            task = await client.call_tool("create_task", {"title": title, "priority": priority})
            print(f"  #{task.data['id']} {task.data['title']} [{task.data['priority']}]")

        print("\n--- 分页 ---")
        page = await client.call_tool("list_tasks", {"limit": 2, "offset": 0})
        print(f"  total={page.data['total']} items={[item['title'] for item in page.data['items']]}")

        print("\n--- 状态流转 ---")
        moved = await client.call_tool("set_status", {"task_id": 1, "status": "doing"})
        print(f"  #1 → {moved.data['status']}")
        bad = await client.call_tool("set_status", {"task_id": 2, "status": "done"}, raise_on_error=False)
        print(f"  跳步（todo→done）→ is_error={bad.is_error} {bad.content[0].text}")

        print("\n--- 统计 / 资源 / 提示 ---")
        print(f"  stats = {(await client.call_tool('task_stats', {})).data}")
        doing = await client.read_resource("tasks://doing")
        print(f"  tasks://doing = {doing[0].text}")
        prompt = await client.get_prompt("daily_plan", {"status": "doing"})
        print(f"  prompt = {prompt.messages[0].content.text}")

        print("\n--- 删除 ---")
        print(f"  delete #3 = {(await client.call_tool('delete_task', {'task_id': 3})).data}")


if __name__ == "__main__":
    asyncio.run(main())
