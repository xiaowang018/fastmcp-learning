"""0302 · 把 REST API 包装成 MCP 工具。

三个关键点：
1. httpx2 客户端放 lifespan，复用连接。
2. 超时 / 连接失败 / 4xx / 5xx 统一翻译成 ToolError，文案给模型看。
3. 重试只针对瞬时错误，业务错误不重试。
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx2
from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

TIMEOUT = 2.0


def api_base() -> str:
    """调用时读取，便于测试里切换到临时 mock 服务。"""
    return os.environ.get("WEATHER_API", "http://127.0.0.1:8107")


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict]:
    client = httpx2.AsyncClient(timeout=TIMEOUT)
    try:
        yield {"client": client}
    finally:
        await client.aclose()


mcp = FastMCP(
    name="WeatherMCP",
    instructions="把本地 mock 天气 API 包装成 MCP 工具，演示超时、重试与错误映射。",
    lifespan=lifespan,
)


async def get_json(ctx: Context, path: str, params: dict | None = None) -> dict:
    """带一次重试的 GET；所有异常统一翻译成 ToolError。"""
    client: httpx2.AsyncClient = ctx.lifespan_context["client"]
    url = api_base() + path
    last_error: Exception | None = None

    for attempt in range(2):
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx2.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 404:
                raise ToolError(f"上游没有这个资源：{exc.response.json().get('detail', path)}") from exc
            if status >= 500:
                raise ToolError(f"上游服务错误（{status}），请稍后重试或联系管理员") from exc
            raise ToolError(f"上游拒绝了请求（{status}）") from exc
        except (httpx2.TimeoutException, httpx2.ConnectError) as exc:
            last_error = exc
            if attempt == 0:
                continue
            raise ToolError("天气服务暂时不可达（已重试 1 次），请稍后再试") from exc

    raise ToolError(f"天气服务调用失败：{last_error}")


@mcp.tool
async def current_weather(city: str, ctx: Context) -> dict:
    """查询城市当前天气。

    Args:
        city: 城市名，例如 北京 / 上海 / 深圳。
    """
    return await get_json(ctx, "/weather", {"city": city})


@mcp.tool
async def forecast(city: str, days: int = 3, ctx: Context = None) -> dict:
    """查询未来几天的温度；days 限制在 1-7。"""
    if not 1 <= days <= 7:
        raise ToolError("days 必须在 1-7 之间")
    return await get_json(ctx, "/forecast", {"city": city, "days": days})


@mcp.tool
async def debug_upstream_error(ctx: Context) -> dict:
    """故意调用上游的 /boom，用来观察 5xx 如何映射成 ToolError。"""
    return await get_json(ctx, "/boom")


@mcp.tool
async def upstream_health(ctx: Context) -> dict:
    """探测上游是否可用；失败时返回结构化状态而不是抛错。"""
    try:
        await get_json(ctx, "/weather", {"city": "北京"})
    except ToolError as exc:
        return {"healthy": False, "reason": str(exc)}
    return {"healthy": True}


if __name__ == "__main__":
    mcp.run()
