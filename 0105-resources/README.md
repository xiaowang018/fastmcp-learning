# 0105 · 资源：静态、模板、通配、查询参数

> 目标：把「读数据」从工具里拆出来，用 Resource 表达，并守住路径安全边界。
> 难度 ★★☆ ｜ 前置：0103 ｜ 依赖：无 ｜ 端口：无 ｜ 预计：25 分钟

## 1. 你会学到

- 四种资源写法：静态 `docs://guide`、模板 `docs://{filename}`、通配 `files://{path*}`、查询参数 `items://catalog{?limit,tag}`。
- `mime_type` 与 `ResourceResult` 多内容项怎么用。
- 「资源 vs 工具」的三条判定标准。
- FastMCP 4 的路径穿越防护，以及为什么还要自己做根目录检查。

## 2. 先跑起来

```bash
cd 0105-resources
uv run python client.py
```

预期输出（截断）：

```text
静态资源：['docs://guide', 'report://summary']
模板资源：['docs://{filename}', 'files://{path*}', 'items://catalog{?limit,tag}']

--- 静态 docs://guide ---
# 资源使用指南

--- 通配 files://advanced/tips ---
# 进阶技巧

--- 查询参数 items://catalog?limit=1&tag=mcp ---
{"total": 2, "items": [{"id": 1, "name": "MCP \u5165\u95e8", "tag": "mcp"}]}

--- 路径穿越 files://../secret ---
已拒绝（MCPError）：Resource not found: 'files://../secret'
```

```bash
uv run pytest . -q
# 7 passed
```

## 3. 代码地图

| 文件 | 作用 |
|---|---|
| `server.py` | 五种资源声明 + 根目录包含检查 |
| `client.py` | 列出资源/模板，逐个读取，演示穿越被拒 |
| `test_server.py` | 覆盖静态、模板、通配、查询参数、多内容、安全 |
| `data/docs/` | 被暴露的 Markdown 目录 |
| `data/secret.txt` | 故意放在目录外，用来验证防护 |

## 4. 资源 vs 工具：三条判定

| 判据 | 选 Resource | 选 Tool |
|---|---|---|
| 有副作用吗？ | 无（只读） | 有（写库、发请求、改状态） |
| 值得被缓存/引用吗？ | 是，URI 可复用 | 否，每次参数不同 |
| 数据体积大吗？ | 大（原文、文件、页面） | 小（摘要、状态码） |

同一个知识库，常常**两者都要**：Resource 暴露原文，Tool 做检索（见 0303）。

## 5. 四种写法

### 静态资源

```python
@mcp.resource("docs://guide", mime_type="text/markdown")
def guide() -> str:
    return "# 资源使用指南\n..."
```

没有参数，URI 固定，适合「服务自述」「配置说明」「固定词表」。

### 模板资源

```python
@mcp.resource("docs://{filename}", mime_type="text/markdown")
def read_doc(filename: str) -> str:
    path = (DOCS_DIR / filename).with_suffix(".md").resolve()
    if not path.is_relative_to(DOCS_DIR) or not path.is_file():
        raise ResourceError(f"文档不存在：{filename}")
    return path.read_text(encoding="utf-8")
```

- `{filename}` 只匹配**单个路径段**，不跨 `/`。
- 参数名必须与函数签名一致。
- 一定要做 `resolve()` + `is_relative_to()` 检查，即使框架已经拦了一层。

### 通配资源

```python
@mcp.resource("files://{path*}")
def read_nested(path: str) -> str:
    ...
```

`{path*}` 可以跨 `/`，所以 `files://advanced/tips` 能命中 `data/docs/advanced/tips.md`。适合目录树、仓库文件、文档站。

### 查询参数

```python
@mcp.resource("items://catalog{?limit,tag}")
def catalog(limit: int = 10, tag: str = "all") -> dict:
```

- 查询参数必须是**带默认值**的可选参数；
- 客户端写 `items://catalog?limit=1&tag=mcp`；
- 支持 `int/float/bool/str` 自动转换；
- 列表参数要用 `{?tags*}`。

## 6. `mime_type` 与多内容

```python
@mcp.resource("report://summary")
def summary() -> ResourceResult:
    return ResourceResult(
        contents=[
            ResourceContent("# 摘要", mime_type="text/markdown"),
            ResourceContent({"count": 3}, mime_type="application/json"),
        ],
        meta={"generated_by": "0105"},
    )
```

- 返回 `str` → 默认 `text/plain`；返回 `dict/list` → JSON 文本，但 `mime_type` **不会自动变成** `application/json`，要显式声明。
- 返回 `bytes` → Base64 编码的 Blob，记得指定 `image/png` 之类的 MIME。
- 一条资源可以返回多个内容项，客户端会收到一个列表。

## 7. 路径安全

FastMCP 4 默认启用 `ResourceSecurity`，在**进入你的函数之前**就拒绝：

- `../secret`、裸 `..`、`a/../../b`；
- 绝对路径；
- 空字节；
- `..%2F` 这类编码变形。

但框架的拦截不能替代业务校验。正确姿势是「双层」：

```python
path = (DOCS_DIR / filename).resolve()
if not path.is_relative_to(DOCS_DIR) or not path.is_file():
    raise ResourceError("文档不存在")
```

需要放宽时（例如 `git://diff/{ref}` 允许 `HEAD~3..HEAD`）：

```python
from fastmcp.resources import ResourceSecurity

@mcp.resource("git://diff/{ref}", security=ResourceSecurity(exempt_params={"ref"}))
```

## 8. 三种验证方式

**client.py**：一次读全五种资源。

**Inspector**：`uv run fastmcp dev inspector server.py`，在 Resources 标签里能看到静态资源与模板，点 `Read` 即可。

**接入宿主**：资源通常不会自动进入模型上下文，需要宿主支持「附加资源」。Claude Desktop 里可以用 `@` 引用资源（视版本而定）；更稳的方式是让工具内部 `ctx.read_resource()`（见 0107）。

## 9. 常见坑

**① URI 里的参数名和函数参数不一致**

```text
错误：Resource template 'docs://{filename}' parameter 'filename' not found in function signature
解决：{filename} ↔ def read_doc(filename: str)
```

**② 查询参数没给默认值**

```text
错误：Query parameter 'limit' must have a default value
解决：def catalog(limit: int = 10, ...)
```

**③ 以为 `{filename}` 能读子目录**

单段参数不跨 `/`。要读 `advanced/tips.md`，用 `{path*}` 或 `files://{dir}/{name}`。

**④ 返回 dict 却没声明 `mime_type="application/json"`**

客户端拿到的是 `text/plain`，依赖 MIME 做解析的逻辑会失效。

**⑤ 把写操作塞进 Resource**

Resource 的语义是只读。宿主可能缓存、预取、批量读取，写操作会变得不可预期。

## 10. 与 2.x / 3.x 的差异

- `ResourceSecurity` 与路径穿越防护是 4.0 新增，2.x/3.x 需要自己校验。
- 查询参数 `{?limit,tag}` 从 2.13 起支持；更早版本只能用路径参数。
- `ResourceResult` / `ResourceContent` 在 4.x 从 `fastmcp.resources` 导入。
- 完整差异见 [`docs/03-compat.md`](../docs/03-compat.md)。

## 11. 练习

1. 增加一条 `docs://{filename}{?raw}`，`raw=True` 时返回原文，否则返回去掉首行标题的摘要。
2. 用 `DirectoryResource` 把 `data/docs/` 整个目录暴露成一条资源，对比它与 `{path*}` 的差异。
3. 故意把 `read_doc` 的 `is_relative_to` 检查删掉，用 `files://` 之外的方式构造一个能穿越的 URI，验证框架是否仍能拦住。

## 12. 延伸阅读

- FastMCP Resources：<https://gofastmcp.com/docs/servers/resources>
- RFC 6570 URI Template：<https://www.rfc-editor.org/rfc/rfc6570>
