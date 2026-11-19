# 0302 · 实战：把 REST API 包装成 MCP 工具

> 目标：不依赖外网和密钥，用本地 mock API 走通「HTTP → MCP」的包装层，重点讲错误映射与重试。
> 难度 ★★★★ ｜ 前置：0202 0206（概念）｜ 依赖：api 组（推荐 `uv sync --all-groups`）｜ 端口：8107（mock，手动）｜ 预计：40 分钟

## 1. 你会学到

- `httpx2.AsyncClient` 放进 lifespan，复用连接、统一超时。
- 404 / 5xx / 连接失败 / 超时如何翻译成模型能理解的 `ToolError`。
- 重试只对瞬时错误生效，业务错误立即返回。
- 为什么「包装层」比「自动转换 OpenAPI」更适合生产。

## 2. 先跑起来

```bash
cd 0302-rest-api-wrapper
uv sync --group api
uv run python client.py
```

> `uv sync --group api` 会把环境精确同步成「默认 + api」，之前装的 `apps` 组会被移除。
> 想一次装齐：`uv sync --all-groups`（根 README §0.4 的推荐做法）。

预期输出：

```text
mock API = http://127.0.0.1:63743
current_weather(北京) = {'city': '北京', 'temperature': 18, 'condition': '晴', ...}
forecast(上海, 2)     = {'city': '上海', 'days': [{'day': 1, 'temperature': 22}, ...]}
未收录城市 → is_error=True 上游没有这个资源：未收录城市：杭州
upstream_health = {'healthy': True}
上游不可达 → is_error=True 天气服务暂时不可达（已重试 1 次），请稍后再试
```

```bash
uv run pytest . -q
# 4 passed
```

## 3. 代码地图

| 文件 | 作用 |
|---|---|
| `mock_api.py` | FastAPI 假天气服务：正常 / 404 / 500 / 慢响应 |
| `server.py` | MCP 包装层：lifespan 客户端、重试、错误映射 |
| `client.py` | 起 mock API，跑正常与两类失败 |
| `test_server.py` | 覆盖 200 / 404 / 500 / 不可达 |

## 4. 为什么不用 `from_fastapi`

0206 的自动转换适合**快速验证**。这个案例讲的是**生产包装**，区别在于：

| | 自动转换 | 手写包装 |
|---|---|---|
| 工具粒度 | 一个端点一个工具 | 一个任务一个工具 |
| 错误文案 | 原始 HTTP 错误 | 翻译成可操作建议 |
| 重试/超时 | 需额外配置 | 完全可控 |
| 多端点编排 | 模型自己组合 | 服务端封装好 |

真实项目常见做法：**内部用包装层，外部才暴露自动转换的原型**。

## 5. 客户端放 lifespan

```python
@asynccontextmanager
async def lifespan(server):
    client = httpx2.AsyncClient(timeout=2.0)
    try:
        yield {"client": client}
    finally:
        await client.aclose()
```

- 复用连接池，避免每次调用 TCP/TLS 握手；
- 统一超时，防止某个上游拖死整个服务；
- 关闭时 `aclose()`，避免资源泄漏。

4.x 的 HTTP 客户端是 `httpx2`（不是 `httpx`）。API 基本一致，导入名不同。

## 6. 错误映射表

| 上游情况 | 原始异常 | 映射后的 `ToolError` |
|---|---|---|
| 404 | `HTTPStatusError(404)` | `上游没有这个资源：<detail>` |
| 5xx | `HTTPStatusError(500+)` | `上游服务错误（500），请稍后重试...` |
| 超时 | `TimeoutException` | 重试 1 次后 `天气服务暂时不可达...` |
| 连不上 | `ConnectError` | 同上 |
| 4xx 其他 | `HTTPStatusError` | `上游拒绝了请求（403）` |

原则：**给模型「为什么 + 怎么办」，不给堆栈和内部地址。**

## 7. 重试策略

```python
for attempt in range(2):
    try:
        ...
    except (httpx2.TimeoutException, httpx2.ConnectError):
        if attempt == 0:
            continue
        raise ToolError("...")
```

- 只重试**瞬时错误**（超时、连接失败）；
- 404/400 不重试，重试也不会变；
- POST 等非幂等操作不要盲目重试，除非上游支持幂等键；
- 真实项目用指数退避 + 抖动，并设总预算（例如 5s）。

## 8. 配置与切换

```python
def api_base() -> str:
    return os.environ.get("WEATHER_API", "http://127.0.0.1:8107")
```

- 调用时读取，测试里可以 `monkeypatch.setenv` 指向临时服务；
- 生产用环境变量/密钥管理，不写进代码；
- 需要认证时给 `AsyncClient(headers={"Authorization": ...})`，token 同样从环境变量来。

## 9. 三种验证方式

**client.py**：自动起 mock API，跑正常 + 404 + 不可达。

**手动**：

```bash
uv run uvicorn mock_api:app --port 8107
WEATHER_API=http://127.0.0.1:8107 uv run python server.py
```

**Inspector**：连 `server.py`，调用 `debug_upstream_error` 观察 500 的文案。

## 10. 常见坑

**① 用同步 `httpx2.Client`**

会阻塞事件循环，并发请求排队。MCP 服务端一律用 `AsyncClient`。

**② 把上游堆栈直接返回**

泄漏内部地址与实现细节。统一 `raise ToolError("...")`，堆栈留在服务端日志。

**③ 对 4xx 做重试**

400/404 重试只会放大错误。只重试超时与连接失败。

**④ 忘记 `aclose()`**

连接泄漏，长时间运行后 fd 耗尽。放 `finally`。

**⑤ 超时设成 30s**

一个慢上游会占满所有并发。按业务设 2-5s，长任务改用后台任务。

**⑥ 在工具里新建 client**

每次调用都建连接池，性能差且易泄漏。放 lifespan。

## 11. 与 2.x / 3.x 的差异

- 4.x 使用 `httpx2`；2.x/3.x 用 `httpx`，迁移时改导入即可。
- 4.x 的 `Client` 也基于 `httpx2`，自定义 transport 时注意类型。
- `ToolError` 的位置与语义未变。
- 完整差异见 [`docs/03-compat.md`](../docs/03-compat.md)。

## 12. 练习

1. 给 `get_json` 加指数退避（0.2s、0.4s），并统计重试次数。
2. 加一个 `batch_weather(cities: list[str])`，用 `asyncio.gather` 并发查询，限制并发数为 5。
3. 给 mock API 加一个需要 `X-API-Key` 的端点，用环境变量注入，验证 401 的映射。

## 13. 延伸阅读

- httpx2 文档：<https://www.python-httpx.org/>
- FastMCP Lifespans：<https://gofastmcp.com/docs/servers/lifespan>
- 超时与取消：<https://gofastmcp.com/docs/servers/tools>
