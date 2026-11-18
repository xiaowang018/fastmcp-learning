# 接入宿主：Inspector / Claude Desktop / Cursor / Claude Code

> 目标：让本仓库的服务器出现在你常用的 MCP 客户端里。以下路径以 Windows 为例，其他平台替换为对应路径。

## 1. 先确认服务器能独立运行

```bash
cd 0101-hello-mcp
uv run python server.py
```

stdio 模式下它会安静地等待输入，这是正常的。按 `Ctrl+C` 退出。

更快的确认方式：

```bash
uv run fastmcp inspect 0101-hello-mcp/server.py
```

能看到 `Tools: 1` 就说明服务器本身没问题，接下来是宿主配置。

## 2. 绝对路径准备

宿主不会继承你当前终端的工作目录，配置里必须写**绝对路径**：

```text
项目根：C:/Users/Administrator/WorkBuddy/2026-11-18-10-44-56/fastmcp-learning
Python：C:/Users/Administrator/WorkBuddy/2026-11-18-10-44-56/fastmcp-learning/.venv/Scripts/python.exe
```

Windows 路径用正斜杠 `/` 最稳，避免 JSON 转义问题。

## 3. MCP Inspector（最快）

```bash
cd 0101-hello-mcp
uv run fastmcp dev inspector server.py
```

- 浏览器打开后，左侧是 Tools / Resources / Prompts；
- 点工具、填参数、Run，右侧看结果与 `structuredContent`；
- 适合调试 schema、错误文案、资源 MIME。

第一次运行会通过 `npx` 下载 Inspector，需要网络。

## 4. Claude Desktop

配置文件：

```text
%APPDATA%\Claude\claude_desktop_config.json
```

内容：

```json
{
  "mcpServers": {
    "hello-mcp": {
      "command": "C:/Users/Administrator/WorkBuddy/2026-11-18-10-44-56/fastmcp-learning/.venv/Scripts/python.exe",
      "args": [
        "C:/Users/Administrator/WorkBuddy/2026-11-18-10-44-56/fastmcp-learning/0101-hello-mcp/server.py"
      ]
    }
  }
}
```

步骤：

1. 完全退出 Claude Desktop（托盘也要退）；
2. 重新打开；
3. 在输入框的「工具/连接器」图标里确认 `hello-mcp` 已连接；
4. 输入「用 add 算一下 2 加 3」。

常见问题：

- 服务器没出现：JSON 语法错误、路径不存在、Python 解释器不对；
- 出现但工具为空：服务器启动即崩溃，先用 `inspect` 在终端复现；
- 中文乱码：配置里加 `"env": {"PYTHONUTF8": "1"}`。

## 5. Cursor

项目级配置（推荐，随仓库走）：

```text
<项目>/.cursor/mcp.json
```

```json
{
  "mcpServers": {
    "fastmcp-learning": {
      "command": "uv",
      "args": [
        "--directory",
        "C:/Users/Administrator/WorkBuddy/2026-11-18-10-44-56/fastmcp-learning",
        "run",
        "python",
        "0104-tool-errors/server.py"
      ]
    }
  }
}
```

用 `uv --directory` 的好处：不写死 Python 路径，依赖由项目统一管理。改完在 Cursor 的 MCP 面板点刷新。

## 6. Claude Code

命令行安装：

```bash
cd C:/Users/Administrator/WorkBuddy/2026-11-18-10-44-56/fastmcp-learning
fastmcp install claude-code 0101-hello-mcp/server.py --name hello-mcp
```

或手动：

```bash
claude mcp add hello-mcp -- \
  "C:/Users/Administrator/WorkBuddy/2026-11-18-10-44-56/fastmcp-learning/.venv/Scripts/python.exe" \
  "C:/Users/Administrator/WorkBuddy/2026-11-18-10-44-56/fastmcp-learning/0101-hello-mcp/server.py"
```

验证：

```bash
claude mcp list
```

在会话里用 `/mcp` 查看连接状态。

## 7. 生成配置但不改本机

```bash
cd 0305-deploy-install
uv run fastmcp install mcp-json server.py --name deploy-demo
```

会输出一段 `mcpServers` JSON，可粘贴到任意宿主。`mcp-json` 不会修改任何配置文件，适合先审查再安装。

## 8. HTTP 服务器接入

远程/HTTP 服务器不需要 `command`，用 URL：

```json
{
  "mcpServers": {
    "http-demo": {
      "url": "http://127.0.0.1:8101/mcp"
    }
  }
}
```

带鉴权时加 header：

```json
{
  "mcpServers": {
    "secure-demo": {
      "url": "http://127.0.0.1:8104/mcp",
      "headers": {"Authorization": "Bearer alice-token"}
    }
  }
}
```

先手动确认服务可用：

```bash
cd 0201-http-server && uv run python server.py
curl http://127.0.0.1:8101/health
```

## 9. 排错顺序

```text
1. 终端能跑吗？        uv run python server.py / fastmcp inspect
2. 路径是绝对路径吗？  宿主不继承 cwd
3. 解释器对吗？        .venv/Scripts/python.exe，不是系统 Python
4. JSON 合法吗？       用 json.loads 校验，不要有尾随逗号
5. 宿主重启了吗？      托盘退出再开
6. 看宿主日志           Claude Desktop: %APPDATA%\Claude\logs
```

## 10. 安全提醒

- 宿主配置里不要写长期有效的生产 token；
- 远程 MCP 用 HTTPS，并限制 `allowed_hosts`；
- 安装第三方 MCP 服务器前，先看它会读写哪些文件/网络；
- `install` 会修改本机配置，执行前先 `mcp-json` 预览。
