# 0206 · 从 FastAPI / OpenAPI 生成 MCP 服务器

> 目标：先用自动转换看清「镜像 REST」的噪声，再用 `RouteMap` 与手写包装把它收敛成给模型用的工具。
> 难度 ★★★ ｜ 前置：0205 ｜ 依赖：api 组（推荐 `uv sync --all-groups`）｜ 端口：无 ｜ 预计：35 分钟

## 1. 你会学到

- `FastMCP.from_fastapi(app)` 与 `FastMCP.from_openapi(spec, client)` 的用法。
- `operation_id` 如何决定工具名，以及为什么必须显式写。
- `RouteMap` + `MCPType` 把 GET 映射成资源、把写操作排除。
- 官方建议：自动转换适合原型，生产要**收敛**而不是**镜像**。

## 2. 先跑起来

```bash
cd 0206-openapi-fastapi
uv sync --group api        # 安装 fastapi / uvicorn
uv run python client.py
```

> `uv sync --group api` 会把环境精确同步成「默认 + api」，之前装的 `apps` 组会被移除。
> 想一次装齐：`uv sync --all-groups`（根 README §0.4 的推荐做法）。

预期输出（截断）：

```text
① from_fastapi 默认：所有端点 → 工具
   - list_products: 列出商品，可按分类与价格上限过滤。
   - create_product: 创建商品。
   - get_product: 按 ID 获取商品。
   - list_orders: 列出订单。

   list_products(electronics) = [Product(name='机械键盘', price=499.0, ...)]
   404 映射 → ToolError: Error calling tool 'get_product': HTTP error 404 ...

② 自定义 RouteMap：GET 变资源，POST 被排除
   资源      = ['resource://list_products', 'resource://list_orders']
   资源模板  = ['resource://get_product/{product_id}']
   工具      = []
```

```bash
uv run pytest . -q
# 3 passed
```

没装 `fastapi` 时测试会 `skip`，不会让全仓变红。

## 3. 代码地图

| 文件 | 作用 |
|---|---|
| `api.py` | 普通 FastAPI 应用：4 个端点，显式 `operation_id` |
| `server.py` | `mcp`（全转工具）+ `read_mcp`（GET 转资源） |
| `client.py` | 对比两种映射、调用、观察 404 如何变成 `ToolError` |
| `test_server.py` | 断言工具名、过滤/创建、RouteMap 结果 |

## 4. 最小转换

```python
from fastapi import FastAPI
from fastmcp import FastMCP

app = FastAPI()
mcp = FastMCP.from_fastapi(app=app, name="ShopMCP")
```

- 底层走 OpenAPI 规范，所以 FastAPI 的请求体、查询参数、响应模型都会变成 JSON Schema。
- 默认**所有端点 → 工具**。
- 工具名 = `operation_id` 在第一个 `__` 处截断；不写 `operation_id` 就会得到 `list_products_products_get` 这种名字。

```python
@app.get("/products", operation_id="list_products")
def list_products(...): ...
```

## 5. RouteMap：控制映射

```python
from fastmcp.server.providers.openapi import MCPType, RouteMap

read_mcp = FastMCP.from_fastapi(
    app=app,
    route_maps=[
        RouteMap(methods=["GET"], pattern=r".*\{.*\}.*", mcp_type=MCPType.RESOURCE_TEMPLATE),
        RouteMap(methods=["GET"], pattern=r".*", mcp_type=MCPType.RESOURCE),
        RouteMap(mcp_type=MCPType.EXCLUDE),
    ],
)
```

| `MCPType` | 结果 |
|---|---|
| `TOOL` | 可调用工具（默认） |
| `RESOURCE` | 资源，URI 形如 `resource://list_products` |
| `RESOURCE_TEMPLATE` | 带参数的资源模板 |
| `EXCLUDE` | 不暴露 |

自定义映射先匹配，默认映射兜底；**第一个匹配生效**。

## 6. 为什么不要直接镜像 REST

官方明确说：LLM 在「精心设计的 MCP 服务器」上的表现显著好于「自动转换的 OpenAPI 服务器」。

典型问题：

- 20 个端点 = 20 个工具，模型选择困难；
- 端点按资源拆分，但任务往往跨资源（下单要查库存 + 查价格 + 创建订单）；
- REST 的错误码（404/409）对模型不友好，需要翻译成「为什么 + 怎么办」；
- 暴露了内部管理端点（`/admin/*`），有安全风险。

正确做法：

1. 用 `route_maps` 排除内部端点；
2. 把「一个任务」封装成一个工具（如 `place_order(sku, qty)`），内部调多个 REST 端点；
3. 只把稳定的读操作暴露成 Resource；
4. 错误统一成 `ToolError`，附可操作文案。

## 7. 错误映射

FastAPI 的 `HTTPException(404)` 会被转成：

```text
ToolError: Error calling tool 'get_product': HTTP error 404: Not Found - {"detail": "商品 999 不存在"}
```

模型能看到状态码和 detail。生产环境建议在包装层把它翻译成更自然的文案，并开启 `mask_error_details` 防止上游细节泄漏。

## 8. 三种验证方式

**client.py**：对比两种映射。

**Inspector**：连 `server.py`，看自动生成的参数表单；再连 `read_mcp` 看资源列表。

**curl**：FastAPI 本身还能直接跑：`uv run uvicorn api:app --port 8106`，对比 REST 与 MCP 的调用差异。

## 9. 常见坑

**① 没装 fastapi 就 import server.py**

```text
ModuleNotFoundError: No module named 'fastapi'
解决：uv sync --group api
```

**② 返回的是 Pydantic 模型，不是 dict**

`result.data` 是自动生成的模型对象，用 `result.data[0].category`，不要下标。想要原始字典用 `structured_content`。

**③ `operation_id` 重复**

FastAPI 会告警，MCP 侧工具名冲突。每个端点都要唯一。

**④ 把上游 token 写进 OpenAPI 客户端**

`from_openapi` 的 `client` 会带上所有 headers。给最小权限 token，并避免把管理接口暴露给模型。

**⑤ 以为 RouteMap 会改变 REST 行为**

它只影响 MCP 侧的暴露方式，FastAPI 的 HTTP 行为不变。

## 10. 与 2.x / 3.x 的差异

- `from_openapi` 从 2.0 起提供；`route_maps` 从 2.8 起，`route_map_fn` 从 2.5 起。
- 4.x 底层改用 `OpenAPIProvider`，组件命名与 2.x 略有差异。
- 4.x 的 HTTP 客户端是 `httpx2`；2.x 用 `httpx`，自定义 client 时要注意导入。
- 完整差异见 [`docs/03-compat.md`](../docs/03-compat.md)。

## 11. 练习

1. 给 `/admin/stats` 加一个端点，用 `RouteMap(tags={"internal"}, mcp_type=MCPType.EXCLUDE)` 排除它。
2. 写一个手写的 `place_order(product_id, qty)` 工具，内部调用 `get_product` 与 `list_orders`，对比自动生成的工具数量。
3. 用 `from_openapi(openapi_spec=app.openapi(), client=...)` 跑通纯 OpenAPI 路径（不依赖 FastAPI 实例）。

## 12. 延伸阅读

- FastAPI 集成：<https://gofastmcp.com/docs/integrations/fastapi>
- OpenAPI 集成：<https://gofastmcp.com/docs/integrations/openapi>
- RouteMap / MCPType：<https://gofastmcp.com/docs/integrations/openapi>
