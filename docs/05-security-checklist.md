# MCP 服务端安全最小清单

> 每条都应该有一个「会失败」的测试，而不是只写在文档里。对应实现见 0204 / 0105 / 0206 / 0302。

## 1. 鉴权：三态必须分开

```python
assert await status(url, None) == 401
assert await status(url, "wrong") == 401
assert await status(url, "alice-token") == 200
```

- 无 token 与错 token 都必须是 401，不能一个 401 一个 500；
- `StaticTokenVerifier` 的 token 声明必须含 `client_id`，否则会 500；
- 生产用 JWT / OIDC / OAuth，不要长期使用静态 token。

## 2. 授权：默认最小可见

```python
@mcp.tool(auth=require_scopes("write"))
def write_data(...): ...
```

- 无 scope 的工具应**不可见**，而不是「可见但调用报 403」；
- 每个 token 只给完成任务所需的最小 scope；
- 管理类工具单独分组，默认不暴露给模型。

## 3. 绑定地址

```python
mcp.run(transport="http", host="127.0.0.1", port=8101)
```

- 本地开发绑 `127.0.0.1`；
- 容器内需要 `0.0.0.0`，但必须配合网络策略与 TLS；
- 公网部署配置 `allowed_hosts` / `allowed_origins`，防 DNS rebinding。

## 4. 传输与 TLS

- 远程 MCP 一律 HTTPS；
- 反向代理关闭缓冲（SSE/流式必需）；
- CORS 的 `allow_origins` 不用 `*`；
- 暴露 `mcp-session-id` 时确认前端只从可信域访问。

## 5. 路径安全

```python
path = (DOCS_DIR / filename).resolve()
if not path.is_relative_to(DOCS_DIR) or not path.is_file():
    raise ResourceError("文档不存在")
```

- 4.x 框架会拦 `../`、绝对路径、空字节；
- 业务仍要做白名单或根目录检查（纵深防御）；
- 不要用 `os.path.join` 直接拼用户输入。

## 6. 工具面收敛

- 不要把所有 REST 端点自动暴露给模型（0206）；
- 写操作单独标注 `destructiveHint=True`；
- 删除/转账/发布等高风险动作需要二次确认或人工审批；
- 内部管理端点用 `RouteMap(..., MCPType.EXCLUDE)` 排除。

## 7. 错误信息

```python
mcp = FastMCP("Prod", mask_error_details=True)
```

- 对外只返回「为什么 + 怎么办」的 `ToolError`；
- 堆栈、SQL、连接串、文件路径只进服务端日志；
- 上游 API 的 401/403 不要原样透传凭据信息。

## 8. 输入与提示注入

- 工具描述、资源内容、上游返回值都会进入模型上下文；
- 资源内容可能包含「忽略之前的指令」这类注入，Host 侧要做隔离；
- 不要把密钥、内部 URL、员工信息写进工具描述；
- 对模型生成的参数做 schema 校验，不信任「模型不会传坏值」。

## 9. SSRF 与外部请求

- `from_openapi` / 手写包装层只访问白名单域名；
- 禁止用户可控的完整 URL（`fetch(url)` 是高风险工具）；
- 内网元数据地址（169.254.169.254）、localhost、file:// 要显式拦截；
- 上游凭据用最小权限，并限制可访问的资源范围。

## 10. 密钥与配置

- token / API key 从环境变量或密钥管理读取；
- `.env`、`*.db`、日志已在 `.gitignore`；
- 不在代码、工具描述、错误消息里出现密钥；
- 定期轮换，支持多密钥并行（灰度）。

## 11. 日志与审计

- 记录：谁（subject/client_id）、调了什么、参数摘要、结果状态、耗时；
- 不记录：完整 token、密码、身份证、完整请求体；
- 审计中间件放最外层（0203），保证被限流/拒绝的请求也有记录；
- 日志保留期与脱敏策略按合规要求执行。

## 12. 资源与性能边界

- 列表类工具必须分页（`limit` 上限 + `total`）；
- 单条响应限制大小（`ResponseLimitingMiddleware`）；
- 长任务用后台任务，不要让 HTTP 连接挂几分钟；
- 超时分层：客户端、服务端、上游各自配置。

## 13. 部署

- 容器用非 root 用户；
- 固定依赖版本，提交 `uv.lock`；
- `/health` 只返回状态，不泄露版本细节；
- 多副本开 `stateless_http=True`；
- 生产前跑一遍：`pytest`、`verify_all.py`、`ruff`、依赖审计。

## 14. 上线前自检表

```text
[ ] 无 token / 错 token / 对 token 三态断言通过
[ ] 无 scope 的工具不可见
[ ] 资源路径穿越被拒
[ ] 高风险工具带 destructiveHint 或审批
[ ] 错误信息已掩码，堆栈只在服务端
[ ] 默认绑 127.0.0.1，公网有 TLS 与 Host 白名单
[ ] 工具列表经过收敛，没有内部管理端点
[ ] 密钥来自环境变量，仓库无明文
[ ] 审计日志脱敏且覆盖所有调用
[ ] 分页、响应大小、超时均有上限
```
