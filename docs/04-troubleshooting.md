# 排错手册

> 按「现象 → 原因 → 解决」组织。先看终端，再看宿主；先复现，再改配置。

## 1. 环境与安装

### `uv: command not found` / `无法将“uv”项识别为 cmdlet...`

```text
原因：uv 没装，或装完没有重开终端（PATH 未刷新）
解决：
  1) 按 README §0.2 安装 uv（Windows PowerShell / macOS / Linux 各一条）
  2) 关掉终端再开一个新的
  3) uv --version 能输出版本即可
```

### `ModuleNotFoundError: No module named 'fastmcp'`

```bash
uv sync
uv run python -c "import fastmcp; print('ok')"
```

不要用系统 Python 跑案例；`uv run` 会自动用项目 `.venv`。

### 能 import 但 `dir(fastmcp)` 几乎是空的

```text
原因：只装了 fastmcp 元包，没装 fastmcp-slim 的 client/server extras
解决：uv sync（不要 pip install -U fastmcp 混装）
```

### `No module named 'fastapi'` / `'prefab_ui'`

```bash
uv sync --all-groups
# 或只装需要的（注意会移除另一组）
uv sync --group api
uv sync --group apps
```

注意：`uv sync --group apps` 会把环境精确同步成「默认 + apps」，之前装的 `api` 会被移除。

### `verify_all.py` 跑到 0206 报 `No module named 'fastapi'`

```text
现象：前面案例都 OK，到 0206/0302/0304 显示 FAIL，traceback 指向 fastapi / prefab_ui
原因：只装了默认组，api/apps 组不在环境里
解决：uv sync --all-groups 后重跑；只想验基础篇用
     uv run python scripts/verify_all.py --only 01
```

## 2. 启动与连接

### 服务器启动后「卡住」不动

stdio 模式下这是正常的：它在等 JSON-RPC 输入。用 `fastmcp inspect server.py` 或宿主连接验证。

### `RuntimeError: Client is not connected`

```python
async with Client(mcp) as client:   # 必须在上下文里调用
    await client.call_tool(...)
```

不要把 `Client` 存到全局，也不要在 `async with` 外调用。

### `Client` 连本地脚本失败

```python
Client("server.py")          # 4.x 会当成 URL
Client(Path("server.py"))    # 正确
```

### HTTP 服务连不上

```bash
curl -i http://127.0.0.1:8101/health
```

- 端口被占：换端口或 `port=0`；
- 绑了 `127.0.0.1`，远程访问不到：容器/远程要 `0.0.0.0`；
- CORS 报错：补 `mcp-session-id` 的 expose 与 `Authorization` 的 allow header。

## 3. stdio 与编码

### `Unexpected token` / 连接突然断开

```text
原因：server.py 里有 print() 写到了 stdout，污染 JSON-RPC
解决：日志改 print(..., file=sys.stderr) 或 ctx.info()
```

### 中文乱码 / `UnicodeEncodeError`

```text
原因：Windows 子进程默认 cp936
解决：env 加 PYTHONUTF8=1、PYTHONIOENCODING=utf-8
```

本仓库的 `helpers.py` 已统一处理；自己起子进程时也要带上。

### `asyncio.create_subprocess_exec` 报 NotImplementedError

```text
原因：Windows 上用了 SelectorEventLoop
解决：保持默认 Proactor；不要设置 WindowsSelectorEventLoopPolicy
```

### Windows 提示 `printf` / `grep` 不是内部或外部命令

```text
原因：0101 的裸 JSON-RPC 示例用的是 Unix 命令，PowerShell / cmd 没有
解决：改用 Git Bash 执行；或跳过这一步，用 client.py / fastmcp inspect 验证
```

## 4. 工具与 schema

### 工具没出现在 `tools/list`

- 装饰器写了吗？`@mcp.tool`
- 被 `mcp.disable` / `enable(only=True)` 过滤了吗？
- scope 不足？无权限的工具会被隐藏；
- 挂在子服务器上但没 `mount`？
- 函数有 `*args` / `**kwargs`？不支持。

### 参数被拒：`validation error for call[...]`

```text
原因：类型/约束不匹配（字符串传给了 int、超出 ge/le、enum 不在范围）
解决：看错误里的字段名与 `type=`，改参数或放宽 Field 约束
```

### `data` 不是 dict

```python
result.data.words              # Pydantic 模型
result.structured_content["words"]  # 原始字典
```

### 返回 `None` 或空

- 工具返回 `None` → 空响应；
- 只返回 `Image` → `data` 是 `None`，内容在 `content`；
- 被 `ResponseLimitingMiddleware` 截断 → 看 `content` 文本尾部标记。

## 5. 错误与超时

### `ToolError` 和 `MCPError` 分不清

| 异常 | 来源 | `raise_on_error=False` 能接住吗 |
|---|---|---|
| `ToolError` | 工具内部 | 能 |
| `MCPError` | 协议层（鉴权、限流、方法不存在） | 不能 |

### `Error calling tool 'x'` 但没有细节

```text
原因：mask_error_details=True 且不是 ToolError
解决：看服务端日志；对外需要细节时显式 raise ToolError
```

### 超时

- 工具 `timeout=` 是服务端约束；
- `Client(timeout=)` 是客户端约束；
- 同步函数在线程池里无法被真正中断；
- 长任务用 `task=True` 后台任务。

### 取消后资源没释放

`CancelledError` 是 `BaseException`，用 `try/finally` 清理，不要吞掉。

## 6. 状态与协议

### `ctx.set_state` 跨调用丢了

```text
原因：4.x 现代协议无会话，每次调用独立
解决：改用数据库/文件/Redis，或配置 session_state_store
调试：打印 client.protocol_version，对比 mode="legacy"
```

### `ctx.elicit` 抛错

现代协议不支持；用 `mode="legacy"` 或改多轮返回/恢复模式。

### `on_initialize` 中间件不触发

现代协议走 `server/discover`；改用 `on_discover` 或 `on_message`。

## 7. 测试

### `import file mismatch`

```text
原因：多个同名 test_server.py 且没有 __init__.py
解决：pytest 配置 --import-mode=importlib（本仓库已配置）
```

### 数字目录 import 失败

```text
原因：0101-hello-mcp 不是合法标识符
解决：用 helpers.load_server("0101-hello-mcp")
```

### 测试之间互相污染

- 模块级可变状态（`TICKETS`、`QUOTA`、`STOCK`）要在每个测试前重置；
- 数据库用 `tmp_path` + `monkeypatch.setenv("TASK_DB", ...)`；
- 不要共用固定的 `tasks.db`。

### 测试卡在 HTTP 请求

```text
原因：在事件循环里用同步 urllib 请求自己起的 uvicorn
解决：用 httpx2.AsyncClient，或 asyncio.to_thread
```

## 8. 宿主

### Claude Desktop 看不到服务器

1. 完全退出（托盘）再开；
2. 检查 `claude_desktop_config.json` 是否是合法 JSON；
3. 路径必须是绝对路径；
4. 用 `.venv/Scripts/python.exe`，不是系统 Python；
5. 看 `%APPDATA%\Claude\logs`。

### 工具列表为空

服务器启动即崩溃。先在终端复现：

```bash
.venv/Scripts/python.exe path/to/server.py
```

### Inspector 打不开

`fastmcp dev inspector` 依赖 `npx`，需要 **Node.js 18+** 与网络。

```text
先确认：node --version、npx --version
没装 Node：跳过 Inspector，用 client.py 或下面的 inspect 命令
```

也可以直接连 HTTP：

```bash
uv run fastmcp inspect http://127.0.0.1:8101/mcp
```

## 9. 组合与代理

### 挂载后工具名不对

namespace 会改写：`weather_get_weather`、`weather://weather/cities`。先 `list_tools()` 看真实名字。

### 代理子进程起不来

```text
原因：相对路径按当前工作目录解析
解决：Path(__file__).parent / "child.py"
```

### 同名工具静默丢失

默认「先挂载的赢」。用 `FastMCP(..., on_duplicate="error")` 让冲突暴露。

## 10. 一键自检

```bash
uv run python scripts/verify_all.py
uv run pytest -q
uv run ruff check .
uv run fastmcp inspect 0101-hello-mcp/server.py
```

四条都过，基本可以排除环境与代码问题。
