# 0305 · 部署与安装：fastmcp.json、CLI 与容器

> 目标：把「能跑」变成「能交付」：一份声明式配置、四种宿主安装、一个容器镜像。
> 难度 ★★★ ｜ 前置：0201 0204 ｜ 依赖：无（Docker 可选）｜ 端口：8109 ｜ 预计：35 分钟

## 1. 你会学到

- `fastmcp.json` 的三块结构：source / environment / deployment。
- `fastmcp run`、`inspect`、`install` 的用法与优先级。
- 如何给 Claude Desktop / Cursor / Claude Code 生成配置而不手写路径。
- Dockerfile 里的 `--skip-env` 与 `/health` 探针。

## 2. 先跑起来

```bash
cd 0305-deploy-install
uv run python client.py
```

关键输出：

```text
--- fastmcp.json ---
{
  "source": {"type": "filesystem", "path": "server.py", "entrypoint": "mcp"},
  "deployment": {"transport": "http", "host": "127.0.0.1", "port": 8109, ...}
}

MCP 调用：server_time = 2026-11-18T11:35:13
          roll_dice  = {'sides': 20, 'value': 15}
/health = {'status': 'ok', 'version': 'dev'}

--- 生成宿主配置（只打印，不改本机）---
{
  "deploy-demo": {
    "command": "uv",
    "args": ["run", "--with", "fastmcp", "fastmcp", "run", ".../server.py"]
  }
}
```

```bash
uv run pytest . -q
# 3 passed
```

手动运行：

```bash
uv run fastmcp run fastmcp.json
# 浏览器/客户端连 http://127.0.0.1:8109/mcp
```

## 3. 代码地图

| 文件 | 作用 |
|---|---|
| `server.py` | 两个工具 + `/health` |
| `fastmcp.json` | 声明源码、入口、HTTP 部署参数与环境变量 |
| `Dockerfile` | 自包含镜像，`--skip-env` 跳过 uv 环境创建 |
| `client.py` | 校验配置、跑服务、生成宿主配置 |
| `test_server.py` | 配置字段、工具、健康检查、容器文件 |

## 4. `fastmcp.json` 三块

```json
{
  "$schema": "https://gofastmcp.com/public/schemas/fastmcp.json/v1.json",
  "source": {"type": "filesystem", "path": "server.py", "entrypoint": "mcp"},
  "environment": {"type": "uv", "python": ">=3.11"},
  "deployment": {
    "transport": "http", "host": "127.0.0.1", "port": 8109,
    "path": "/mcp", "log_level": "INFO",
    "env": {"APP_VERSION": "1.0.0"}
  }
}
```

- **source**（必填）：`path` 相对配置文件解析；`entrypoint` 可省略，自动找 `mcp` / `server` / `app`。
- **environment**：`type: uv` 时可用 `python` / `dependencies` / `requirements` / `project` / `editable`。省略则用当前环境。
- **deployment**：传输、绑定地址、端口、路径、日志级别、环境变量、工作目录、启动参数。

严格 JSON：不能有注释和尾随逗号。

## 5. CLI 速查

```bash
uv run fastmcp run                     # 自动找当前目录 fastmcp.json
uv run fastmcp run fastmcp.json        # 显式指定
uv run fastmcp run server.py           # 直接跑文件（找 mcp/server/app）
uv run fastmcp inspect fastmcp.json    # 查看能力
uv run fastmcp dev inspector server.py # Inspector 调试
uv run fastmcp install mcp-json server.py --name deploy-demo   # 只打印配置
```

命令行参数**覆盖**配置文件：

```bash
uv run fastmcp run fastmcp.json --port 8200 --transport http
```

## 6. 四种宿主安装

```bash
fastmcp install claude-desktop server.py --name deploy-demo
fastmcp install cursor server.py --name deploy-demo
fastmcp install claude-code server.py --name deploy-demo
fastmcp install mcp-json server.py --name deploy-demo   # 只输出 JSON
```

- `install` 会**修改本机配置**（除 `mcp-json`），所以本仓库把它标为手动步骤，不放进自动化测试。
- Windows 路径含空格时，配置里的 `args` 要保留引号。
- 安装后在宿主里重启/刷新 MCP 列表。

## 7. 容器化

```dockerfile
FROM python:3.13-slim
RUN pip install --no-cache-dir "fastmcp>=4.2.1,<5"
WORKDIR /app
COPY server.py fastmcp.json ./
EXPOSE 8109
CMD ["fastmcp", "run", "fastmcp.json", "--skip-env", "--transport", "http", "--host", "0.0.0.0", "--port", "8109"]
```

```bash
docker build -t fastmcp-demo .
docker run --rm -p 8109:8109 fastmcp-demo
curl http://127.0.0.1:8109/health
```

要点：

- 容器内已装依赖，`--skip-env` 避免再建一个 uv 环境；
- `host=0.0.0.0` 才能被宿主机访问；
- 生产用非 root 用户、固定版本、健康探针。

## 8. 三种验证方式

**client.py**：配置 + 调用 + 生成宿主 JSON。

**fastmcp inspect**：`uv run fastmcp inspect fastmcp.json`，确认能力与版本。

**容器**：`docker build` 后 `curl /health`；Docker 不可用时跳过。

## 9. 常见坑

**① 文件名不是精确的 `fastmcp.json`**

`dev.fastmcp.json` 不会被自动发现，必须显式传路径。

**② 以为 `deployment.env` 会影响进程外**

`fastmcp.json` 的 env 只在 `fastmcp run` 启动时注入。本案例用 `serve_http` 直接起服务时，`APP_VERSION` 仍是 `dev`。

**③ `install` 改了本机配置却不知道**

`claude-desktop` / `cursor` / `claude-code` 会写配置文件。先 `mcp-json` 看输出，确认后再装。

**④ 容器里绑 127.0.0.1**

宿主机访问不到。容器内必须 `0.0.0.0`，再用端口映射。

**⑤ 生产还用 `uv run` 动态装依赖**

启动慢、不可复现。镜像里预装依赖，运行时 `--skip-env`。

**⑥ 忘记 `/health`**

负载均衡/容器平台无法判断就绪，流量会打到还没启动完的实例。

## 10. 与 2.x / 3.x 的差异

- `fastmcp.json` 从 2.12 起支持；4.x 字段基本兼容。
- `install` 的子命令在 4.x 扩展了 Gemini CLI / Goose / Claude Code。
- 4.x 的 `run` 支持更多 server spec（URL、MCPConfig、fastmcp.json）。
- 完整差异见 [`docs/03-compat.md`](../docs/03-compat.md)。

## 11. 练习

1. 给 `fastmcp.json` 加 `environment.dependencies`，用 `fastmcp run fastmcp.json` 观察首次启动的环境创建。
2. 把 `deployment.env.APP_VERSION` 改成 `${APP_VERSION}`，用环境变量注入，验证 `/health` 返回值。
3. 写一个多阶段 Dockerfile，把依赖层与代码层分离，比较构建缓存命中。

## 12. 延伸阅读

- 运行服务器：<https://gofastmcp.com/docs/deployment/running-server>
- 项目配置：<https://gofastmcp.com/docs/deployment/server-configuration>
- CLI：<https://gofastmcp.com/docs/cli/overview>
