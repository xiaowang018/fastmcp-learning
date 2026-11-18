"""0202 · 生命周期与依赖注入。

lifespan 负责「进程级资源」：连接池、HTTP 客户端、模型、缓存。
Depends 负责「每次调用注入的参数」：配置、当前用户、租户上下文。
两者都不应该出现在工具 schema 里。
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from fastmcp import Context, FastMCP
from fastmcp.dependencies import Depends


@dataclass
class Settings:
    """进程级配置，通常来自环境变量。"""

    region: str = "cn-north"
    max_rows: int = 100


def get_settings() -> Settings:
    """依赖注入工厂：每次调用都会执行，参数不会出现在 schema 里。"""
    return Settings()


@dataclass
class FakePool:
    """假装是一个数据库连接池。"""

    name: str
    in_use: int = 0
    closed: bool = False
    history: list[str] = field(default_factory=list)

    def acquire(self, user: str) -> str:
        self.in_use += 1
        self.history.append(f"acquire:{user}")
        return f"{self.name}#{self.in_use}"

    def release(self, user: str) -> None:
        self.in_use = max(0, self.in_use - 1)
        self.history.append(f"release:{user}")


STATE: dict = {"started": 0, "stopped": 0, "pool": None}


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """服务器启动时创建池，关闭时释放；即使工具有异常也会执行 finally。"""
    STATE["started"] += 1
    pool = FakePool(name=f"pool-{STATE['started']}")
    STATE["pool"] = pool
    try:
        yield {"pool": pool, "settings": Settings()}
    finally:
        pool.closed = True
        STATE["stopped"] += 1


mcp = FastMCP(
    name="LifespanDemo",
    instructions="演示 lifespan 管理进程级资源，以及 Depends 注入配置。",
    lifespan=app_lifespan,
)


@mcp.tool
def acquire(ctx: Context, user: str = "anonymous") -> dict:
    """从连接池借一个连接。"""
    pool: FakePool = ctx.lifespan_context["pool"]
    handle = pool.acquire(user)
    return {"handle": handle, "in_use": pool.in_use, "pool": pool.name}


@mcp.tool
def release(ctx: Context, user: str = "anonymous") -> dict:
    """归还连接。"""
    pool: FakePool = ctx.lifespan_context["pool"]
    pool.release(user)
    return {"in_use": pool.in_use, "history": pool.history[-4:]}


@mcp.tool
def pool_status(ctx: Context) -> dict:
    """查看池状态。连接池跨调用复用，这一点与 0107 的请求内状态不同。"""
    pool: FakePool = ctx.lifespan_context["pool"]
    return {
        "pool": pool.name,
        "in_use": pool.in_use,
        "closed": pool.closed,
        "calls": len(pool.history),
    }


@mcp.tool
def effective_settings(settings: Settings = Depends(get_settings)) -> dict:  # noqa: B008
    """Depends 注入的配置：schema 里看不到 settings 参数。"""
    return {"region": settings.region, "max_rows": settings.max_rows}


@mcp.tool
def crash(ctx: Context) -> str:
    """故意抛错，用来验证 lifespan 的清理仍会执行。"""
    pool: FakePool = ctx.lifespan_context["pool"]
    pool.history.append("crash")
    raise RuntimeError("模拟数据库断连")


if __name__ == "__main__":
    mcp.run()
