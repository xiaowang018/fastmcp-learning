# 0108 · 三种连接方式与两个协议纪元

> 目标：搞清 `Client(...)` 到底怎么连服务器，以及 4.x 的「现代 / legacy」协议差异会带来什么实际影响。
> 难度 ★★★ ｜ 前置：0107 ｜ 依赖：无 ｜ 端口：临时端口 ｜ 预计：35 分钟

## 1. 你会学到

- 三种连接方式：进程内、stdio 子进程、HTTP。
- `mode="auto"` 与 `mode="legacy"` 协商出的协议版本不同，**状态语义也不同**。
- 为什么 4.x 默认是「无会话」的，以及它带来的三个可见现象。
- `Client("server.py")` 为什么被弃用。

## 2. 先跑起来

```bash
cd 0108-client-transports
uv run python client.py
```

预期输出（端口随机）：

```text
① 进程内连接 Client(mcp)
   protocol_version = 2026-07-28
   ping = pong

② stdio 子进程 Client(Path('server.py'))
   protocol_version = 2026-07-28
   ping = pong

③ HTTP：后台起 uvicorn，再按 URL 连接
   url = http://127.0.0.1:59047/mcp
   protocol_version = 2026-07-28（auto，协商到现代协议）
   protocol_version = 2025-11-25（强制 legacy）

④ 同一 URL、两种协议下的 session_id
   auto   first=56f5270b second=4c7b443b
          before(second)=None
   legacy first=e5ec453e second=e5ec453e
          before(second)=A
```

```bash
uv run pytest . -q
# 4 passed
```

## 3. 代码地图

| 文件 | 作用 |
|---|---|
| `server.py` | 一个 `ping` 工具、一个状态工具、一个 `/health` 路由；`--http` 切换传输 |
| `client.py` | 依次演示三种连接 + 两种协议模式 |
| `test_server.py` | 四条测试，覆盖 in-memory / stdio / HTTP / 协议差异 |

## 4. 三种连接方式

| 方式 | 写法 | 成本 | 适用 |
|---|---|---|---|
| 进程内 | `Client(mcp)` | 零启动、零序列化 | 单元测试、调试 |
| stdio | `Client(Path("server.py"))` | 拉子进程 | 本地宿主（Claude Desktop / Cursor） |
| HTTP | `Client("http://host:port/mcp")` | 独立服务 | 远程、多客户端、横向扩容 |

`Client(...)` 会根据参数类型自动选传输：

```python
Client(mcp)                       # FastMCP 实例 → 内存传输
Client(Path("server.py"))         # Path → PythonStdioTransport
Client("http://localhost:8108/mcp")  # str/URL → Streamable HTTP
```

**注意**：`Client("server.py")` 在 4.x 会告警，因为字符串被当成 URL。本地脚本必须传 `Path`。

## 5. 现代协议 vs legacy

4.x 会为每个连接协商最合适的协议版本：

| | 现代（`2026-07-28`） | legacy（`2025-11-25`） |
|---|---|---|
| 会话 | 无会话，每个请求自带上下文 | 有会话，连接期间保持 |
| `session_id` | 每次调用不同 | 同一连接内相同 |
| `ctx.set_state` | 跨调用重置 | 跨调用保留 |
| `ctx.elicit` | 不可用（需多轮返回/恢复） | 可用 |
| `on_initialize` 钩子 | 不触发 | 触发 |
| `ctx.sample` | 4.0 已移除 | 也已移除 |

`mode` 的取值：

```python
Client(url)                 # auto：先探测现代协议，失败再回退
Client(url, mode="legacy")  # 只用握手时代协议
```

这就是为什么 0107 里 `state_demo` 第二次调用 `before` 还是 `None`：**不是状态丢了，是现代协议本来就不保留会话**。

## 6. 手动跑 HTTP 模式

```bash
# 终端 1
PORT=8108 uv run python server.py --http

# 终端 2
curl http://127.0.0.1:8108/health
# {"status":"ok"}

uv run fastmcp inspect http://127.0.0.1:8108/mcp
```

`server.py` 用 `--http` 显式切换，是为了让 `Client(Path("server.py"))` 仍然走 stdio。**如果脚本在 `__main__` 里无条件 `run(transport="http")`，stdio 客户端会拉起一个 HTTP 服务，然后一直等不到协议响应。** 这是本地调试最常见的「卡住」原因之一。

## 7. 三种验证方式

**client.py**：一次看全三种连接和两种协议。

**Inspector**：HTTP 模式起来后，在 Inspector 里选 `Streamable HTTP`，填 `http://127.0.0.1:8108/mcp`。

**接入宿主**：本地宿主用 stdio（配置同 0101）；远程宿主用 URL。同一个服务器两种都能服务。

## 8. 常见坑

**① 用字符串传本地脚本**

```python
Client("server.py")          # 被当成 URL，连接失败/告警
Client(Path("server.py"))    # 正确
```

**② `__main__` 无条件起 HTTP**

见第 6 节：stdio 客户端会拉起一个 HTTP 服务，握手永远等不到。

**③ 端口写死导致冲突**

手动运行用固定端口（本案例 8108），自动化测试用 `port=0`（`helpers.serve_http`），不要反过来。

**④ 在测试 fixture 里 `async with Client(...)`**

事件循环生命周期容易错位。fixture 只产出 server 对象，`async with Client` 写在测试函数体内。

**⑤ 以为 `mode="legacy"` 只是「兼容开关」**

它改变的是整个会话语义：状态保留、`elicit` 可用、`on_initialize` 触发。调试状态相关问题时，先确认协议版本。

## 9. 与 2.x / 3.x 的差异

- 4.0 引入协议协商与 `mode` 参数；2.x 只有握手时代协议。
- 4.0 移除 `ctx.sample()` / `ctx.list_roots()`；`ctx.elicit()` 仅 legacy 可用。
- `Client("server.py")` 的字符串形式在 4.x 弃用，5.0 移除。
- 完整差异见 [`docs/03-compat.md`](../docs/03-compat.md)。

## 10. 练习

1. 把 `mode="legacy"` 换成 `mode="2026-07-28"`，看是否还能连上。
2. 用 `client.server_capabilities` 打印两种协议下的能力差异。
3. 给 `server.py` 加一个 `--port` 参数解析，替换环境变量，比较两种写法的可读性。

## 11. 延伸阅读

- FastMCP Client：<https://gofastmcp.com/docs/clients/client>
- 传输：<https://gofastmcp.com/docs/clients/transports>
- 协议协商：<https://gofastmcp.com/docs/getting-started/whats-new>
