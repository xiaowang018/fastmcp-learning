# 0103 · 返回值：content、structuredContent 与 data 的区别

> 目标：搞清一次工具调用到底返回了什么，以及为什么「同样的数据」会有三种视图。
> 难度 ★★☆ ｜ 前置：0102 ｜ 依赖：无 ｜ 端口：无 ｜ 预计：20 分钟

## 1. 你会学到

- MCP 工具结果的三个层次：`content`（内容块）、`structuredContent`（结构化对象）、`meta`（元数据）。
- 四种返回类型分别被 FastMCP 转成了什么：Pydantic 模型、`int`、`ToolResult`、`Image`。
- 客户端 `result.data` 与 `result.structured_content` 的差别（前者可能被重新校验成模型对象）。
- 什么时候该用 `ToolResult` 完全接管输出。

## 2. 先跑起来

```bash
cd 0103-tool-output
uv run python client.py
```

关键输出（截断）：

```text
analyze（Pydantic 模型）
  data               = Root(title='hello fastmcp world', words=3, tags=['short'])
  structured_content = {'title': 'hello fastmcp world', 'words': 3, 'tags': ['short']}
  content blocks     = [('text', None)]

word_count（int）
  data               = 3
  structured_content = {'result': 3}

analyze_verbose（ToolResult）
  data               = {'words': 2, 'chars': 13}
  meta               = {'analyzer': 'rule-based', 'version': 1, ...}

badge（Image）
  content blocks     = [('image', 'image/png')]
```

```bash
uv run pytest . -q
# 4 passed
```

## 3. 代码地图

| 文件 | 作用 |
|---|---|
| `server.py` | 四个工具，分别返回 Pydantic 模型 / `int` / `ToolResult` / `Image` |
| `client.py` | 把 `data`、`structured_content`、`content`、`meta` 四个字段并排打印 |
| `test_server.py` | 断言每种返回类型的映射规则 |

## 4. 返回类型映射表

| 函数返回 | `content` | `structuredContent` | 客户端 `data` |
|---|---|---|---|
| `dict` / Pydantic / dataclass | JSON 文本块 | ✅ 原生对象 | 重新校验后的模型或 dict |
| `int` / `str` / `list`（有返回注解） | 文本块 | ✅ `{"result": ...}` | 原始值 |
| `int` / `str` / `list`（无返回注解） | 文本块 | ❌ | 原始值 |
| `ToolResult` | 你指定的内容 | 你指定的对象 | `structured_content` |
| `Image` / `Audio` / `File` | 二进制内容块 | ❌ | `None` |
| `None` | 空 | ❌ | `None` |

两条容易忽略的规则：

1. **原始类型只有写了返回注解才会生成 `structuredContent`**。`def f(): return 1` 只有文本块；`def f() -> int: return 1` 才有 `{"result": 1}`。
2. **裸 `list` / `list[Any]` 推不出元素结构**，等价于 `Any`。写 `list[dict]`、`list[int]` 才能生成有意义的 `outputSchema`。

## 5. `data` 不一定是你以为的类型

`analyze` 的返回注解是 `Report`，客户端 `result.data` 打印出来是 `Root(...)` —— 一个自动生成的 Pydantic 包装模型，**不能用 `data["words"]` 下标访问**：

```python
result.data.words                 # ✅
result.structured_content["words"]  # ✅ 想要原始字典时用这个
result.data["words"]              # ❌ TypeError: 'Root' object is not subscriptable
```

这是 0103 最容易踩的坑，也是写测试时最常见的报错来源。

## 6. 什么时候用 `ToolResult`

默认映射够用就不要碰 `ToolResult`。需要下面任意一项时再上：

- `content` 想给人看一句摘要，`structured_content` 给机器另一份精确数据；
- 想设置结果级 `meta`（例如 `{"analyzer": "rule-based"}`）；
- 想返回 `is_error=True` 但**不抛异常**（例如批量任务里部分失败）。

```python
return ToolResult(
    content="文本共 2 个词，长度 13 个字符。",
    structured_content={"words": 2, "chars": 13},
    meta={"analyzer": "rule-based", "version": 1},
)
```

注意：`ToolResult.meta` 是**运行时**元数据；`@mcp.tool(meta={...})` 是**定义时**元数据，两者出现在不同位置。

## 7. 三种验证方式

**client.py**：并排打印四个字段，最直观。

**Inspector**：

```bash
uv run fastmcp dev inspector server.py
```

调用 `analyze` 后切到 `Structured Content` 标签，能同时看到文本块和结构化对象。

**接入宿主**：配置同 0101。带图片的工具在支持 MCP Apps / 多模态的宿主里会直接渲染；纯文本宿主只会显示 `content` 文本。

## 8. 常见坑

**① 以为返回 `dict` 就一定有 `outputSchema`**

`outputSchema` 由返回注解推导。没有注解时，即使返回 dict 也可能没有声明 schema（运行时仍有 `structuredContent`）。**养成写返回注解的习惯。**

**② `data` 是模型对象却当字典用**

见第 5 节。测试里优先断言 `structured_content`，它对类型变化更稳。

**③ 图片/音频塞进 dict 返回**

`Image` / `Audio` / `File` 只有**直接返回**或作为**列表元素**时才会自动转成内容块；放进 dict 不会。需要混合内容时，用 `ToolResult` 或返回内容块列表。

**④ 大文本撑爆上下文**

工具结果会原样进入模型上下文。列表类结果务必分页，或在服务端截断并返回 `total`。

## 9. 与 2.x / 3.x 的差异

- `ToolResult` 在 4.x 从 `fastmcp.tools` 导入；2.x 里对应 `TextContent` 手动拼装，写法不同。
- `structuredContent` 的自动包裹规则（`x-fastmcp-wrap-result`）在 3.x 之后稳定；4.x 对对象类型总是生成结构化内容。
- 完整差异见 [`docs/03-compat.md`](../docs/03-compat.md)。

## 10. 练习

1. 把 `word_count` 的返回注解删掉，重跑 `client.py`，观察 `structured_content` 的变化。
2. 写一个 `batch_analyze(texts: list[str]) -> ToolResult`，部分失败时设置 `is_error=True`，并在 `content` 里列出失败项。
3. 让 `badge` 返回 `list[Image]`（两张图），确认 `content` 里有两个 `image` 块。

## 11. 延伸阅读

- FastMCP Tools（返回值与结构化输出）：<https://gofastmcp.com/docs/servers/tools>
- MCP 内容类型：<https://modelcontextprotocol.io/specification>
