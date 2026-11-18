"""0109 · 客户端进阶：把 MCP 的能力完整用一遍。

覆盖 list/call/read/get_prompt、错误分支、ClientGroup 聚合两个服务器，
最后写一个 20 行的「最小 Host」：发现工具 → 按计划调用 → 汇总结果。
"""

import json
from typing import Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

mcp = FastMCP(
    name="TicketServer",
    instructions="一个内存版工单服务，用来演示客户端的完整调用面。",
)

TICKETS: list[dict] = []


@mcp.tool
def create_ticket(
    title: str,
    priority: Literal["low", "normal", "high"] = "normal",
) -> dict:
    """创建一张工单。

    Args:
        title: 工单标题。
        priority: 优先级。
    """
    if not title.strip():
        raise ToolError("title 不能为空")
    ticket = {"id": len(TICKETS) + 1, "title": title, "priority": priority}
    TICKETS.append(ticket)
    return ticket


@mcp.tool
def list_tickets(priority: Literal["low", "normal", "high"] | None = None) -> list[dict]:
    """列出工单，可按优先级过滤。"""
    if priority is None:
        return list(TICKETS)
    return [ticket for ticket in TICKETS if ticket["priority"] == priority]


@mcp.tool
def close_ticket(ticket_id: int) -> dict:
    """关闭工单；不存在时返回业务错误。"""
    for ticket in TICKETS:
        if ticket["id"] == ticket_id:
            ticket["closed"] = True
            return ticket
    raise ToolError(f"工单 {ticket_id} 不存在")


@mcp.resource("tickets://all", mime_type="application/json")
def all_tickets() -> str:
    """以 JSON 形式暴露全部工单。"""
    return json.dumps(TICKETS, ensure_ascii=False)


@mcp.prompt
def triage(ticket_id: int) -> str:
    """生成一段工单分诊指令。"""
    return f"请阅读工单 {ticket_id}，判断它应该交给前端、后端还是运维，并说明理由。"


if __name__ == "__main__":
    mcp.run()
