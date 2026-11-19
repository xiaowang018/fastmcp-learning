# 0101 · 最小 MCP 服务器：一个工具、一条资源

> 目标：10 分钟内跑通第一个 MCP 服务器，并亲眼看到「发现 → 调用 → 读取」的协议报文。
> 难度 ★☆☆ ｜ 前置：无 ｜ 依赖：无 ｜ 端口：无 ｜ 预计：15 分钟

## 1. 你会学到

- MCP 里的三个角色：**Host（宿主）**、**Client（客户端）**、**Server（服务器）**，以及谁负责拉起进程。
- FastMCP 的最小结构：`FastMCP(name)` + `@mcp.tool` + `@mcp.resource` + `mcp.run()`。
- 三种验证通路：`client.py`（代码）、Inspector（界面）、裸 JSON-RPC（协议）。
- 类型注解如何变成工具的 `inputSchema`，返回注解如何变成 `outputSchema`。

## 2. 先跑起来

在项目根目录执行（一次即可）：

```bash
uv sync
```

然后进入本案例：

```bash
cd 0101-hello-mcp
uv run python client.py
```

预期输出：

```text
服务器：HelloMCP
协议版本：2026-07-28
工具列表：['add']
add 的入参 schema：{'type': 'object', 'additionalProperties': False, 'properties': {'a': {'type': 'integer', 'description': '第一个整数。'}, ...}, 'required': ['a', 'b']}
add(2, 3) = 5
资源 info://server = HelloMCP v1 · 由 FastMCP 4.2 提供
```

跑测试：

```bash
uv run pytest . -q
# 3 passed
```

## 3. 代码地图

| 文件 | 作用 | 关键点 |
|---|---|---|
| `server.py` | 服务端 | `mcp.run()` 默认走 stdio，由宿主拉起进程 |
| `client.py` | 进程内自测 | `Client(mcp)` 直接传实例，不启子进程、不占端口 |
| `test_server.py` | 自动化测试 | 同时覆盖「进程内」和「真实 stdio 子进程」两条通路 |

## 4. 关键概念

### 三个角色

```text
Host（Claude Desktop / Cursor / Claude Code / 你自己的 Agent）
  └─ 内置 Client ──stdio 或 HTTP──> MCP Server（本文件的 server.py）
```

- **Server** 只声明能力：有哪些工具、资源、提示。
- **Client** 负责协议握手、发请求、收结果。
- **Host** 决定什么时候调用哪个工具，并把结果交给模型。

`mcp.run()` 默认是 **stdio**：宿主用子进程方式启动 `python server.py`，通过标准输入输出交换 JSON-RPC。这也是本地 MCP 最常见的形态。

### 三个核心原语

| 原语 | 语义 | 本例 |
|---|---|---|
| Tool | 可执行的动作，可能产生副作用 | `add(a, b)` |
| Resource | 可读取的数据，通常无副作用 | `info://server` |
| Prompt | 可复用的消息模板 | 见 0106 |

判断标准很简单：**要“做事”用 Tool，要“取数”用 Resource，要“给模型一段固定指令”用 Prompt。**

### 类型注解就是协议 schema

```python
@mcp.tool
def add(a: int, b: int) -> int:
    """把两个整数相加。"""
    return a + b
```

FastMCP 在注册时做了四件事：

1. 函数名 `add` → 工具名；
2. docstring 首段 → 工具描述，`Args:` 里的条目 → 参数描述；
3. `a: int` / `b: int` → `inputSchema` 的 `integer` 字段，无默认值 → `required`；
4. `-> int` → `outputSchema`，返回值会被包成 `{"result": 5}`。

所以**改类型注解，就是在改模型看到的工具契约**。这是后面所有案例的基础。

一步步的调用时序（initialize → tools/list → tools/call → result）见 [`docs/00-mcp-in-10-minutes.md`](../docs/00-mcp-in-10-minutes.md) 第 3 节的时序图。

## 5. 三种验证方式

### 方式一：代码（最快）

```bash
uv run python client.py
```

`Client(mcp)` 是进程内连接，适合写测试和调试，不经过序列化，因此**不能**用来验证宿主真实行为。

### 方式二：Inspector（最直观）

```bash
uv run fastmcp dev inspector server.py
```

浏览器会打开 MCP Inspector：左侧能看到 `add` 工具和 `info://server` 资源，点 `Run Tool` 填入 `{"a": 1, "b": 2}` 即可看到结果。

第一次运行会通过 `npx` 下载 Inspector：需要 **Node.js 18+** 与网络。没装 Node 时这一步会失败，改用方式一，或执行 `uv run fastmcp inspect server.py`，不影响后面的学习。

### 方式三：裸 JSON-RPC（最接近真相）

MCP 的 stdio 传输就是**按行分隔的 JSON-RPC**。直接喂三条消息给服务器：

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"raw","version":"0.1"}}}' \
  '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  | uv run python server.py 2>/dev/null | grep -a jsonrpc
```

> Windows：以上命令在 **Git Bash** 中可直接运行；PowerShell 没有 `printf` / `grep`，请直接用方式一，或在 Git Bash 里做这一步。不要因为这条命令报错就怀疑服务器坏了。

会得到（已截断）：

```json
{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-06-18","capabilities":{...},"serverInfo":{"name":"HelloMCP","version":"4.2.1"}}}
{"jsonrpc":"2.0","id":2,"result":{"tools":[{"name":"add","description":"把两个整数相加。","inputSchema":{"type":"object","properties":{"a":{"type":"integer"},"b":{"type":"integer"}},"required":["a","b"]},"outputSchema":{"type":"object","properties":{"result":{"type":"integer"}},"x-fastmcp-wrap-result":true}}]}}
```

看到 `initialize` 和 `tools/list` 的原始响应后，后面遇到的「工具没出现」「参数被拒」都能定位到具体环节。

## 6. 接入真实宿主

Claude Desktop（Windows 配置文件在 `%APPDATA%\Claude\claude_desktop_config.json`，macOS 在 `~/Library/Application Support/Claude/claude_desktop_config.json`）。把 `<仓库目录>` 换成你 clone 下来的绝对路径，例如 `D:/code/fastmcp-learning`：

```json
{
  "mcpServers": {
    "hello-mcp": {
      "command": "<仓库目录>/.venv/Scripts/python.exe",
      "args": ["<仓库目录>/0101-hello-mcp/server.py"]
    }
  }
}
```

macOS / Linux 把 `command` 换成 `<仓库目录>/.venv/bin/python`，其余相同。

跨平台写法（不写死解释器）：

```json
{
  "mcpServers": {
    "hello-mcp": {
      "command": "uv",
      "args": ["--directory", "<仓库目录>", "run", "python", "0101-hello-mcp/server.py"]
    }
  }
}
```

> `<仓库目录>` 是占位符，**不要原样粘贴**；没替换时宿主会报找不到文件。

改完重启宿主，在对话框里说「用 add 算一下 2 加 3」，应该能看到工具调用卡片。

> 更多宿主（Cursor / Claude Code / Inspector）的配置见 [`docs/02-client-integration.md`](../docs/02-client-integration.md)。

## 7. 常见坑

**① 在 `server.py` 里 `print()` 调试**

```text
错误：客户端报 "Unexpected token" 或连接直接断开
原因：stdio 传输的 stdout 只能有 JSON-RPC 报文，print 会污染协议流
解决：日志一律 print(..., file=sys.stderr)，或改用 ctx.info()
```

**② 从项目根目录执行 `uv run python server.py`**

```text
错误：ModuleNotFoundError: No module named 'server'
原因：server.py 在本案例目录里，不在根目录
解决：cd 0101-hello-mcp 后再执行，或写完整路径
```

**③ 用字符串传脚本路径**

```python
Client("server.py")   # 4.x 已弃用：字符串会被当成 URL
Client(Path("server.py"))  # 正确
```

**④ 中文乱码 / 断言失败（Windows）**

```text
原因：子进程默认 cp936
解决：本仓库的 helpers.py 已统一设置 PYTHONUTF8=1，自己起进程时也要带上
```

## 8. 与 2.x / 3.x 的差异

- `@mcp.tool` 在 4.x 可以**不带括号**；2.x 教程里常见 `@mcp.tool()`，两种都合法，但不要混用两种风格。
- `Client("server.py")` 在 4.x 会告警并按 URL 处理，必须传 `Path`。
- 4.x 默认协商**无会话的现代协议**（本例中 `protocol_version` 是 `2026-07-28`）；2.x 教程里的 `ctx.sample()` 已被移除。差异总表见 [`docs/03-compat.md`](../docs/03-compat.md)。

## 9. 练习

1. 给 `add` 增加第三个可选参数 `scale: float = 1.0`，返回 `(a + b) * scale`。重跑 `client.py`，观察 `inputSchema` 的 `required` 和 `default` 怎么变。
2. 把 `-> int` 改成 `-> dict`，返回 `{"sum": a + b, "expression": f"{a}+{b}"}`，用 `client.py` 打印 `result.data` 和 `result.structured_content`，解释两者差异。
3. 用上面的裸 JSON-RPC 命令，把 `tools/list` 换成 `tools/call`，手动调用一次 `add`。

<details>
<summary>练习 3 提示</summary>

```json
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"add","arguments":{"a":2,"b":3}}}
```

</details>

## 10. 延伸阅读

- MCP 协议总览：<https://modelcontextprotocol.io/docs/learn/architecture>
- FastMCP 快速开始：<https://gofastmcp.com/docs/getting-started/quickstart>
- FastMCP Tools：<https://gofastmcp.com/docs/servers/tools>
