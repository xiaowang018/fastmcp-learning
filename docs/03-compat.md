# 版本差异：2.x / 3.x → 4.x

> 网上大量教程停留在 2.x。照抄最常见的后果是 `AttributeError`、`TypeError`、工具不出现。本文只列本仓库涉及的差异，完整清单以官方升级指南为准。

## 1. 先确认版本

```bash
uv run python -c "from importlib.metadata import version; print(version('fastmcp'))"
# 4.2.1
```

`fastmcp.__version__` 在 4.2.1 里仍然存在，但不要依赖它；用 `importlib.metadata`。

`fastmcp` 4.x 是**薄元包**，实际代码在 `fastmcp-slim[client,server]`。只装了一半时会出现「能 import 但什么都没有」的假象。只用 `uv sync` / `uv add`，不要 `pip install -U fastmcp` 混装。

## 2. 速查表

| 主题 | 2.x / 3.x | 4.x |
|---|---|---|
| 连接本地脚本 | `Client("server.py")` | `Client(Path("server.py"))`（字符串已弃用） |
| 组合服务器 | `import_server`（复制）/ `mount`（链接） | 统一 `mount(server, namespace=...)` |
| 代理 | `as_proxy(...)` | `create_proxy(...)` |
| 采样 | `ctx.sample()` / `ctx.sample_step()` | **已移除**，改多轮 `InputRequiredResult` |
| Roots | `ctx.list_roots()` | **已移除**，改返回/恢复模式 |
| 用户追问 | `ctx.elicit()` | 仅 legacy 连接可用；现代协议用多轮 |
| 工具装饰器 | `@mcp.tool()` | `@mcp.tool`（两种都支持，建议统一） |
| Apps | 无 | `@mcp.tool(app=True)`（3.2+） |
| HTTP 客户端 | `httpx` | `httpx2`（FastMCP 内部与示例） |
| 协议 | 握手时代 | 现代（2026-07-28）+ legacy 双协议 |
| 资源安全 | 自行校验 | `ResourceSecurity` 默认开启（4.0+） |
| 中间件初始化钩子 | `on_initialize` 可用 | 仅 legacy；现代用 `on_discover` |
| 工具可见性 | 无统一机制 | tags + `mcp.enable/disable`（3.0+） |
| 组件版本 | 无 | `version=` + 最高版本解析（3.0+） |

## 3. 导入路径变化

| 对象 | 4.x 导入 |
|---|---|
| `ToolResult` | `from fastmcp.tools import ToolResult` |
| `Message` / `PromptResult` | `from fastmcp.prompts import Message, PromptResult` |
| `ResourceResult` / `ResourceContent` | `from fastmcp.resources import ResourceResult, ResourceContent` |
| `Image` / `Audio` / `File` | `from fastmcp.utilities.types import Image` |
| `ToolError` / `ResourceError` | `from fastmcp.exceptions import ...` |
| `Depends` | `from fastmcp.dependencies import Depends` |
| `Middleware` | `from fastmcp.server.middleware import Middleware` |
| `StaticTokenVerifier` | `from fastmcp.server.auth import StaticTokenVerifier` |
| `create_proxy` | `from fastmcp.server import create_proxy` |
| `ToolAnnotations` | `from mcp.types import ToolAnnotations` |

2.x 教程里的 `fastmcp.server.context.Context`、`fastmcp.tools.tool.ToolResult` 等旧路径可能仍可用，但不要在新项目里使用。

## 4. 协议纪元带来的行为差异

| 现象 | 现代（默认） | legacy |
|---|---|---|
| `session_id` | 每次调用不同 | 同一连接相同 |
| `ctx.set_state` | 跨调用重置 | 跨调用保留 |
| `ctx.elicit` | 不可用 | 可用 |
| `on_initialize` | 不触发 | 触发 |
| `ctx.sample` | 已移除 | 已移除 |

调试状态问题时，先打印 `client.protocol_version`，再决定是不是协议差异。

## 5. 字段命名

4.x 的 Python 对象用 snake_case，JSON 用 camelCase：

```python
tool.input_schema           # 不是 tool.inputSchema（已弃用）
tool.annotations.read_only_hint
result.structured_content
```

MCP 协议报文里仍是 `inputSchema`、`structuredContent`、`isReadOnlyHint`。

## 6. 错误处理差异

- 2.x：普通异常直接以文本返回，掩码能力有限；
- 4.x：`mask_error_details=True` 时只保留 `ToolError` / `ResourceError` 的消息，其余统一为 `Error calling tool 'x'`；
- 4.x 的 scope 检查会让工具**不可见**，而不是返回 403；
- 4.x 的协议层错误（鉴权、限流）仍会抛 `MCPError`，`raise_on_error=False` 接不住。

## 7. 迁移步骤建议

1. 锁定版本，先跑通测试基线；
2. 把 `Client("x.py")` 全部改成 `Path`；
3. 把 `import_server` 改成 `mount`，并补 `namespace`；
4. 搜索 `ctx.sample` / `ctx.list_roots`，按新范式重写；
5. 检查 `on_initialize` 是否还符合预期；
6. 把 `httpx` 换成 `httpx2`（如果自定义了客户端）；
7. 开启 `mask_error_details`，逐个把业务错误转成 `ToolError`；
8. 用 `Client(url, mode="legacy")` 做兼容性回归，确认老客户端仍可用。

## 8. 本仓库的取舍

- 代码按 4.2 写，不提供 2.x 分支；
- 每篇案例只写 1-3 条 case-specific 差异，总表在这里维护；
- 标注「4.0 移除」的能力（sampling / roots）不设案例，但在 0108 解释原因，避免学员照抄旧教程。

## 9. 参考

- What's New in FastMCP 4：<https://gofastmcp.com/docs/getting-started/whats-new>
- 从 2 升级：<https://gofastmcp.com/docs/getting-started/upgrading/from-fastmcp-2>
- 从 3 升级：<https://gofastmcp.com/docs/getting-started/upgrading/from-fastmcp-3>
- 从 4.1 升级：<https://gofastmcp.com/docs/getting-started/upgrading/from-fastmcp-4-1>
