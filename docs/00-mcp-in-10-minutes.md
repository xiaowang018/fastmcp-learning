# MCP 十分钟速览

> 读这篇不需要写代码。目标是建立一张地图，知道后面 22 个案例分别在地图的什么位置。

## 1. 三个角色

```text
Host（Claude Desktop / Cursor / 你的 Agent）
  └─ Client（协议实现，负责握手与收发）
       └─ Server（你写的 FastMCP 程序，声明工具/资源/提示）
```

- **Host** 决定「什么时候调用哪个能力」，把结果交给模型。
- **Client** 管协议：JSON-RPC、传输、认证、生命周期。FastMCP 的 `Client` 就是它。
- **Server** 只声明能力，不关心谁来调。

一个 Host 可以连多个 Server；一个 Server 也可以被多个 Host 连。

## 2. 三个核心原语

| 原语 | 语义 | 例子 | 谁发起 |
|---|---|---|---|
| Tool | 可执行的动作，可能有副作用 | `create_ticket`、`send_email` | 模型 |
| Resource | 可读取的数据，通常只读 | `file:///readme.md`、`db://schema` | Host/用户 |
| Prompt | 可复用的消息模板 | `code_review`、`daily_plan` | 用户 |

判断标准：

- 要「做事」→ Tool
- 要「取数」→ Resource
- 要「固定一段指令」→ Prompt

## 3. 一次工具调用的完整链路

```text
1. Client → initialize / server/discover     协商协议版本与能力
2. Client → tools/list                       拿到工具名、描述、inputSchema
3. 模型决定调用 add，生成 {"a": 2, "b": 3}
4. Client → tools/call                       发 JSON-RPC 请求
5. Server 校验参数 → 执行函数 → 包装结果
6. Client ← result {content, structuredContent, isError}
7. Host 把结果放回模型上下文
```

后面遇到的绝大多数问题，都能对应到其中某一步：

- 工具没出现 → 第 2 步（注册/可见性）
- 参数被拒 → 第 5 步（schema/校验）
- 返回看不懂 → 第 6 步（content vs structuredContent）
- 连不上 → 第 1 步（传输/鉴权）

## 4. 传输：stdio 与 HTTP

### stdio

Host 用子进程启动 `python server.py`，通过标准输入输出交换**按行分隔的 JSON-RPC**。

- 优点：零端口、零网络、进程隔离；
- 缺点：一个客户端一个进程，不能多客户端共享；
- 铁律：**stdout 只能有协议报文**，`print()` 会直接破坏连接。

### Streamable HTTP

Server 独立运行，客户端连 `http://host:port/mcp`。

- 优点：多客户端、可远程、可横向扩容；
- 缺点：要处理端口、鉴权、CORS、健康检查；
- 多副本时必须开 `stateless_http=True`，否则会话会飘。

切换传输不改业务代码，只改 `mcp.run(transport=...)`。

## 5. 两个协议纪元

FastMCP 4 会为每个连接协商协议版本：

| | 现代（2026-07-28） | legacy（2025-11-25） |
|---|---|---|
| 会话 | 无会话，每个请求自带上下文 | 有会话 |
| `session_id` | 每次调用不同 | 同一连接相同 |
| `ctx.set_state` | 跨调用重置 | 跨调用保留 |
| `ctx.elicit` | 不可用 | 可用 |
| `on_initialize` 钩子 | 不触发 | 触发 |

这就是为什么 0107 里状态「丢了」、0203 里 `on_initialize` 等不到——不是 bug，是协议设计。

`Client(url, mode="legacy")` 可以强制回到旧协议，用于兼容或调试。

## 6. 结果长什么样

一次 `tools/call` 的结果有四个关键字段：

```json
{
  "content": [{"type": "text", "text": "5"}],
  "structuredContent": {"result": 5},
  "isError": false,
  "_meta": {"fastmcp": {"wrap_result": true}}
}
```

- `content`：给人和模型看的文本/图片块；
- `structuredContent`：给程序解析的对象；
- `isError`：业务失败也是「正常结果」，不是协议错误；
- `_meta`：附加信息，例如服务端版本、运行时元数据。

## 7. 错误的两层

| 层 | 例子 | 客户端看到 |
|---|---|---|
| 协议层 | 鉴权失败、限流、方法不存在 | `MCPError` / 连接错误 |
| 工具层 | 参数校验、业务规则、未捕获异常 | `isError: true` 的结果 |

`raise_on_error=False` 只能接住工具层；协议层仍会抛异常。这个区别在 0104 和 0203 反复出现。

## 8. 安全边界

- 鉴权（401）：你是谁；
- 授权（scope）：你能看到哪些工具；
- 路径安全：资源模板不能穿越目录；
- 工具描述也是模型输入，可能被用于提示注入；
- 默认绑 `127.0.0.1`，公网必须 TLS + Host 白名单。

清单见 [`05-security-checklist.md`](05-security-checklist.md)。

## 9. 术语速查

| 术语 | 含义 |
|---|---|
| MCP | Model Context Protocol，模型与外部能力之间的标准协议 |
| JSON-RPC | MCP 的报文格式，`{jsonrpc, id, method, params}` |
| Transport | stdio / Streamable HTTP / SSE |
| Tool schema | 工具参数的 JSON Schema，模型据此填参 |
| Structured output | `structuredContent`，机器可解析的结果 |
| Host | 宿主应用，负责编排模型与工具 |
| Elicitation | 服务端向用户追问（仅 legacy 可用） |
| Sampling | 服务端借用客户端模型（4.0 已移除） |

## 10. 接下来读什么

- 想动手：[`0101`](../0101-hello-mcp/README.md)
- 想查 API：[`01-api-cheatsheet.md`](01-api-cheatsheet.md)
- 想接宿主：[`02-client-integration.md`](02-client-integration.md)
- 从旧版本迁移：[`03-compat.md`](03-compat.md)
