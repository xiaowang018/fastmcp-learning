"""0204 · 鉴权与授权：先证明你是谁，再决定你能看到什么。

StaticTokenVerifier 适合内网/原型：token 写死在配置里。
生产环境应换成 JWT / OAuth / OIDC（见 README 的升级路径）。
"""

from fastmcp import FastMCP
from fastmcp.server.auth import StaticTokenVerifier, require_scopes
from fastmcp.server.dependencies import get_access_token
from starlette.requests import Request
from starlette.responses import JSONResponse

# token -> 声明。client_id 是必填字段，缺少会直接 500。
auth = StaticTokenVerifier(
    tokens={
        "alice-token": {"sub": "alice", "client_id": "cli", "scopes": ["read", "write"]},
        "bob-token": {"sub": "bob", "client_id": "cli", "scopes": ["read"]},
    }
)

mcp = FastMCP(
    name="AuthDemo",
    instructions="演示 Bearer token 鉴权、scope 授权与工具可见性。",
    auth=auth,
)

DATA = {"items": ["alpha", "beta"]}


@mcp.tool
def whoami() -> dict:
    """返回当前 token 的身份与 scope。"""
    token = get_access_token()
    if token is None:
        return {"authenticated": False}
    return {
        "subject": token.subject,
        "client_id": token.client_id,
        "scopes": token.scopes,
    }


@mcp.tool
def read_data() -> dict:
    """读取数据：任何通过鉴权的调用方都能用。"""
    return DATA


@mcp.tool(auth=require_scopes("write"))
def write_data(item: str) -> dict:
    """写入数据：需要 write scope；没有 scope 的调用方连工具都看不到。"""
    DATA["items"].append(item)
    return {"items": DATA["items"]}


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    """健康检查不受 MCP 鉴权保护，供探针使用。"""
    return JSONResponse({"status": "ok"})


if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8104)
