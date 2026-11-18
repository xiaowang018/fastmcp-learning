"""0203 · 中间件：把横切逻辑从工具里拿出来。

三个中间件按顺序执行：
1. AuditMiddleware   记录每次调用（谁、调了什么、参数是什么）。
2. QuotaMiddleware   只对 add 限次，超过后返回业务错误。
3. ResponseLimiting  限制响应体积，超长自动截断。

内置的 TimingMiddleware 只负责打日志，用来观察每个请求耗时。
"""

import asyncio
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.server.middleware.response_limiting import ResponseLimitingMiddleware
from fastmcp.server.middleware.timing import TimingMiddleware

AUDIT: list[dict[str, Any]] = []
QUOTA = {"used": 0, "limit": 2}


class AuditMiddleware(Middleware):
    """记录所有工具调用；生产环境可替换成写日志/打点。"""

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        message = context.message
        AUDIT.append({"tool": message.name, "arguments": message.arguments})
        print(f"[audit] {message.name} {message.arguments}")
        return await call_next(context)


class QuotaMiddleware(Middleware):
    """只对 add 做配额限制，演示「按工具名分流」。"""

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        if context.message.name == "add":
            if QUOTA["used"] >= QUOTA["limit"]:
                raise ToolError(f"配额用尽：add 最多调用 {QUOTA['limit']} 次")
            QUOTA["used"] += 1
        return await call_next(context)


mcp = FastMCP(
    name="MiddlewareDemo",
    instructions="演示自定义中间件、内置限流/截断/计时，以及执行顺序。",
)

mcp.add_middleware(AuditMiddleware())
mcp.add_middleware(QuotaMiddleware())
mcp.add_middleware(TimingMiddleware())
mcp.add_middleware(ResponseLimitingMiddleware(max_size=300))


@mcp.tool
def add(a: int, b: int) -> int:
    """把两个整数相加（受配额限制）。"""
    return a + b


@mcp.tool
def big() -> str:
    """返回 200 个字符，用来观察响应截断。"""
    return "x" * 200


@mcp.tool
async def slow(seconds: float = 0.2) -> str:
    """睡一会，用来观察 TimingMiddleware 的日志。"""
    await asyncio.sleep(seconds)
    return f"slept {seconds}s"


def reset() -> None:
    """测试与 client.py 用来重置状态。"""
    AUDIT.clear()
    QUOTA.update({"used": 0, "limit": 2})


if __name__ == "__main__":
    mcp.run()
