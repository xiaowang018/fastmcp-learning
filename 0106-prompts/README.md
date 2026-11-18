# 0106 · 提示（Prompt）：给模型一段可复用的指令

> 目标：分清 Tool 和 Prompt 的职责，掌握三种 Prompt 返回形态与参数校验。
> 难度 ★★☆ ｜ 前置：0102 ｜ 依赖：无 ｜ 端口：无 ｜ 预计：20 分钟

## 1. 你会学到

- Prompt 是「用户主动选用的消息模板」，不是模型自动调用的工具。
- 三种返回形态：`str`、`list[Message]`、`PromptResult`。
- 参数如何变成 `PromptArgument`，必填/可选怎么判定。
- 为什么 Prompt 适合放「审查清单」「写作规范」「角色设定」。

## 2. 先跑起来

```bash
cd 0106-prompts
uv run python client.py
```

预期输出（截断）：

```text
Prompt：explain
  描述：让模型解释一个技术概念。
  参数：[('topic', True)]

Prompt：code_review
  参数：[('code', True), ('language', False)]

Prompt：summarize
  参数：[('text', True), ('max_words', False)]

explain → user: 请用初学者能懂的语言解释「MCP 的 stdio 传输」，并给出一个可运行的最小例子。
code_review → assistant: 我会先看边界条件，再看错误处理，最后给修改建议。
summarize → meta={'template': 'summarize', 'max_words': 30, ...}
```

```bash
uv run pytest . -q
# 5 passed
```

## 3. 代码地图

| 文件 | 作用 |
|---|---|
| `server.py` | 三个 Prompt，分别返回字符串、消息列表、`PromptResult` |
| `client.py` | 列出 Prompt、渲染三次、打印角色与元数据 |
| `test_server.py` | 断言参数、角色、元数据与参数校验 |

## 4. Tool vs Prompt

| | Tool | Prompt |
|---|---|---|
| 谁发起 | 模型根据任务自动选择 | 用户主动选用（斜杠命令、模板按钮） |
| 参数谁填 | 模型从上下文推断 | 用户填写表单 |
| 是否有副作用 | 可能有 | 无，只渲染消息 |
| 典型用途 | 查库、发请求、算数 | 代码审查、写作规范、角色扮演 |

一句话：**Tool 是「做什么」，Prompt 是「怎么说」。**

## 5. 三种返回形态

### 字符串：单条 user 消息

```python
@mcp.prompt
def explain(topic: str) -> str:
    """让模型解释一个技术概念。

    Args:
        topic: 要解释的概念。
    """
    return f"请用初学者能懂的语言解释「{topic}」..."
```

最简单的形态，适合 90% 的场景。docstring 的首段是描述，`Args:` 里的条目会变成参数描述。

### 消息列表：多轮对话

```python
@mcp.prompt
def code_review(code: str, language: str = "python") -> list[Message]:
    return [
        Message(f"请审查下面这段 {language} 代码..."),
        Message("我会先看边界条件，再看错误处理。", role="assistant"),
    ]
```

`Message` 的 `role` 默认是 `user`，可以显式设成 `assistant` 来「预填」一轮回复，引导模型按这个思路走。

### `PromptResult`：需要结果级元数据

```python
@mcp.prompt(name="summarize", description="...", tags={"writing"})
def summarize(text: str, max_words: int = 100) -> PromptResult:
    return PromptResult(
        messages=[Message(f"请把下面的文本摘要成不超过 {max_words} 个词...")],
        meta={"template": "summarize", "max_words": max_words},
    )
```

`PromptResult` 的 `meta` 会出现在渲染结果的 `_meta` 字段，适合做 A/B 实验标记、模板版本号。

## 6. 参数与校验

- 没有默认值 → 必填；有默认值 → 可选。
- 用 `Field(ge=..., le=..., min_length=...)` 加约束，**服务端会真正校验**。
- 参数类型建议保持简单：`str` / `int` / `float` / `bool` / `list[str]`。MCP 客户端传参时会把非字符串编码成 JSON 字符串，复杂嵌套模型容易转换失败。

```python
max_words: int = Field(default=100, ge=20, le=500, description="摘要最大词数")
```

传 `max_words=5` 会得到校验错误（本案例的最后一个测试）。

## 7. 三种验证方式

**client.py**：列出 + 渲染，最快。

**Inspector**：`uv run fastmcp dev inspector server.py`，切到 Prompts 标签，选 `summarize` 填参数，右侧会显示渲染后的消息。

**接入宿主**：Claude Desktop / Cursor 通常把 Prompt 显示为斜杠命令或模板菜单；Claude Code 里可用 `/mcp__<server>__<prompt>` 形式调用（视版本而定）。

## 8. 常见坑

**① 把 Prompt 当成 Tool 用**

Prompt 不会被执行，也不会自动触发。如果希望「模型自己决定何时调用」，应该写 Tool。

**② 参数没有默认值却以为是可选**

MCP 的 `PromptArgument.required` 由默认值决定。想可选必须给默认值。

**③ 在 Prompt 里塞了超长文档**

Prompt 是模板，不是数据通道。大段原文应该放 Resource，Prompt 只放「指令 + 资源 URI」。

**④ 返回了 `list[str]` 却以为角色会保留**

`list[str]` 会被逐条转成 **user** 消息。需要 assistant 角色时必须用 `Message(..., role="assistant")`。

## 9. 与 2.x / 3.x 的差异

- `Message` 与 `PromptResult` 是 3.0 引入的；2.x 需要手写 `PromptMessage`。
- `Field` 作为参数默认值的写法在 4.x 完整支持；2.x 部分版本只支持 `Annotated`。
- 参数描述从 docstring 自动提取是 3.2.4 之后的能力。
- 完整差异见 [`docs/03-compat.md`](../docs/03-compat.md)。

## 10. 练习

1. 写一个 `debug_prompt(error: str, stack: str = "") -> list[Message]`，第一条 user 给错误，第二条 assistant 给出排查框架。
2. 给 `summarize` 增加 `style: Literal["bullet", "paragraph"] = "paragraph"`，观察 `PromptArgument` 的 schema 变化。
3. 用 `client.get_prompt` 渲染 `code_review`，把 `language` 换成 `javascript`，确认代码块围栏也跟着变。

## 11. 延伸阅读

- FastMCP Prompts：<https://gofastmcp.com/docs/servers/prompts>
- MCP Prompts 规范：<https://modelcontextprotocol.io/specification>
