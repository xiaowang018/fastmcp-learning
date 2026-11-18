# FastMCP 4.2 从 0 到 1

一套能跑、能测、能查的中文 FastMCP 学习案例库：**22 个编号目录，一个目录一个案例**，每个案例都有代码、md 教程、一键自测和 pytest 测试。

- 版本基线：**FastMCP 4.2.1**（Python ≥ 3.11），代码按 4.x API 编写，文档标注 2.x / 3.x 差异。
- 学习方式：从 `0101` 顺着做，或按角色跳读（见「学习路径」）。
- 质量保证：`uv run pytest` 91 个测试全绿；`uv run python scripts/verify_all.py` 22/22 客户端可跑。
- 零外部依赖：核心案例不联网、不需要 API key；REST 案例用本地 mock，Apps 案例有 HTML 降级。

## 5 分钟开始

```bash
cd fastmcp-learning
uv sync

cd 0101-hello-mcp
uv run python client.py
uv run pytest . -q
```

看到 `add(2, 3) = 5` 就说明环境通了。接下来读 [`0101-hello-mcp/README.md`](0101-hello-mcp/README.md)。

可选依赖（只影响两个案例）：

```bash
uv sync --group api --group apps    # 0206/0302 需要 api，0304 需要 apps
```

> 只装单个组会把环境精确同步成「默认 + 该组」，之前装的另一组会被移除。一次装多个组，或用 `--all-groups`。

## 目录结构

```text
fastmcp-learning/
├─ README.md                 # 本文件：路线图 + 索引
├─ pyproject.toml            # 统一依赖与 pytest 配置
├─ helpers.py                # load_server / free_port / serve_http / serve_asgi
├─ docs/                     # 6 篇横向文档
├─ scripts/verify_all.py     # 逐个跑 22 个 client.py
├─ 01xx-*                    # 基础篇 9 个
├─ 02xx-*                    # 进阶篇 7 个
└─ 03xx-*                    # 实战篇 6 个
```

每个案例固定四件套：

| 文件 | 作用 |
|---|---|
| `README.md` | 教程：目标 / 跑起来 / 代码地图 / 讲解 / 验证 / 踩坑 / 差异 / 练习 |
| `server.py` | 服务端实现，可独立 `python server.py` 启动 |
| `client.py` | 一键自测，`uv run python client.py` 即可验证 |
| `test_server.py` | pytest 测试，覆盖正常、边界、错误与契约 |

部分案例追加 `data/`、`mock_api.py`、`fastmcp.json`、`Dockerfile`。

## 22 个案例

### 01 基础篇：把 MCP 跑起来

| 编号 | 主题 | 核心内容 | 前置 |
|---|---|---|---|
| [0101](0101-hello-mcp/README.md) | 最小服务器 | 三通路对照、stdio、裸 JSON-RPC | — |
| [0102](0102-tool-schema/README.md) | 工具 schema | Annotated/Field、枚举、嵌套模型 | 0101 |
| [0103](0103-tool-output/README.md) | 返回值 | content / structuredContent / ToolResult / Image | 0102 |
| [0104](0104-tool-errors/README.md) | 失败五形态 | 校验、ToolError、异常、超时、取消 | 0103 |
| [0105](0105-resources/README.md) | 资源 | 静态/模板/通配/查询参数、路径安全 | 0103 |
| [0106](0106-prompts/README.md) | 提示 | 三种返回形态、参数校验、角色 | 0102 |
| [0107](0107-context/README.md) | 上下文 | 进度、日志、读资源、请求内状态 | 0105 0106 |
| [0108](0108-client-transports/README.md) | 连接与协议 | in-memory / stdio / HTTP、现代 vs legacy | 0107 |
| [0109](0109-client-advanced/README.md) | 客户端进阶 | 完整调用面、ClientGroup、最小 Host | 0108 |

### 02 进阶篇：工程化

| 编号 | 主题 | 核心内容 | 前置 | 端口/依赖 |
|---|---|---|---|---|
| [0201](0201-http-server/README.md) | HTTP 部署 | run/http_app、/health、CORS、stateless | 0108 | 8101 |
| [0202](0202-lifespan-di/README.md) | 生命周期与 DI | lifespan 资源、清理、Depends | 0107 | — |
| [0203](0203-middleware/README.md) | 中间件 | 钩子层级、配额、响应截断、顺序 | 0201 | — |
| [0204](0204-auth-security/README.md) | 鉴权与安全 | Bearer、scope 可见性、401 三态 | 0201 0203 | 8104 |
| [0205](0205-compose-proxy/README.md) | 组合与代理 | mount/namespace、create_proxy、冲突 | 0109 | — |
| [0206](0206-openapi-fastapi/README.md) | OpenAPI/FastAPI | from_fastapi、RouteMap、收敛 | 0205 | `--group api` |
| [0207](0207-testing/README.md) | 测试 | 五类测试、schema 契约、markers | 0109 0202 | — |

### 03 实战篇：完整项目

| 编号 | 主题 | 核心内容 | 前置 | 端口/依赖 |
|---|---|---|---|---|
| [0301](0301-sqlite-crud/README.md) | SQLite 待办 | lifespan + 锁、分页、状态机、资源 | 01 篇 + 0202 | — |
| [0302](0302-rest-api-wrapper/README.md) | REST 包装 | httpx2、超时/重试、错误映射 | 0202 0206 | `--group api`，8107 |
| [0303](0303-docs-kb/README.md) | 知识库 | Resource + Tool + Prompt、可解释检索 | 0105 0106 0109 | — |
| [0304](0304-apps-ui/README.md) | MCP Apps | `app=True`、Prefab、HTML 降级 | 0103 0201 | `--group apps`，8108 |
| [0305](0305-deploy-install/README.md) | 部署与安装 | fastmcp.json、CLI install、Docker | 0201 0204 | 8109 |
| [0306](0306-agent-host/README.md) | 最小 Host | ClientGroup、确定性 planner、错误恢复 | 0109 0301 0302 | — |

## 学习路径

**三天速成（约 8 小时）**

`0101 → 0102 → 0103 → 0105 → 0107 → 0108 → 0109 → 0201 → 0204 → 0303`

覆盖：工具设计、资源、上下文、连接、鉴权、一个完整知识库。

**一周系统（约 15 小时）**

按 01 → 02 → 03 顺序全做，每篇结束跑一次该篇的 `verify_all.py --only 0X`。

**按角色跳读**

| 角色 | 建议路径 |
|---|---|
| 后端/平台 | 0101-0104 → 0107 → 0201-0205 → 0301/0302/0305 |
| 算法/数据 | 0102 0103 → 0109 → 0206 → 0302/0303/0306 |
| 前端/全栈 | 0105 0106 → 0201 0204 → 0304 |
| 只想接宿主 | 0101 → 0108 → docs/02-client-integration |

## 常用命令

```bash
# 跑单个案例
cd 0104-tool-errors
uv run python client.py
uv run pytest . -q

# 跑某一篇
uv run python scripts/verify_all.py --only 02
uv run pytest 02* -q

# 跑全量
uv run python scripts/verify_all.py
uv run pytest -q
uv run ruff check .

# 查看服务能力
uv run fastmcp inspect 0101-hello-mcp/server.py
uv run fastmcp inspect 0305-deploy-install/fastmcp.json

# 手动起 HTTP
cd 0201-http-server && uv run python server.py
```

## 运行约定

| 项 | 约定 |
|---|---|
| 端口 | 手动运行用固定端口（8101/8104/8107/8108/8109）；测试用 `port=0` |
| 就绪判定 | 轮询 `/health`，不用 `sleep` |
| 编码 | 子进程 `PYTHONUTF8=1` / `PYTHONIOENCODING=utf-8` |
| stdout | 服务端日志只走 stderr；stdout 只能有 JSON-RPC |
| 路径 | `Client(Path("server.py"))`，不传字符串 |
| 超时 | 客户端 10s，pytest 单测 30s |
| 数据 | 案例自带的 `*.db` / `.env` 已在 `.gitignore` |

## 横向文档

| 文档 | 内容 |
|---|---|
| [docs/00-mcp-in-10-minutes.md](docs/00-mcp-in-10-minutes.md) | MCP 协议速览：角色、原语、传输、协议纪元 |
| [docs/01-api-cheatsheet.md](docs/01-api-cheatsheet.md) | FastMCP 4.2 API 速查 |
| [docs/02-client-integration.md](docs/02-client-integration.md) | Inspector / Claude Desktop / Cursor / Claude Code 接入 |
| [docs/03-compat.md](docs/03-compat.md) | 2.x / 3.x → 4.x 差异总表 |
| [docs/04-troubleshooting.md](docs/04-troubleshooting.md) | Windows、编码、端口、stdio 污染排查 |
| [docs/05-security-checklist.md](docs/05-security-checklist.md) | 服务端安全最小清单 |

## 验证状态

```text
uv run pytest -q                          → 91 passed
uv run python scripts/verify_all.py       → 22/22 OK
uv run fastmcp inspect 0101-hello-mcp/... → HelloMCP, 1 tool, 1 resource
```

## 许可与致谢

案例代码可自由用于学习与内部培训。FastMCP 由 Prefect 维护，文档见 <https://gofastmcp.com>。
