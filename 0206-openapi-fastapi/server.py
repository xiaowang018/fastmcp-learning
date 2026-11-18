"""0206 · 两种生成方式。

1. mcp：默认把所有端点转成工具（适合快速验证）。
2. read_mcp：用 RouteMap 把 GET 转成资源/模板，其余排除（适合「读多写少」的 API）。
"""

from api import app
from fastmcp import FastMCP
from fastmcp.server.providers.openapi import MCPType, RouteMap

# 默认：所有端点 → 工具，工具名取 operation_id
mcp = FastMCP.from_fastapi(app=app, name="ShopMCP")

# 自定义映射：GET 带路径参数 → 资源模板，GET → 资源，其余排除
read_mcp = FastMCP.from_fastapi(
    app=app,
    name="ShopReadOnly",
    route_maps=[
        RouteMap(methods=["GET"], pattern=r".*\{.*\}.*", mcp_type=MCPType.RESOURCE_TEMPLATE),
        RouteMap(methods=["GET"], pattern=r".*", mcp_type=MCPType.RESOURCE),
        RouteMap(mcp_type=MCPType.EXCLUDE),
    ],
)


if __name__ == "__main__":
    mcp.run()
