# 0201 · 从 stdio 切到 HTTP：只改一行

> 目标：把 0101 的服务器原样搬到 HTTP 上，补齐健康检查、CORS 与 stateless 模式。
> 难度 ★★★ ｜ 前置：0108 ｜ 依赖：无 ｜ 端口：8101（手动）/ 随机（测试）｜ 预计：30 分钟

## 1. 你会学到

- `mcp.run(transport="http")` 与 `mcp.http_app()` 两条部署路径。
- 自定义 `/health` 路由、CORS 中间件、`stateless_http=True`。
- 为什么「同步 HTTP 请求」会把你自己起的服务卡死。
- HTTP 模式的 URL 结构与多副本部署注意点。

## 2. 先跑起来

```bash
cd 0201-http-server
uv run python client.py
```

预期输出：

```text
① 有状态 HTTP 服务（默认）
   MCP URL  = http://127.0.0.1:65040/mcp
   health   = {'status': 'ok', 'service': 'HttpDemo'}
   协议版本 = 2026-07-28
   greet    = 你好，MCP！这条响应来自 HTTP 传输。
   add      = 42

② stateless_http=True：不保留会话，适合多副本
   第 1 个连接：add = 2
   第 2 个连接：add = 3
```

```bash
uv run pytest . -q
# 3 passed
```

手动跑：

```bash
uv run python server.py                 # 端口 8101
# 或
uv run uvicorn app:app --host 127.0.0.1 --port 8101
curl http://127.0.0.1:8101/health
```

## 3. 代码地图

| 文件 | 作用 |
|---|---|
| `server.py` | 业务工具 + `/health` + `mcp.run(transport="http")` |
| `app.py` | ASGI 入口：CORS + `mcp.http_app()`，交给 uvicorn |
| `client.py` | 起临时服务、验证 health、调用工具、对比 stateless |
| `test_server.py` | 三条测试，全部使用随机端口 |

## 4. 两条部署路径

### 路径 A：`mcp.run()`

```python
mcp.run(transport="http", host="127.0.0.1", port=8101)
```

适合本地开发、单进程、内部工具。MCP 端点是 `http://host:port/mcp`。

### 路径 B：`mcp.http_app()`

```python
app = mcp.http_app(path="/mcp", middleware=[...])
# uvicorn app:app --port 8101
```

适合生产：多 worker、自定义中间件、挂到现有 FastAPI/Starlette（见 0206）。

两条路径**共用同一份工具代码**，切换成本只有启动方式。

## 5. 健康检查

```python
@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "HttpDemo"})
```

- Custom route **不经过 MCP 协议**，也不受 MCP 鉴权中间件保护（设计如此，用于探针）。
- 就绪判定请轮询 `/health`，不要 `sleep(3)` 猜启动时间。
- 需要鉴权的运维接口，挂到 FastAPI 上并用 `Depends()`。

## 6. CORS

浏览器里的 MCP 客户端需要三个关键头：

```python
allow_headers=["mcp-protocol-version", "mcp-session-id", "Authorization", "Content-Type"]
expose_headers=["mcp-session-id"]
```

`mcp-session-id` 必须 expose，否则前端 JS 读不到会话 ID。生产环境把 `allow_origins=["*"]` 换成具体域名。

## 7. stateless 模式

```python
app = mcp.http_app(stateless_http=True)
# 或 mcp.run(transport="http", stateless_http=True)
```

用途：多副本、无粘性会话的负载均衡。

- 每个请求自带全部上下文，任何副本都能处理；
- 不保留会话状态，`ctx.set_state` 跨请求无效（0107/0108 已见）；
- 多 worker 部署**必须**开 stateless，因为会话存在单实例内存里。

## 8. 三种验证方式

**client.py**：自动起临时端口，最省事。

**curl**：

```bash
PORT=8101 uv run python server.py &
curl -i http://127.0.0.1:8101/health
```

**Inspector**：Transport 选 `Streamable HTTP`，URL 填 `http://127.0.0.1:8101/mcp`。

## 9. 常见坑

**① 在同一个事件循环里用 `urllib` 请求自己**

本案例第一次实现就踩了这个坑：`uvicorn` 跑在当前事件循环里，`urllib.request.urlopen()` 是同步阻塞的，循环被卡住 → 请求永远等不到响应 → `TimeoutError`。

解决：用 `httpx2.AsyncClient`，或 `await asyncio.to_thread(...)`。

**② 以为 `/health` 也会走鉴权**

Custom route 永远不受 MCP 的 auth 中间件保护。别把敏感信息放进去。

**③ 多 worker 没开 stateless**

```text
现象：请求偶发 404 / session not found
原因：会话创建在 worker A，下一次请求被路由到 worker B
解决：stateless_http=True，或做粘性会话
```

**④ 端口写死**

手动运行固定 8101；测试用 `port=0`（`helpers.serve_http`），否则并行跑测试必冲突。

**⑤ 忘了 `mcp-session-id` 的 CORS expose**

浏览器端能连上但读不到会话，表现为「工具列表为空」。

## 10. 与 2.x / 3.x 的差异

- 4.x 默认 `transport="http"`（Streamable HTTP）；2.x 时代常用 SSE，`transport="sse"` 仍保留但属旧版。
- `stateless_http` 在 3.x 之后稳定；2.x 需要自行处理会话。
- `custom_route` 从 2.4 起支持，4.x 行为一致。
- 完整差异见 [`docs/03-compat.md`](../docs/03-compat.md)。

## 11. 练习

1. 把 `stateless_http=True` 与 `False` 各跑一次，用 `client.protocol_version` 和 `session_id` 记录差异。
2. 给 `app.py` 加一个 `GET /version` 路由，返回 FastMCP 版本（用 `importlib.metadata`）。
3. 用 `uv run uvicorn app:app --workers 4 --port 8101` 起 4 个 worker，观察不开 stateless 时的失败率。

## 12. 延伸阅读

- FastMCP HTTP 部署：<https://gofastmcp.com/docs/deployment/http>
- 运行服务器：<https://gofastmcp.com/docs/deployment/running-server>
- Starlette CORS：<https://www.starlette.io/middleware/>
