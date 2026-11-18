# 0102 · 工具 schema：让模型看得懂、调得对

> 目标：同一个搜索需求写三版签名，亲眼看到 JSON Schema 从「只有类型」变成「有描述、有约束、有枚举」。
> 难度 ★★☆ ｜ 前置：0101 ｜ 依赖：无 ｜ 端口：无 ｜ 预计：25 分钟

## 1. 你会学到

- `@mcp.tool` 如何把函数签名、docstring、默认值翻译成 `inputSchema`。
- 三种补信息的方式：docstring 的 `Args:`、`Annotated[..., Field(...)]`、Pydantic 模型。
- 必填 vs 可选、`Literal` / `Enum` 枚举、数值范围、嵌套对象在 schema 里的样子。
- 参数校验失败时，客户端收到的是 `ToolError`，不是裸的 `ValidationError`。

## 2. 先跑起来

```bash
cd 0102-tool-schema
uv run python client.py
```

输出会依次打印三个工具的完整 JSON Schema，然后调用三次，最后演示一次校验失败：

```text
工具：search_basic
{
  "properties": {
    "query": {"type": "string"},
    "limit": {"default": 5, "type": "integer"}
  },
  "required": ["query"]
}
...
query 太短 → 1 validation error for call[search_annotated]
query
  String should have at least 2 characters [type=string_too_short, ...]
```

```bash
uv run pytest . -q
# 3 passed
```

## 3. 代码地图

| 文件 | 作用 |
|---|---|
| `server.py` | 三个工具：`search_basic` / `search_annotated` / `search_structured` |
| `client.py` | 打印三份 schema、调用三次、触发一次校验失败 |
| `test_server.py` | 把「schema 必须包含什么」写成断言 |

## 4. 三层写法对比

### 第一层：裸类型（能用，但模型只能猜）

```python
@mcp.tool
def search_basic(query: str, limit: int = 5) -> list[dict]:
    """按关键词搜索文章（基础版：只有类型注解）。"""
```

生成的 schema：

```json
{
  "properties": {
    "query": {"type": "string"},
    "limit": {"default": 5, "type": "integer"}
  },
  "required": ["query"]
}
```

问题：模型不知道 `query` 是标题还是全文，也不知道 `limit` 能不能填 1000。**描述缺失是工具误调用第一大原因。**

### 第二层：`Annotated` + `Field`（推荐默认写法）

```python
@mcp.tool
def search_annotated(
    query: Annotated[str, Field(description="搜索关键词，至少 2 个字符", min_length=2)],
    limit: Annotated[int, Field(description="返回条数，1-20", ge=1, le=20)] = 5,
    sort: Annotated[Literal["relevance", "newest"], Field(description="排序方式")] = "relevance",
) -> dict:
```

对应 schema 多了三样东西：

```json
{
  "query": {"type": "string", "description": "搜索关键词，至少 2 个字符", "minLength": 2},
  "limit": {"type": "integer", "description": "返回条数，1-20", "minimum": 1, "maximum": 20, "default": 5},
  "sort": {"type": "string", "enum": ["relevance", "newest"], "default": "relevance"}
}
```

- `description`：给模型看的自然语言说明，**写清楚“干什么 + 边界”**。
- `ge/le/min_length`：既写进 schema，也在运行时真正校验。
- `Literal` / `Enum`：把可选值收窄成枚举，显著降低乱填概率。

### 第三层：Pydantic 模型（复杂参数收口）

```python
class SearchRequest(BaseModel):
    query: str = Field(min_length=2, description="搜索关键词")
    tags: list[str] = Field(default_factory=list, description="标签过滤")
    date_range: DateRange | None = Field(default=None, description="可选的时间范围")
    limit: int = Field(default=5, ge=1, le=20)

@mcp.tool
def search_structured(request: SearchRequest) -> dict:
```

调用时必须传对象，不能传 JSON 字符串：

```python
{"request": {"query": "mcp", "tags": ["mcp"]}}          # 正确
{"request": "{\"query\": \"mcp\"}"}                      # 错误：会被当成字符串
```

参数超过 5 个、或出现「一组强相关参数」时，用模型收口比平铺更清晰。FastMCP 默认会解引用 `$ref`，把嵌套模型**内联**进 schema，兼容不喜欢 `$ref` 的客户端。

## 5. docstring 也能写参数说明

除了 `Field`，FastMCP 还解析 Google / NumPy / Sphinx 风格的 docstring：

```python
@mcp.tool
def search(query: str, limit: int = 5) -> list[dict]:
    """按关键词搜索。

    Args:
        query: 搜索关键词。
        limit: 返回条数。
    """
```

优先级：`Annotated` / `Field` 的显式描述 **高于** docstring。两种都写时以显式描述为准。

## 6. 三种验证方式

**client.py**：直接打印 schema，最快。

**Inspector**：

```bash
uv run fastmcp dev inspector server.py
```

在工具详情里能看到格式化的参数表单，试试把 `limit` 填 `0`，会看到校验错误。

**接入宿主**：配置方式同 0101，把 `args` 里的路径换成 `0102-tool-schema/server.py`。在对话里说「帮我搜 mcp，只要最新一条」，观察模型是否会正确带上 `sort=newest`。

## 7. 常见坑

**① 以为写了 `description` 模型就一定会遵守**

描述只是提示，不是强制。真正的约束要靠 `ge/le/min_length/enum`，运行时校验才是硬边界。

**② Pydantic 模型参数传了字符串化 JSON**

```text
错误：Input should be a valid dictionary or instance of SearchRequest
原因：MCP 客户端把参数当 JSON 对象传，模型参数也必须是对象
解决：{"request": {"query": "..."}}，不要 json.dumps 后再传
```

**③ 可选参数写成了必填**

没有默认值 = 必填。想让参数可省略，必须给默认值（`= None` 或具体值）。

**④ 工具名冲突**

同名工具默认 `on_duplicate="warn"` 并替换。生产环境建议 `FastMCP(..., on_duplicate="error")`，让冲突在启动时暴露。

## 8. 与 2.x / 3.x 的差异

- `Annotated[str, "描述"]` 的字符串简写从 2.11 起支持；4.x 继续可用，但复杂约束建议直接用 `Field`。
- 4.x 默认 `dereference_schemas=True`，嵌套模型会内联；3.x 之前部分版本保留 `$ref`，客户端兼容性不同。
- 完整差异见 [`docs/03-compat.md`](../docs/03-compat.md)。

## 9. 练习

1. 给 `search_basic` 的 `limit` 加上 `ge=1, le=50`，重跑 `client.py`，确认 schema 里出现 `minimum` / `maximum`。
2. 新增一个 `tag: Literal["mcp", "python"] | None = None` 参数，观察 `anyOf` + `enum` 的嵌套结构。
3. 把 `SearchRequest.tags` 改成 `set[str]`，看 schema 变成什么（提示：`uniqueItems`）。

## 10. 延伸阅读

- FastMCP Tools 文档：<https://gofastmcp.com/docs/servers/tools>
- Pydantic Field：<https://docs.pydantic.dev/latest/concepts/fields/>
- JSON Schema：<https://json-schema.org/understanding-json-schema/>
