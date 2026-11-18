"""0106 · 提示（Prompt）：可复用的消息模板。

Prompt 不执行动作，只负责「渲染一段对话」。它和 Tool 的分工：
- Tool：模型决定要做什么，参数由模型填。
- Prompt：用户主动选用，把一段结构化指令注入对话。
"""

from fastmcp import FastMCP
from fastmcp.prompts import Message, PromptResult
from pydantic import Field

mcp = FastMCP(
    name="PromptDemo",
    instructions="演示三种 Prompt 返回形态：字符串、消息列表、PromptResult。",
)


@mcp.prompt
def explain(topic: str) -> str:
    """让模型解释一个技术概念。

    Args:
        topic: 要解释的概念，例如 "MCP 的 stdio 传输"。
    """
    return f"请用初学者能懂的语言解释「{topic}」，并给出一个可运行的最小例子。"


@mcp.prompt
def code_review(code: str, language: str = "python") -> list[Message]:
    """生成一段代码审查对话（带一条 assistant 示例消息）。"""
    return [
        Message(f"请审查下面这段 {language} 代码，指出正确性、边界和可读性问题：\n\n```{language}\n{code}\n```"),
        Message("我会先看边界条件，再看错误处理，最后给修改建议。", role="assistant"),
    ]


@mcp.prompt(
    name="summarize",
    description="把一段文本压缩成指定词数的摘要，并带上结果元数据。",
    tags={"writing", "summary"},
)
def summarize(
    text: str = Field(description="待摘要的原文"),
    max_words: int = Field(default=100, ge=20, le=500, description="摘要最大词数"),
) -> PromptResult:
    """生成摘要请求。"""
    return PromptResult(
        messages=[
            Message(f"请把下面的文本摘要成不超过 {max_words} 个词，保留数字和结论：\n\n{text}"),
        ],
        meta={"template": "summarize", "max_words": max_words},
    )


if __name__ == "__main__":
    mcp.run()
