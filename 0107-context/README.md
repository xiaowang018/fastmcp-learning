# 0107 · Context：进度、日志、资源与请求内状态

> 目标：让工具有「感知能力」——上报进度、写日志、读资源、拿请求标识，并理解 4.x 的状态边界。
> 难度 ★★★ ｜ 前置：0105 0106 ｜ 依赖：无 ｜ 端口：无 ｜ 预计：30 分钟

## 1. 你会学到

- 在工具签名里加 `ctx: Context`，FastMCP 会自动注入，**不会**出现在工具参数里。
- `report_progress` + 客户端的**异步** `progress_handler`。
- `ctx.read_resource()` 与 `client.read_resource()` 的返回结构差异。
- `set_state/get_state` 的真实边界：**同一次调用内有效，跨调用重置**。
- 为什么 `ctx.info` 在 2026-07-28 协议下被标记为 deprecated，以及 stderr 的正确用法。

## 2. 先跑起来

```bash
cd 0107-context
uv run python client.py
```

预期输出（截断）：

```text
--- summarize：读资源 + 进度 ---
  [progress] 0.0/2.0 读取摘要规范
  [progress] 1.0/2.0 处理文本
  [progress] 2.0/2.0 完成
  rule = 摘要要求：不超过 80 字；保留数字与结论；不要加入原文没有的推断。

--- state_demo：同一会话里的两次调用 ---
  第一次：{'before': None, 'after': 'draft-A', 'request_id': '5', 'session_id': 'cbe3...'}
  第二次：{'before': None, 'after': 'draft-B', 'request_id': '6', 'session_id': '2b44...'}
  结论：同一次调用内 set/get 有效；跨调用 before 仍是 None，session_id 也变了。
```

```bash
uv run pytest . -q
# 3 passed
```

## 3. 代码地图

| 文件 | 作用 |
|---|---|
| `server.py` | 四个工具：`summarize` / `long_task` / `state_demo` / `logging_demo` |
| `client.py` | 注册异步进度/日志回调，并对比两次调用的状态 |
| `test_server.py` | 断言进度序列、状态边界、日志级别 |

## 4. Context 是怎么注入的

```python
@mcp.tool
async def summarize(text: str, ctx: Context) -> dict:
```

- `ctx` 参数**不会**出现在 `inputSchema` 里，模型看不到它。
- 只要类型注解是 `Context`，FastMCP 就会在调用时注入当前请求的上下文。
- 同一套机制也适用于 Resource / Prompt 函数。

## 5. 进度上报

```python
await ctx.report_progress(0, 2, "读取摘要规范")
...
await ctx.report_progress(2, 2, "完成")
```

客户端必须提供**异步**回调：

```python
async def on_progress(progress: float, total: float | None, message: str | None) -> None:
    ...

async with Client(mcp, progress_handler=on_progress) as client:
    ...
```

本案例最容易踩的坑：写成同步 `def`，会得到

```text
notification callback raised
TypeError: object NoneType can't be used in 'await' expression
```

而且这个错误只写日志、不中断调用，很容易以为「进度没生效」。

## 6. 读资源：两个 API 的返回结构不同

| API | 返回 | 取内容 |
|---|---|---|
| `client.read_resource(uri)` | `list[TextResourceContents \| BlobResourceContents]` | `content[0].text` |
| `ctx.read_resource(uri)`（服务端） | `ResourceResult` | `result.contents[0].content` |

服务端读资源的典型用途：把「摘要规范」「字段字典」「提示词模板」放在 Resource 里，工具运行时读取，避免规则硬编码。

## 7. 状态的真实边界

```python
before = await ctx.get_state("draft")   # None
await ctx.set_state("draft", value)
after = await ctx.get_state("draft")    # value
```

在 2026-07-28 协议下，每次 `tools/call` 都是**独立会话**：

- 同一次调用内 `set` 后立刻 `get`：有效；
- 跨两次调用：`before` 又是 `None`，`session_id` 也变了；
- 想跨调用保存状态，要用 `session_state_store`（见 FastMCP 文档的 Session State）。

这不是 bug，而是「无会话协议」的设计：请求自带全部上下文，方便横向扩容。

## 8. 日志：三条通道

| 方式 | 去向 | 适用 |
|---|---|---|
| `await ctx.info(...)` | MCP 日志通知 → 客户端 `log_handler` | 调试、给宿主看 |
| `print(..., file=sys.stderr)` | 服务端进程 stderr | stdio 模式下唯一安全的旁路 |
| `print(...)`（默认 stdout） | **污染 JSON-RPC 协议流** | 绝对不要 |

2026-07-28 协议把 MCP logging capability 标记为 deprecated（SEP-2577），`ctx.info` 仍可用但会告警。新项目优先用进度 + 返回值表达状态，日志只作为调试辅助。

## 9. 三种验证方式

**client.py**：直接看到进度序列与两次调用的状态差异。

**Inspector**：`uv run fastmcp dev inspector server.py`，调用 `long_task` 时界面会有进度条；日志在 Notifications 面板。

**接入宿主**：宿主通常会把进度渲染成进度条；`ctx.info` 是否显示取决于宿主是否实现 logging。

## 10. 常见坑

**① 进度回调写成同步函数**

见第 5 节。必须 `async def`。

**② 用 `ctx.set_state` 做跨调用缓存**

现代协议下不保留。跨调用请用数据库、文件，或显式配置 `session_state_store`。

**③ 在工具里 `print()` 调试**

stdio 模式下 stdout 是协议通道，一行 print 就能让客户端解析失败。用 stderr 或 `ctx.info`。

**④ 把 `ctx.read_resource` 的返回值当列表**

它返回 `ResourceResult`，不是 list；内容在 `.contents[0].content`。

## 11. 与 2.x / 3.x 的差异

- 4.0 起现代协议默认无会话，`set_state` 不再跨调用；2.x 的 session 语义不同。
- `ctx.sample()` / `ctx.list_roots()` 在 4.0 被移除；`ctx.elicit()` 仅 legacy 连接可用。
- `ctx.info` 在 2026-07-28 协议下 deprecated。
- 完整差异见 [`docs/03-compat.md`](../docs/03-compat.md)。

## 12. 练习

1. 给 `long_task` 加一个 `fail_at: int | None`，在第 N 步抛 `ToolError`，观察客户端的进度与错误如何共存。
2. 把 `summarize` 的规则改成两条 Resource（`policy://summary` 和 `policy://style`），用 `asyncio.gather` 并行读取。
3. 故意在 `logging_demo` 里写一个裸 `print("debug")`，用 stdio 方式连接，观察客户端报什么错。

## 13. 延伸阅读

- FastMCP Context：<https://gofastmcp.com/docs/servers/context>
- 进度与日志：<https://gofastmcp.com/docs/servers/progress>
- Session State：<https://gofastmcp.com/docs/servers/sessions>
