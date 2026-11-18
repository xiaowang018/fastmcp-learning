# 0203 · 中间件：审计、配额、截断与计时

> 目标：把日志、限流、响应裁剪这些横切逻辑从业务工具里拿出来，并搞清中间件的执行顺序。
> 难度 ★★★ ｜ 前置：0201 0202 ｜ 依赖：无 ｜ 端口：无 ｜ 预计：30 分钟

## 1. 你会学到

- `Middleware` 的钩子层级：`on_message` → `on_request` → `on_call_tool`。
- 自定义中间件如何读 `context.message.name/arguments`，如何短路。
- 内置中间件：`TimingMiddleware`、`ResponseLimitingMiddleware`，以及限流/重试/缓存的选择。
- 中间件顺序为什么重要，以及 4.x 现代协议下 `on_initialize` 不触发。

## 2. 先跑起来

```bash
cd 0203-middleware
uv run python client.py
```

预期输出（截断）：

```text
--- add 的配额是 2 次 ---
[audit] add {'a': 0, 'b': 1}
  第 1 次：is_error=False data=1
[audit] add {'a': 1, 'b': 1}
  第 2 次：is_error=False data=2
[audit] add {'a': 2, 'b': 1}
  第 3 次：is_error=True data=None

--- big：200 字符会被截断到 300 字节以内 ---
  长度=240
  结尾='xxxxx\n\n[Response truncated due to size limit]'
```

```bash
uv run pytest . -q
# 3 passed
```

## 3. 代码地图

| 文件 | 作用 |
|---|---|
| `server.py` | 两个自定义中间件 + 两个内置中间件 + 三个工具 |
| `client.py` | 触发配额、截断、计时，并打印审计记录 |
| `test_server.py` | 断言配额错误、截断标记、审计顺序 |

## 4. 注册与顺序

```python
mcp.add_middleware(AuditMiddleware())        # 1st in, last out
mcp.add_middleware(QuotaMiddleware())        # 2nd in, 2nd out
mcp.add_middleware(TimingMiddleware())       # 3rd in, 3rd out
mcp.add_middleware(ResponseLimitingMiddleware(max_size=300))
```

请求按注册顺序进入，响应按相反顺序返回。经验法则：

- **错误处理/审计**放最外层（能捕获后面所有中间件的异常）；
- **限流**放在业务之前；
- **响应裁剪**放最靠近业务的一侧；
- **计时代理**放在你关心的范围外层。

## 5. 三个钩子层级

| 层级 | 钩子 | `context.message` 内容 |
|---|---|---|
| 消息 | `on_message` | 所有 JSON-RPC 消息 |
| 类型 | `on_request` / `on_notification` | 请求或通知 |
| 操作 | `on_call_tool` / `on_read_resource` / `on_get_prompt` / `on_list_tools` ... | 具体方法参数 |

最小自定义中间件：

```python
class AuditMiddleware(Middleware):
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        print(context.message.name, context.message.arguments)
        return await call_next(context)
```

- 调用 `call_next(context)` 继续链路；
- 不调用就是短路；
- 抛 `ToolError` 会变成 `isError: true` 的工具结果；
- 抛 `MCPError` 会变成协议层错误（客户端 `call_tool` 直接抛异常，`raise_on_error=False` 也接不住）。

配额中间件就是靠 `raise ToolError(...)` 实现「业务级拒绝」的。

## 6. 内置中间件清单

| 中间件 | 导入 | 用途 |
|---|---|---|
| `TimingMiddleware` | `...middleware.timing` | 每个请求耗时 |
| `DetailedTimingMiddleware` | `...middleware.timing` | 按操作类型分别计时 |
| `LoggingMiddleware` | `...middleware.logging` | 人类可读请求日志 |
| `StructuredLoggingMiddleware` | `...middleware.logging` | JSON 日志 |
| `RateLimitingMiddleware` | `...middleware.rate_limiting` | 令牌桶限流 |
| `SlidingWindowRateLimitingMiddleware` | `...middleware.rate_limiting` | 精确窗口限流 |
| `ErrorHandlingMiddleware` | `...middleware.error_handling` | 异常计数/转换 |
| `RetryMiddleware` | `...middleware.error_handling` | 指数退避重试 |
| `ResponseCachingMiddleware` | `...middleware.caching` | TTL 缓存 |
| `ResponseLimitingMiddleware` | `...middleware.response_limiting` | 响应截断 |

限流类中间件按「请求」计数，**初始化、list_tools 也会占用配额**，所以生产参数不要设成 1/s 这种极限值。本案例改用自定义配额，让行为完全确定。

## 7. 现代协议下的钩子差异

- `on_initialize` 只在 **legacy** 连接触发；现代协议用 `server/discover`，对应 `on_discover`。
- `on_message` 能看到通知、取消等所有消息，适合做统一审计。
- 中间件状态不自动跨挂载边界；组合服务器时，父子各自执行自己的中间件。

## 8. 三种验证方式

**client.py**：配额、截断、审计一次看全。

**Inspector**：连续点三次 `add`，第三次会显示配额错误；`big` 的结果会被截断。

**接入宿主**：宿主看到的错误文本就是 `ToolError` 的内容；限流错误建议写成「请稍后重试」这类可操作文案。

## 9. 常见坑

**① 顺序写反**

把审计放在限流后面，被限流拒绝的请求就不会进审计。需要「所有请求都记录」时，审计必须最外层。

**② 在中间件里抛裸 `Exception`**

会变成内部错误（`isError` + 堆栈），而不是业务错误。对外拒绝用 `ToolError`。

**③ 以为 `raise_on_error=False` 能接住所有错误**

协议层错误（`MCPError`，例如限流、鉴权失败）不走工具结果，仍会抛异常。要分别处理。

**④ 响应截断后还依赖 `structuredContent`**

`ResponseLimitingMiddleware` 会用纯文本替换结构化输出，并在 `tools/list` 里省略 `outputSchema`。需要结构化数据的工具不要套这层。

**⑤ 中间件里做阻塞 IO**

中间件跑在事件循环里，`time.sleep` / 同步数据库调用会拖慢所有请求。用 `async` 或 `asyncio.to_thread`。

## 10. 与 2.x / 3.x 的差异

- 中间件从 2.9 起提供；4.x 的钩子覆盖更全（含通知、取消、发现）。
- `on_initialize` 在 4.x 现代协议下不触发，迁移时容易误判「中间件失效」。
- `ResponseLimitingMiddleware` / `PingMiddleware` 是 3.0 新增。
- 完整差异见 [`docs/03-compat.md`](../docs/03-compat.md)。

## 11. 练习

1. 给 `QuotaMiddleware` 加「按客户端 IP 限流」：HTTP 模式下从 `get_http_headers()` 读 `x-forwarded-for`。
2. 用 `RetryMiddleware(max_retries=2, retry_exceptions=(ConnectionError,))` 包一个会随机失败的 `flaky()` 工具。
3. 写一个 `on_list_tools` 中间件，把名字以 `internal_` 开头的工具从列表中过滤掉。

## 12. 延伸阅读

- FastMCP Middleware：<https://gofastmcp.com/docs/servers/middleware>
- 内置限流：<https://gofastmcp.com/docs/servers/middleware>
