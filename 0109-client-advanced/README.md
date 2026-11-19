# 0109 · 客户端进阶：完整调用面与最小 Host

> 目标：把 Client 的能力一次用全，并用 20 行写一个「不依赖 LLM 的 Host」，理解宿主到底负责什么。
> 难度 ★★★ ｜ 前置：0107 0108（概念）｜ 依赖：无 ｜ 端口：无 ｜ 预计：35 分钟

## 1. 你会学到

- 客户端的完整调用面：`list_tools` / `list_resources` / `list_prompts` / `call_tool` / `read_resource` / `get_prompt`。
- `raise_on_error=False` 与 `is_error`：什么时候要「拿结果」而不是「抛异常」。
- `ClientGroup` 如何把多个服务器聚合成一个工具目录，以及 `{server}_{tool}` 的命名规则。
- Host 的四项核心职责：发现、路由、参数检查、错误回灌。

## 2. 先跑起来

```bash
cd 0109-client-advanced
uv run python client.py
```

预期输出（截断）：

```text
--- 1. 发现 ---
tools = ['create_ticket', 'list_tickets', 'close_ticket']
resources = ['tickets://all']
prompts = ['triage']

--- 4. 错误分支 ---
is_error = True, content = 工单 999 不存在

--- 5. ClientGroup：一个入口聚合两个服务器 ---
聚合后的工具 = ['ticket_create_ticket', 'ticket_list_tickets', 'ticket_close_ticket', 'math_multiply', 'math_power']
math_multiply = 42

--- 6. 最小 Host：按计划执行 ---
  [ok] ticket_create_ticket → {'id': 2, ...}
  [ok] math_power → 1024
```

```bash
uv run pytest . -q
# 4 passed
```

## 3. 代码地图

| 文件 | 作用 |
|---|---|
| `server.py` | 工单服务：3 个工具 + 1 条资源 + 1 个提示 |
| `math_server.py` | 第二个服务器，用于 ClientGroup 聚合 |
| `client.py` | 调用面演示 + ClientGroup + 最小 Host |
| `test_server.py` | 覆盖调用、错误、聚合命名、Host 路由 |

## 4. 客户端调用面速查

| 目的 | 方法 | 返回 | 取数据 |
|---|---|---|---|
| 列工具 | `list_tools()` | `list[Tool]` | `.name` / `.input_schema` |
| 调工具 | `call_tool(name, args)` | `CallToolResult` | `.data` / `.content` / `.is_error` |
| 列资源 | `list_resources()` | `list[Resource]` | `str(item.uri)` |
| 读资源 | `read_resource(uri)` | `list[Content]` | `content[0].text` |
| 列提示 | `list_prompts()` | `list[Prompt]` | `.name` / `.arguments` |
| 取提示 | `get_prompt(name, args)` | `PromptResult` | `.messages` / `.meta` |

`CallToolResult` 的四个字段在 0103 讲过：`content`、`structured_content`、`data`、`meta`，外加 `is_error`。

## 5. 抛异常还是拿结果

```python
# 默认：isError 为 true 时抛 ToolError
try:
    await client.call_tool("close_ticket", {"ticket_id": 999})
except ToolError as exc:
    ...

# 需要自己检查错误、做降级或批量处理时
result = await client.call_tool("close_ticket", {"ticket_id": 999}, raise_on_error=False)
if result.is_error:
    print(result.content[0].text)
```

规律：

- **单次关键调用** → 默认抛异常，代码更短；
- **批量/循环/需要继续执行** → `raise_on_error=False`，收集每条结果；
- Host 通常用后者，把错误作为「工具结果」回灌给模型，让模型自己决定重试还是换方案。

## 6. ClientGroup：多服务器一个入口

```python
group = ClientGroup({"ticket": Client(mcp), "math": Client(math_mcp)})
async with group:
    tools = await group.list_tools()          # ticket_create_ticket, math_multiply, ...
    await group.call_tool("math_multiply", {"a": 6, "b": 7})
```

规则：

- 工具名统一加 `{server}_` 前缀，避免冲突；
- `group.list_tools()` 是**实时聚合**，成员服务器的工具变化会反映出来；
- 每个成员独立协商协议版本，可以混用现代/legacy/子进程；
- 它替代了「在中间再起一个代理服务器」的做法，适合本地 Host 聚合。

当服务器数量多、工具重名严重时，再考虑 0205 的 `mount(namespace=...)` 或代理层裁剪。

## 7. 最小 Host 的四项职责

`mini_host()` 做了一件很有代表性的事：给一个固定计划，逐个执行。

```python
plan = [
    ("ticket_create_ticket", {"title": "支付回调超时", "priority": "high"}),
    ("math_power", {"base": 2, "exponent": 10}),
]
```

它做了四件事：

1. **发现**：`list_tools()` 拿到工具名与 schema；
2. **路由**：按 `{server}_{tool}` 前缀找到对应成员；
3. **参数检查**：调用前比对 `required`，缺参数就跳过（真实 Host 会让模型补参）；
4. **错误回灌**：`raise_on_error=False`，把 `is_error` 与文本作为下一步输入。

LLM 在真实 Host 里替代的是「生成 plan」这一步；**执行、校验、错误处理仍然是 Host 的代码**。0306 会把这条链路补完整。

## 8. 三种验证方式

**client.py**：完整跑一遍调用面、聚合、Host。

**Inspector**：`uv run fastmcp dev inspector server.py`，对比 Inspector 里的工具列表与 `client.list_tools()` 的输出。

**接入宿主**：ClientGroup 是「自己写 Host」时用的；如果只是接 Claude Desktop，用 0101 的单服务器配置即可。

## 9. 常见坑

**① 在 `async with` 外调用 client**

```text
RuntimeError: Client is not connected. Use the 'async with client:' context manager first.
```

**② 批量调用时用默认 `raise_on_error=True`**

第一条失败就中断整个循环。批量场景显式传 `False`。

**③ 以为 ClientGroup 会去重同名工具**

它只加前缀，不做语义合并。两个服务器都有 `search` 时，你需要自己决定用哪个。

**④ 把 Host 的逻辑写进服务器**

服务器只声明能力；「先调哪个、失败了怎么办」属于 Host。混在一起会让服务器难以复用。

## 10. 与 2.x / 3.x 的差异

- `ClientGroup` 是 4.0 新增；2.x 需要自己遍历多个 Client。
- `call_tool` 的 `raise_on_error` 参数在 3.x 之后稳定；更早版本只能自己检查 `isError`。
- `list_tools()` 的 `cache_mode` 也是 4.x 新增（默认 `use`）。
- 完整差异见 [`docs/03-compat.md`](../docs/03-compat.md)。

## 11. 练习

1. 给 `mini_host` 加一条规则：`math_power` 的 `exponent` 超过 10 时自动改成 10，并打印「已修正参数」。
2. 用 `ClientGroup.from_config({...})` 从 MCP 配置字典创建聚合，比较与手动传 Client 的差异。
3. 写一个 `summarize_tools()`，把 `list_tools()` 的结果整理成「工具名 + 必填参数」的 Markdown 表格，作为给模型的工具清单。

## 12. 延伸阅读

- FastMCP Client：<https://gofastmcp.com/docs/clients/client>
- 调用工具：<https://gofastmcp.com/docs/clients/tools>
- Client Groups：<https://gofastmcp.com/docs/clients/client-groups>
