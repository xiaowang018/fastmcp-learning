# 0204 · 鉴权与授权：401、scope 与工具可见性

> 目标：把「谁能连」和「谁能用什么」分开，并用可断言的测试守住安全边界。
> 难度 ★★★ ｜ 前置：0201 0203 ｜ 依赖：无 ｜ 端口：8104（手动）/ 随机（测试）｜ 预计：35 分钟

## 1. 你会学到

- `StaticTokenVerifier` 的最小用法，以及 token 声明里**必须有 `client_id`**。
- 鉴权三态：无 token → 401，错 token → 401，对 token → 200。
- `require_scopes("write")` 如何让工具对无权限者**直接不可见**。
- 为什么 `/health` 永远不受 MCP 鉴权保护。
- 一份可以逐条断言的安全清单。

## 2. 先跑起来

```bash
cd 0204-auth-security
uv run python client.py
```

预期输出：

```text
① 原始 HTTP 状态码（不带 / 错 / 对 token）
   无 token   → 401
   错误 token → 401
   正确 token → 200

② alice（read + write）
   可见工具 = ['whoami', 'read_data', 'write_data']
   whoami   = {'subject': 'alice', 'client_id': 'cli', 'scopes': ['read', 'write']}

③ bob（只有 read）
   可见工具 = ['whoami', 'read_data']
   调用 write_data → ToolError: Unknown tool: 'write_data'

④ /health 不需要 token
   status=200 body={'status': 'ok'}
```

```bash
uv run pytest . -q
# 3 passed
```

## 3. 代码地图

| 文件 | 作用 |
|---|---|
| `server.py` | 两个 token、三个工具（含 scope 保护）、一个公开 `/health` |
| `client.py` | 原始 401 三态 + 两个身份的可见性对比 |
| `test_server.py` | 断言 401/401/200、scope 隐藏、health 公开 |

## 4. 鉴权 vs 授权

| | 鉴权（Authentication） | 授权（Authorization） |
|---|---|---|
| 回答 | 你是谁？ | 你能做什么？ |
| 失败表现 | HTTP 401 | 工具不可见 / 调用被拒 |
| 本例实现 | `StaticTokenVerifier` | `require_scopes("write")` |

## 5. 最小鉴权配置

```python
auth = StaticTokenVerifier(
    tokens={
        "alice-token": {"sub": "alice", "client_id": "cli", "scopes": ["read", "write"]},
        "bob-token": {"sub": "bob", "client_id": "cli", "scopes": ["read"]},
    }
)

mcp = FastMCP("AuthDemo", auth=auth)
```

**`client_id` 是必填字段**。只写 `sub` 和 `scopes` 会在请求时抛 `KeyError: 'client_id'`，表现为 500，而不是 401 —— 这个坑很隐蔽。

客户端带 token：

```python
Client(url, auth="alice-token")          # 会加 Authorization: Bearer ...
Client(url, auth="Bearer alice-token")   # 也可以显式写
```

## 6. scope 控制的是「可见性」

```python
@mcp.tool(auth=require_scopes("write"))
def write_data(item: str) -> dict: ...
```

bob 只有 `read`：

- `list_tools()` 里**没有** `write_data`；
- 强行调用得到 `ToolError: Unknown tool: 'write_data'`，不是 403。

设计理由：不泄露「存在但你不能用」的信息。前端/模型看到的工具目录本身就是权限视图。

工具内部还能拿到 token：

```python
from fastmcp.server.dependencies import get_access_token

token = get_access_token()
token.subject, token.client_id, token.scopes, token.claims
```

## 7. 安全清单（每条都有对应断言）

| # | 规则 | 本例断言 |
|---|---|---|
| 1 | 无 token 必须 401 | `test_auth_three_states` |
| 2 | 错 token 必须 401 | 同上 |
| 3 | 对 token 才能 200 | 同上 |
| 4 | 无 scope 的工具不可见 | `test_scope_hides_tool` |
| 5 | `/health` 不含敏感信息且免鉴权 | `test_health_is_unprotected` |
| 6 | 默认绑 `127.0.0.1`，不绑 `0.0.0.0` | `server.py` 的 `mcp.run(host=...)` |
| 7 | token 不写进代码库 | 用环境变量替换（练习 1） |
| 8 | 工具描述不泄露内部路径/凭据 | code review 检查 |

还有两条不在本例范围、但必须知道：

- `from_openapi` 自动生成的工具会把上游 API 的凭据透传出去，务必用最小权限的上游 token；
- 工具 description 也是模型输入，可能被恶意服务器用于提示注入。

## 8. 生产升级路径

| 场景 | 方案 |
|---|---|
| 内网原型 | `StaticTokenVerifier` |
| 自建 IdP | `JWTVerifier` / `OIDCProxy` |
| 第三方登录 | GitHub / Google / Auth0 / Azure 等 Provider |
| 多来源 | `MultiAuth` |

静态 token 不适合公网：无法轮换、无法细粒度审计、泄露即永久有效。

## 9. 三种验证方式

**client.py**：原始状态码 + 两个身份对比。

**curl**：

```bash
curl -i -X POST http://127.0.0.1:8104/mcp \
  -H "Authorization: Bearer alice-token" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

**Inspector**：在连接设置里填 `Authorization: Bearer alice-token`，再对比不填时的报错。

## 10. 常见坑

**① token 声明缺 `client_id`**

```text
现象：正确 token 也 500，日志里 KeyError: 'client_id'
原因：StaticTokenVerifier 需要 client_id 构造 AccessToken
解决：{"sub": "...", "client_id": "cli", "scopes": [...]}
```

**② 以为无权限会返回 403**

FastMCP 的 scope 检查是「隐藏工具」，客户端看到的是 `Unknown tool`。写测试时不要断言 403。

**③ 把 token 写进 `server.py`**

本案例为了可运行才写死。真实项目用 `os.environ["MCP_TOKEN"]`，并在 `.gitignore` 里排除 `.env`。

**④ 给 `/health` 加鉴权**

Custom route 不受 MCP auth 中间件保护；要鉴权就挂到 FastAPI 上用 `Depends()`，别指望 `auth=` 能覆盖它。

**⑤ 绑 `0.0.0.0` 做本地开发**

局域网内任何人都能连。默认 `127.0.0.1`，需要对外时再显式改，并配 TLS。

## 11. 与 2.x / 3.x 的差异

- `StaticTokenVerifier` 在 3.x 之后签名稳定；2.x 的 token 结构不同（不要求 `client_id`）。
- `require_scopes` 从 `fastmcp.server.auth` 导入；4.x 的授权检查统一走 `AuthCheck`。
- 4.x 默认启用 Host/Origin 保护，公网部署需显式配置 `allowed_hosts`。
- 完整差异见 [`docs/03-compat.md`](../docs/03-compat.md)。

## 12. 练习

1. 把两个 token 改成从环境变量读取，缺失时启动失败并给出清晰提示。
2. 给 `read_data` 加 `require_scopes("read")`，用无 scope 的第三个 token 验证工具不可见。
3. 用 `JWTVerifier` 替换 `StaticTokenVerifier`，用 PyJWT 自签一个 HS256 token 跑通。

## 13. 延伸阅读

- FastMCP Authentication：<https://gofastmcp.com/docs/servers/auth/authentication>
- Token 校验：<https://gofastmcp.com/docs/servers/auth/token-verification>
- 授权：<https://gofastmcp.com/docs/servers/authorization>
