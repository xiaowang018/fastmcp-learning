"""0108 · 同一个服务器，三种连接方式。

- 进程内：Client(mcp)，最快，适合测试。
- stdio：Client(Path("server.py"))，宿主最常用的本地形态。
- HTTP：先起服务，再 Client("http://127.0.0.1:端口/mcp")，适合远程与多客户端。

另外演示 4.x 的协议协商：mode="auto"（默认）与 mode="legacy"。
"""

import os
import sys

from fastmcp import Context, FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

mcp = FastMCP(
    name="TransportDemo",
    instructions="演示 in-memory / stdio / HTTP 三种连接方式与协议协商。",
)


@mcp.tool
def ping() -> str:
    """返回 pong，用来确认连接可用。"""
    return "pong"


@mcp.tool
async def state_demo(value: str, ctx: Context = None) -> dict:
    """观察不同连接方式下的 session_id 与请求内状态。"""
    before = await ctx.get_state("value")
    await ctx.set_state("value", value)
    return {
        "before": before,
        "after": await ctx.get_state("value"),
        "session_id": ctx.session_id,
    }


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    """手动跑 HTTP 模式时的健康检查端点。"""
    return JSONResponse({"status": "ok"})


if __name__ == "__main__":
    if "--http" in sys.argv:
        # 手动验证：uv run python server.py --http
        mcp.run(
            transport="http",
            host="127.0.0.1",
            port=int(os.environ.get("PORT", "8108")),
        )
    else:
        # 默认 stdio：Client(Path(...)) 和宿主都走这里
        mcp.run()
