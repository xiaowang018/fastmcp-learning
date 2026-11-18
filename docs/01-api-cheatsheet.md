# FastMCP 4.2 API 速查

> 只列本仓库用过、并经过验证的 API。完整签名以 <https://gofastmcp.com> 为准。

## 1. 导入

```python
from fastmcp import FastMCP, Client, ClientGroup, Context
from fastmcp.exceptions import ToolError, ResourceError
from fastmcp.tools import ToolResult
from fastmcp.prompts import Message, PromptResult
from fastmcp.resources import ResourceResult, ResourceContent
from fastmcp.utilities.types import Image, Audio, File
from fastmcp.dependencies import Depends
from fastmcp.server import create_proxy
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.server.auth import StaticTokenVerifier, require_scopes
from fastmcp.server.dependencies import get_access_token, get_http_headers
```

## 2. 服务器

```python
mcp = FastMCP(
    name="Demo",
    instructions="给模型看的服务说明",
    lifespan=app_lifespan,           # 进程级资源
    auth=auth,                       # 鉴权
    mask_error_details=True,         # 隐藏内部异常
    on_duplicate="error",            # 重名组件策略
    strict_input_validation=False,   # 是否严格校验
)

mcp.run()                                              # stdio
mcp.run(transport="http", host="127.0.0.1", port=8000) # HTTP
app = mcp.http_app(path="/mcp", stateless_http=True)   # ASGI
```

## 3. 工具

```python
@mcp.tool
def add(a: int, b: int) -> int:
    """一句话描述。

    Args:
        a: 参数说明。
        b: 参数说明。
    """
    return a + b

@mcp.tool(
    name="find_products",
    description="搜索商品",
    tags={"catalog"},
    annotations=ToolAnnotations(readOnlyHint=True),
    timeout=30.0,
    auth=require_scopes("read"),
)
def search(...): ...
```

- 没有默认值 = 必填；有默认值 = 可选。
- `-> int` 会包成 `{"result": n}`；`dict` / Pydantic 自动结构化。
- 不支持 `*args` / `**kwargs`。

## 4. 资源

```python
@mcp.resource("docs://guide", mime_type="text/markdown")
def guide() -> str: ...

@mcp.resource("docs://{name}")
def read_doc(name: str) -> str: ...

@mcp.resource("files://{path*}")
def read_nested(path: str) -> str: ...

@mcp.resource("items://catalog{?limit,tag}")
def catalog(limit: int = 10, tag: str = "all") -> dict: ...
```

- `{param}` 单段；`{param*}` 跨 `/`；`{?a,b}` 查询参数（必须带默认值）。
- 返回 `str` / `bytes` / JSON 原生值 / `ResourceResult`。
- 4.x 默认防路径穿越；业务仍要做根目录检查。

## 5. 提示

```python
@mcp.prompt
def explain(topic: str) -> str: ...

@mcp.prompt
def review(code: str) -> list[Message]:
    return [Message("..."), Message("...", role="assistant")]

@mcp.prompt(name="summarize", tags={"writing"})
def summarize(text: str, max_words: int = 100) -> PromptResult:
    return PromptResult(messages=[Message("...")], meta={"v": 1})
```

## 6. 上下文

```python
@mcp.tool
async def work(ctx: Context) -> dict:
    await ctx.info("日志")
    await ctx.report_progress(1, 3, "第一步")
    resource = await ctx.read_resource("policy://summary")   # ResourceResult
    rule = resource.contents[0].content
    await ctx.set_state("draft", "x")                        # 请求内
    draft = await ctx.get_state("draft")
    return {"request_id": ctx.request_id, "session_id": ctx.session_id}
```

`ctx.sample()` 在 4.0 已移除；`ctx.elicit()` 仅 legacy 连接可用。

## 7. 客户端

```python
async with Client(mcp) as client:                 # 进程内
async with Client(Path("server.py")) as client:   # stdio
async with Client("http://host:8000/mcp") as client:  # HTTP
async with Client(url, mode="legacy") as client:  # 强制旧协议
```

```python
tools = await client.list_tools()          # t.name / t.input_schema
result = await client.call_tool("add", {"a": 1, "b": 2})
result.data                                 # Python 值
result.structured_content                   # 原始对象
result.content                              # 内容块
result.is_error
await client.call_tool("x", {}, raise_on_error=False)
await client.read_resource("docs://guide")  # list[Content]
await client.get_prompt("explain", {"topic": "mcp"})
```

## 8. ClientGroup

```python
group = ClientGroup({"a": Client(server_a), "b": Client(server_b)})
async with group:
    await group.list_tools()                 # a_xxx / b_yyy
    await group.call_tool("b_yyy", {...})
```

## 9. 组合与代理

```python
mcp.mount(child, namespace="weather")        # 工具 → weather_xxx
mcp.mount(create_proxy(Path("other.py")), namespace="other")
mcp.mount(create_proxy("http://host:8000/mcp"), namespace="remote")
```

## 10. 生命周期与依赖

```python
@asynccontextmanager
async def lifespan(server):
    pool = create_pool()
    try:
        yield {"pool": pool}
    finally:
        await pool.close()

def get_settings() -> Settings: ...

@mcp.tool
def t(settings: Settings = Depends(get_settings)) -> dict: ...
```

## 11. 中间件

```python
mcp.add_middleware(LoggingMiddleware())
mcp.add_middleware(TimingMiddleware())
mcp.add_middleware(RateLimitingMiddleware(max_requests_per_second=10, burst_capacity=20))
mcp.add_middleware(ResponseLimitingMiddleware(max_size=500_000))
mcp.add_middleware(ErrorHandlingMiddleware())
mcp.add_middleware(RetryMiddleware(max_retries=3))
```

自定义：

```python
class Audit(Middleware):
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        print(context.message.name, context.message.arguments)
        return await call_next(context)
```

## 12. 鉴权

```python
auth = StaticTokenVerifier(
    tokens={"token": {"sub": "alice", "client_id": "cli", "scopes": ["read"]}}
)
mcp = FastMCP("Secure", auth=auth)

@mcp.tool(auth=require_scopes("write"))
def write(): ...
```

## 13. 错误

```python
from fastmcp.exceptions import ToolError

@mcp.tool
def t() -> str:
    raise ToolError("可操作的业务错误")
```

| 异常 | 客户端看到 |
|---|---|
| `ToolError` | `isError` + 原消息 |
| 普通异常（未掩码） | `isError` + 详情 |
| 普通异常（掩码） | `isError` + 通用文案 |
| 鉴权/限流 | `MCPError`（协议层） |

## 14. CLI

```bash
fastmcp run server.py
fastmcp run fastmcp.json
fastmcp inspect server.py
fastmcp list server.py
fastmcp call server.py add a=1 b=2
fastmcp dev inspector server.py
fastmcp dev apps server.py
fastmcp install mcp-json server.py --name demo
```

## 15. 版本

```python
from importlib.metadata import version
version("fastmcp")       # 4.2.1
```

`fastmcp` 是薄元包，实际实现在 `fastmcp-slim[client,server]`；只用 `uv sync`，不要 `pip install -U`。
