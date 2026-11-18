"""0201 · ASGI 入口：给 HTTP 服务加 CORS，交给 uvicorn 跑。

运行：uv run uvicorn app:app --host 127.0.0.1 --port 8101
"""

from server import mcp
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境改成具体来源
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=[
            "mcp-protocol-version",
            "mcp-session-id",
            "Authorization",
            "Content-Type",
        ],
        expose_headers=["mcp-session-id"],
    )
]

app = mcp.http_app(path="/mcp", middleware=middleware)
