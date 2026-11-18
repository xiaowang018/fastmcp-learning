"""0201 · 同一个服务器，从 stdio 切到 HTTP。

关键变化只有一行：mcp.run(transport="http", ...)。
其余工具/资源代码完全不用改，这正是 MCP 的价值：能力与传输解耦。
"""

import os

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

mcp = FastMCP(
    name="HttpDemo",
    instructions="演示 Streamable HTTP 传输、健康检查与 stateless 模式。",
)


@mcp.tool
def greet(name: str) -> str:
    """向指定名字打招呼。"""
    return f"你好，{name}！这条响应来自 HTTP 传输。"


@mcp.tool
def add(a: int, b: int) -> int:
    """把两个整数相加。"""
    return a + b


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    """健康检查：不经过 MCP 协议，也不受鉴权中间件保护。"""
    return JSONResponse({"status": "ok", "service": "HttpDemo"})


if __name__ == "__main__":
    mcp.run(
        transport="http",
        host="127.0.0.1",
        port=int(os.environ.get("PORT", "8101")),
    )
