# 0202 · 生命周期与依赖注入：连接池该放哪

> 目标：把「进程级资源」放进 lifespan，把「每次调用的配置」交给 Depends，两者都不出现在工具 schema 里。
> 难度 ★★★ ｜ 前置：0107 0201 ｜ 依赖：无 ｜ 端口：无 ｜ 预计：30 分钟

## 1. 你会学到

- `lifespan` 的启动/关闭时机，以及为什么清理必须写在 `finally`。
- `ctx.lifespan_context` 如何在多次调用间复用同一个连接池。
- `Depends` 注入的参数如何从 schema 中消失。
- 请求内状态（0107）与进程级状态（本例）的边界。

## 2. 先跑起来

```bash
cd 0202-lifespan-di
uv run python client.py
```

预期输出（截断）：

```text
连接前：started=0 stopped=0
连接后：started=1 stopped=0
acquire(alice) = {'handle': 'pool-1#1', 'in_use': 1, 'pool': 'pool-1'}
acquire(bob) = {'handle': 'pool-1#2', 'in_use': 2, 'pool': 'pool-1'}
release(alice) = {'in_use': 1, 'history': ['acquire:alice', 'acquire:bob', 'release:alice']}
effective_settings 的参数 = []
crash = Error calling tool 'crash': 模拟数据库断连
断开后：started=1 stopped=1 closed=True
```

```bash
uv run pytest . -q
# 4 passed
```

## 3. 代码地图

| 文件 | 作用 |
|---|---|
| `server.py` | lifespan 创建/关闭 `FakePool`，四个工具演示复用、清理、Depends |
| `client.py` | 观察 started/stopped、连接复用、参数隐藏、异常后的清理 |
| `test_server.py` | 断言池共享、清理必达、Depends 不出现在 schema |

## 4. lifespan 的时机

```python
@asynccontextmanager
async def app_lifespan(server: FastMCP):
    pool = FakePool(...)
    try:
        yield {"pool": pool, "settings": Settings()}
    finally:
        pool.closed = True

mcp = FastMCP("...", lifespan=app_lifespan)
```

- **启动**：服务器开始服务前执行，yield 的值成为 `ctx.lifespan_context`。
- **复用**：同一个服务器进程内，所有请求共享这个值（与 0107 的请求内状态不同）。
- **关闭**：客户端断开 / 进程退出时执行 `finally`，即使工具有异常也会执行。

本案例的测试专门验证了「`crash` 抛错后池仍然被关闭」。

## 5. 三种作用域，别混

| 作用域 | 载体 | 生命周期 | 典型用途 |
|---|---|---|---|
| 请求内 | `ctx.set_state/get_state` | 一次 `tools/call` | 多步操作的临时草稿 |
| 进程内 | `lifespan` + `ctx.lifespan_context` | 服务器进程 | 连接池、HTTP 客户端、模型、缓存 |
| 跨进程 | 数据库 / Redis / 文件 | 持久 | 业务数据、会话存储 |

把连接池放进 `ctx.set_state` 是最常见的错误：每次调用都会新建一个池，连接数瞬间爆炸。

## 6. Depends：把参数从 schema 里藏起来

```python
def get_settings() -> Settings:
    return Settings()

@mcp.tool
def effective_settings(settings: Settings = Depends(get_settings)) -> dict:
    return {"region": settings.region}
```

- `settings` **不会**出现在 `inputSchema` 里，模型看不到也不需要填。
- 适合：当前用户、租户、配置、数据库句柄。
- 与 `ctx` 注入的区别：`Context` 拿的是请求上下文；`Depends` 拿的是你定义的工厂返回值。

4.2 还支持把依赖写进类型注解：

```python
Config = Annotated[dict, Depends(get_settings)]

@mcp.tool
async def fetch(query: str, config: Config) -> str: ...
```

## 7. 三种验证方式

**client.py**：观察 started/stopped 与池历史。

**Inspector**：看 `effective_settings` 的参数列表为空，确认 Depends 生效。

**接入宿主**：lifespan 在宿主拉起进程时执行一次；宿主重启才会重建池。

## 8. 常见坑

**① 把 `yield` 写在 `try` 外面**

```python
async def lifespan(server):
    pool = create_pool()
    yield {"pool": pool}
    pool.close()      # 异常时不会执行
```

必须 `try/finally`，否则工具崩溃时连接泄漏。

**② 在 lifespan 里做耗时初始化**

宿主通常有启动超时（10-30s）。大数据加载、模型下载应该放后台任务或懒加载。

**③ 用 `ctx.set_state` 存连接池**

请求结束即销毁，下一次调用又建一个池。连接池必须放 lifespan。

**④ Depends 工厂抛异常**

会变成工具调用的内部错误。工厂里要做好默认值与降级。

**⑤ 在测试 fixture 里打开 Client**

事件循环生命周期错位。fixture 只产出 server 对象，连接写在测试体内。

## 9. 与 2.x / 3.x 的差异

- `lifespan` 参数与 `ctx.lifespan_context` 在 2.x 已存在，4.x 行为一致。
- `Depends` 从 `fastmcp.dependencies` 导入；4.2 新增 `Annotated[..., Depends(...)]` 写法。
- 4.x 的现代协议下请求状态不跨调用，lifespan 的作用更加重要。
- 完整差异见 [`docs/03-compat.md`](../docs/03-compat.md)。

## 10. 练习

1. 给 `FakePool` 加一个 `max_size`，`acquire` 超过上限时抛 `ToolError`，并用测试覆盖。
2. 把 `get_settings` 改成读环境变量 `APP_REGION`，用 `monkeypatch` 在测试里切换。
3. 写一个 `@mcp.tool` 故意 `await asyncio.sleep(10)`，在客户端取消后确认 lifespan 仍然关闭池。

## 11. 延伸阅读

- FastMCP Lifespans：<https://gofastmcp.com/docs/servers/lifespan>
- 依赖注入：<https://gofastmcp.com/docs/servers/dependency-injection>
- Session State：<https://gofastmcp.com/docs/servers/sessions>
