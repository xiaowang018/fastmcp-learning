# 0104 · 失败的五种形态：校验、业务错误、异常、超时、取消

> 目标：不再把「报错」当成一件事。MCP 里五类失败在客户端表现完全不同，处理方式也不同。
> 难度 ★★★ ｜ 前置：0103 ｜ 依赖：无 ｜ 端口：无 ｜ 预计：30 分钟

## 1. 你会学到

- 参数校验失败、业务 `ToolError`、未捕获异常、服务端超时、客户端取消，各自长什么样。
- `ToolError` 的消息为什么能直达模型，而普通异常会被包一层。
- `mask_error_details` 什么时候该开，开了会丢什么。
- `annotations`（`readOnlyHint` / `destructiveHint` / `idempotentHint`）如何告诉宿主「这个工具安全不安全」。
- `raise_on_error=False` 与 `is_error` 的用途。

## 2. 先跑起来

```bash
cd 0104-tool-errors
uv run python client.py
```

预期输出（截断）：

```text
get_balance 的注解： title='查询余额' read_only_hint=True destructive_hint=None idempotent_hint=True open_world_hint=False

① 参数校验失败（a 传了字符串）
   ToolError: 1 validation error for call[divide]
② 业务错误（余额不足）
   ToolError: 余额不足：当前 100 元，尝试取出 500 元
③ 未捕获异常（mask_error_details=False，详情会泄漏）
   ToolError: Error calling tool 'crash': 数据库连接串：postgres://user:secret@localhost/db
④ 服务端超时（工具声明 timeout=0.3s）
   ToolError: Error calling tool 'slow': Tool 'slow' execution timed out after 0.3s
⑤ 客户端取消（0.1s 后 cancel 任务）
   CancelledError：取消不是错误，是调用方主动放弃
```

```bash
uv run pytest . -q
# 6 passed
```

## 3. 代码地图

| 文件 | 作用 |
|---|---|
| `server.py` | 五个工具，分别对应五类失败；`get_balance` 带只读注解 |
| `client.py` | 逐条触发并打印异常类型与消息 |
| `test_server.py` | 把「错误消息长什么样」固化成断言 |

## 4. 五类失败对照表

| # | 触发方式 | 客户端收到 | 是否 `isError` | 该怎么做 |
|---|---|---|---|---|
| ① | 参数类型/约束不满足 | `ToolError`，消息里带 `validation error` | 是 | 不要 catch，让模型看到并改参数 |
| ② | 业务规则不满足，主动 `raise ToolError("...")` | `ToolError`，**消息原样保留** | 是 | 写清「为什么 + 怎么改」，这是给模型看的 |
| ③ | 未捕获异常（`ValueError` 等） | `ToolError: Error calling tool 'x': <详情>`；开掩码后只剩 `Error calling tool 'x'` | 是 | 服务端记日志，客户端只给安全文案 |
| ④ | 工具声明 `timeout=` 且超时 | `ToolError`，消息含 `execution timed out` | 是 | 长任务改用 `task=True` 后台任务 |
| ⑤ | 客户端 `task.cancel()` / 断开 | `asyncio.CancelledError` | — | 不要当错误处理；服务端应清理资源 |

**关键区别**：前四类都是「工具调用失败」，以 `isError: true` 的**正常结果**返回；第五类不是错误，是调用方主动放弃。

## 5. `ToolError` 与普通异常

```python
from fastmcp.exceptions import ToolError

@mcp.tool
def withdraw(amount: int) -> dict:
    if amount > BALANCE:
        raise ToolError(f"余额不足：当前 {BALANCE} 元，尝试取出 {amount} 元")
```

- `ToolError` 的语义是「工具无法完成，但这是可预期的业务结果」。消息会**原样**发给客户端，所以写给模型看：包含当前值、期望值、下一步建议。
- 普通异常（`ValueError` / `RuntimeError`）默认也会带详情，但那是**内部错误**，可能泄漏路径、连接串、SQL。生产环境应开启掩码。

### `mask_error_details`

```python
mcp = FastMCP("ErrorDemo", mask_error_details=True)
```

开启后：

- `ToolError` 的消息仍然保留（它被认为是安全文案）；
- 其他异常统一变成 `Error calling tool 'x'`；
- 完整堆栈只出现在**服务端日志**里。

本案例故意关闭掩码，让学员看到泄漏；第 7 节给出生产写法。

## 6. 超时与取消

```python
@mcp.tool(timeout=0.3)
async def slow(seconds: float = 2.0) -> str:
    await asyncio.sleep(seconds)
```

- `timeout` 是**服务端**约束，超时返回 MCP 错误（客户端看到 `ToolError`）。
- 同步函数在线程池里跑，**无法被真正中断**：超时后客户端立刻收到错误，但线程会继续跑到结束。CPU 密集型任务不要指望 `timeout` 能省资源。
- 客户端 `Client(..., timeout=10)` 是**客户端**约束，两者相互独立。
- `task.cancel()` 触发的是取消，不是超时；服务端应捕获 `CancelledError` 做清理后**重新抛出**，不要吞掉。

## 7. 生产建议：掩码 + 日志

```python
mcp = FastMCP("Production", mask_error_details=True)

@mcp.tool
def crash() -> str:
    raise RuntimeError("postgres://user:secret@localhost/db")
```

客户端只会看到 `Error calling tool 'crash'`，堆栈留在服务端日志。需要给模型可操作信息时，显式 `raise ToolError("...")`。

## 8. `annotations`：给宿主的 safety profile

```python
@mcp.tool(annotations=ToolAnnotations(
    title="查询余额",
    readOnlyHint=True,
    idempotentHint=True,
    openWorldHint=False,
))
```

| 注解 | 含义 | 宿主可能的行为 |
|---|---|---|
| `readOnlyHint` | 只读，不改变状态 | 跳过二次确认 |
| `destructiveHint` | 可能删除/覆盖数据 | 弹确认框 |
| `idempotentHint` | 重复调用结果相同 | 允许自动重试 |
| `openWorldHint` | 会访问外部系统 | 提示网络/隐私风险 |

注解是**建议**，不是强制安全边界。真正的权限要靠 0204 的鉴权。

## 9. 三种验证方式

**client.py**：一次看全五类失败。

**Inspector**：调用 `withdraw` 传 `500`，界面上会显示 `isError: true` 和错误文本；调用 `get_balance` 能在工具详情看到注解。

**接入宿主**：配置同 0101。带 `destructiveHint` 的工具在 Claude 里通常会先征求确认，可以直接观察宿主差异。

## 10. 常见坑

**① 用 `except Exception` 吞掉 `CancelledError`**

Python 3.8+ 的 `CancelledError` 继承 `BaseException`，`except Exception` 抓不到；但如果你写了 `except BaseException`，会把取消也吞掉，导致连接无法正常关闭。

**② 把内部异常消息直接返回给模型**

```text
错误：模型看到 "psycopg2.OperationalError: password authentication failed for user 'root'"
原因：mask_error_details=False，且没有转成 ToolError
解决：生产开启掩码；对外只抛语义化的 ToolError
```

**③ 以为 `timeout` 能中断同步函数**

同步工具跑在线程池，超时只是「客户端不再等」，线程还在跑。长任务用 `async` + 取消检查点，或 `task=True`。

**④ 在工具里 `raise HTTPException`**

那是 FastAPI 的异常，FastMCP 不认识，会被当成未捕获异常。MCP 侧统一用 `ToolError`。

## 11. 与 2.x / 3.x 的差异

- `@mcp.tool(timeout=...)` 从 3.0 起提供；2.x 需要自己在函数里 `asyncio.wait_for`。
- `ToolError` 从 `fastmcp.exceptions` 导入，4.x 未变；但 2.x 里 `ToolResult` 的位置和字段不同。
- `mask_error_details` 在 4.x 对 `ToolError` / `ResourceError` 一律放行，只掩普通异常。
- 完整差异见 [`docs/03-compat.md`](../docs/03-compat.md)。

## 12. 练习

1. 把 `mask_error_details` 改成 `True`，重跑 `client.py`，记录 ③ 和 ④ 的消息变化。
2. 给 `withdraw` 加 `annotations=ToolAnnotations(destructiveHint=True)`，在 Inspector 里看差异。
3. 写一个 `async def long_task()`，在循环里每 100ms 检查一次取消，被取消时打印「清理完成」再 `raise`。

## 13. 延伸阅读

- FastMCP Tools（错误处理与注解）：<https://gofastmcp.com/docs/servers/tools>
- MCP 错误语义：<https://modelcontextprotocol.io/specification>
