"""全仓共享测试工具（由 pytest 的 pythonpath = ["."] 暴露给各案例测试）。

四个约定：
1. 数字开头的案例目录不能 import，统一用 load_server() 按绝对路径加载。
2. 需要真实 stdio 通路的测试，直接 Client(Path(case) / "server.py")。
3. HTTP 测试用 free_port() 取空闲端口，再用 wait_healthy() 轮询 /health。
4. 子进程统一 UTF-8，避免 Windows cp936 造成中文乱码。
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib.util
import os
import socket
import sys
import time
from collections.abc import AsyncIterator
from pathlib import Path
from types import ModuleType
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent

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


def free_port() -> int:
    """取一个当前空闲的本地端口（仅用于串行测试，仍有极小竞态）。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_healthy(url: str, timeout: float = 10.0, interval: float = 0.1) -> None:
    """轮询一个 HTTP 端点，直到返回 200；禁止用 sleep 猜启动时间。"""
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except Exception as exc:  # 服务未起、连接被拒都属正常
            last_error = exc
        time.sleep(interval)
    raise TimeoutError(f"服务未在 {timeout}s 内就绪：{url}（最后一次错误：{last_error}）")


async def wait_healthy_async(url: str, timeout: float = 10.0, interval: float = 0.1) -> None:
    """wait_healthy 的异步版本：在事件循环里不能调用同步 urlopen，否则会阻塞服务。"""
    import httpx2

    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    async with httpx2.AsyncClient() as client:
        while time.monotonic() < deadline:
            try:
                response = await client.get(url, timeout=1)
                if response.status_code == 200:
                    return
            except Exception as exc:
                last_error = exc
            await asyncio.sleep(interval)
    raise TimeoutError(f"服务未在 {timeout}s 内就绪：{url}（最后一次错误：{last_error}）")


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
