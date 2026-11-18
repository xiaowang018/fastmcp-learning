"""0301 · SQLite 待办服务：把前面学的原语拼成一个完整项目。

设计要点：
- 连接与锁放在 lifespan，进程内复用。
- sqlite3 是阻塞库，所有查询走 asyncio.to_thread，避免卡住事件循环。
- 状态机（todo → doing → done）在服务端强制，错误用 ToolError 给出可操作文案。
- 读操作暴露成 Resource，模板资源按状态查询。
"""

import asyncio
import json
import os
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

Status = Literal["todo", "doing", "done"]
ALLOWED = {"todo": {"doing"}, "doing": {"done", "todo"}, "done": set()}


def db_path() -> Path:
    """每次连接时读取环境变量，方便测试隔离。"""
    return Path(os.environ.get("TASK_DB", str(Path(__file__).parent / "tasks.db")))


def init_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'todo',
            priority TEXT NOT NULL DEFAULT 'normal',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict]:
    conn = sqlite3.connect(db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    lock = asyncio.Lock()
    try:
        yield {"conn": conn, "lock": lock}
    finally:
        conn.close()


mcp = FastMCP(
    name="TaskDB",
    instructions="一个 SQLite 待办服务，演示工具/资源/提示/事务与错误处理的组合。",
    lifespan=lifespan,
)


async def query(ctx: Context, sql: str, params: tuple = ()) -> list[dict]:
    """在线程池里执行查询，并用锁串行化写操作。"""
    state = ctx.lifespan_context
    async with state["lock"]:
        return await asyncio.to_thread(_execute, state["conn"], sql, params)


def _execute(conn: sqlite3.Connection, sql: str, params: tuple) -> list[dict]:
    cursor = conn.execute(sql, params)
    if sql.lstrip().upper().startswith("SELECT"):
        return [dict(row) for row in cursor.fetchall()]
    conn.commit()
    return []


@mcp.tool
async def create_task(
    title: str,
    priority: Literal["low", "normal", "high"] = "normal",
    ctx: Context = None,
) -> dict:
    """创建待办任务。"""
    if not title.strip():
        raise ToolError("title 不能为空")
    await query(ctx, "INSERT INTO tasks(title, priority) VALUES (?, ?)", (title.strip(), priority))
    rows = await query(ctx, "SELECT * FROM tasks ORDER BY id DESC LIMIT 1")
    return rows[0]


@mcp.tool
async def list_tasks(
    status: Status | None = None,
    limit: int = 10,
    offset: int = 0,
    ctx: Context = None,
) -> dict:
    """分页列出任务，可按状态过滤。"""
    if not 1 <= limit <= 50:
        raise ToolError("limit 必须在 1-50 之间")
    where, params = ("WHERE status = ?", (status,)) if status else ("", ())
    total = (await query(ctx, f"SELECT COUNT(*) AS n FROM tasks {where}", params))[0]["n"]
    items = await query(
        ctx,
        f"SELECT * FROM tasks {where} ORDER BY id DESC LIMIT ? OFFSET ?",
        (*params, limit, offset),
    )
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@mcp.tool(annotations=ToolAnnotations(idempotentHint=True))
async def set_status(task_id: int, status: Status, ctx: Context = None) -> dict:
    """推进任务状态；非法流转会返回业务错误。"""
    rows = await query(ctx, "SELECT * FROM tasks WHERE id = ?", (task_id,))
    if not rows:
        raise ToolError(f"任务 {task_id} 不存在")
    current = rows[0]["status"]
    if status == current:
        return rows[0]
    if status not in ALLOWED[current]:
        raise ToolError(f"不能从 {current} 直接改为 {status}；允许：{sorted(ALLOWED[current]) or '无'}")
    await query(ctx, "UPDATE tasks SET status = ? WHERE id = ?", (status, task_id))
    return (await query(ctx, "SELECT * FROM tasks WHERE id = ?", (task_id,)))[0]


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
async def delete_task(task_id: int, ctx: Context = None) -> dict:
    """删除任务（不可恢复）。"""
    if not await query(ctx, "SELECT id FROM tasks WHERE id = ?", (task_id,)):
        raise ToolError(f"任务 {task_id} 不存在")
    await query(ctx, "DELETE FROM tasks WHERE id = ?", (task_id,))
    return {"deleted": task_id}


@mcp.tool
async def task_stats(ctx: Context = None) -> dict:
    """按状态统计任务数。"""
    rows = await query(ctx, "SELECT status, COUNT(*) AS n FROM tasks GROUP BY status")
    return {row["status"]: row["n"] for row in rows}


@mcp.resource("db://schema", mime_type="text/plain")
async def schema(ctx: Context) -> str:
    """暴露建表语句，方便客户端理解数据结构。"""
    rows = await query(ctx, "SELECT sql FROM sqlite_master WHERE type='table' AND name='tasks'")
    return rows[0]["sql"] if rows else "(no table)"


@mcp.resource("tasks://{status}", mime_type="application/json")
async def tasks_by_status(status: str, ctx: Context) -> str:
    """按状态读取任务列表。"""
    if status not in {"todo", "doing", "done"}:
        raise ToolError(f"未知状态：{status}")
    rows = await query(ctx, "SELECT * FROM tasks WHERE status = ? ORDER BY id", (status,))
    return json.dumps(rows, ensure_ascii=False)


@mcp.prompt
def daily_plan(status: Status = "todo") -> str:
    """生成一份今日计划指令。"""
    return (
        f"请读取 tasks://{status} 中的任务，按优先级排出一份今日计划；"
        "每项给出预计耗时，并标注依赖关系。"
    )


if __name__ == "__main__":
    mcp.run()
