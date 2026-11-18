"""0305 · 一个准备部署的最小服务器。

它同时演示三件事：
- 用 fastmcp.json 声明源码、环境与运行参数。
- 用 /health 做容器探针。
- 同一份代码可以被 install 到多个宿主。
"""

import os
from datetime import datetime

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from starlette.requests import Request
from starlette.responses import JSONResponse

mcp = FastMCP(
    name="DeployDemo",
    instructions="演示 fastmcp.json、CLI 安装与容器化部署。",
)


@mcp.tool
def server_time() -> str:
    """返回服务器当前时间（ISO 8601）。"""
    return datetime.now().isoformat(timespec="seconds")


@mcp.tool
def roll_dice(sides: int = 6) -> dict:
    """掷一个骰子；sides 限制在 2-100。"""
    if not 2 <= sides <= 100:
        raise ToolError("sides 必须在 2-100 之间")
    import random

    return {"sides": sides, "value": random.randint(1, sides)}


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    """容器/负载均衡探针。"""
    return JSONResponse({"status": "ok", "version": os.environ.get("APP_VERSION", "dev")})


if __name__ == "__main__":
    mcp.run()
