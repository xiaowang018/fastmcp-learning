"""全仓共享测试工具（由 pytest 的 pythonpath = ["."] 暴露给各案例测试）。

三个约定：
1. 数字开头的案例目录不能 import，统一用 load_server() 按绝对路径加载。
2. 需要真实 stdio 通路的测试，直接 Client(Path(case) / "server.py")。
3. HTTP 测试用 serve_http / serve_asgi，绑 port=0 由操作系统分配端口。
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib.util
import os
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent

# Windows 控制台默认 cp936，会让中文断言和 print 出错；子进程统一 UTF-8。
SUBPROCESS_ENV = {
    **os.environ,
    "PYTHONUTF8": "1",
    "PYTHONIOENCODING": "utf-8",
    "PYTHONUNBUFFERED": "1",
}


def load_server(case: str, filename: str = "server.py") -> ModuleType:
    """加载 <case>/<filename> 并返回模块对象。

    用法：
        server = load_server("0101-hello-mcp")
        math = load_server("0109-client-advanced", "math_server.py")
    """
    path = ROOT / case / filename
    if not path.is_file():
        raise FileNotFoundError(f"找不到案例服务端：{path}")

    module_name = "case_" + case.replace("-", "_") + "_" + path.stem
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:  # pragma: no cover - 理论不可达
        raise ImportError(f"无法加载 {path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module

    # 案例目录加入 sys.path，让 server.py 里的 `from sibling import ...` 可用。
    case_dir = str(path.parent)
    added = case_dir not in sys.path
    if added:
        sys.path.insert(0, case_dir)
    try:
        spec.loader.exec_module(module)
    finally:
        if added:
            with contextlib.suppress(ValueError):
                sys.path.remove(case_dir)
    return module


@contextlib.asynccontextmanager
async def serve_asgi(app, path: str = "") -> AsyncIterator[str]:
    """在后台用 uvicorn 起任意 ASGI 应用，返回基地址（可带路径前缀）。"""
    import uvicorn

    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())

    while not server.started:
        if task.done():
            task.result()  # 把启动异常抛出来
        await asyncio.sleep(0.02)

    sockets = server.servers[0].sockets
    port = sockets[0].getsockname()[1]

    try:
        yield f"http://127.0.0.1:{port}{path}"
    finally:
        server.should_exit = True
        await task


@contextlib.asynccontextmanager
async def serve_http(mcp, path: str = "/mcp", **app_kwargs) -> AsyncIterator[str]:
    """在后台用 uvicorn 起一个 FastMCP HTTP 服务，返回可连接的 URL。

    绑定 port=0，由操作系统分配空闲端口，避免测试之间抢端口。
    app_kwargs 会透传给 mcp.http_app()，例如 stateless_http=True。
    """
    app = mcp.http_app(path=path, **app_kwargs)
    async with serve_asgi(app) as base:
        yield base + path
