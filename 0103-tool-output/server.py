"""0103 · 返回值决定客户端看到什么。

同一个「分析文本」需求，用四种返回类型实现：
1. Pydantic 模型 → 结构化内容 + JSON 文本块
2. int → 只有声明了 -> int 才会包成 {"result": n}
3. ToolResult → 完全控制 content / structured_content / meta
4. Image → 二进制内容块
"""

import base64

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from fastmcp.utilities.types import Image
from pydantic import BaseModel, Field

mcp = FastMCP(
    name="ToolOutputDemo",
    instructions="演示 FastMCP 的返回类型如何映射到 content 与 structuredContent。",
)

# 1x1 透明 PNG，避免依赖外部图片文件
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


class Report(BaseModel):
    """一份文本分析报告。"""

    title: str = Field(description="报告标题")
    words: int = Field(description="词数")
    tags: list[str] = Field(default_factory=list, description="命中的标签")


@mcp.tool
def analyze(text: str) -> Report:
    """分析文本并返回结构化报告。"""
    words = len(text.split())
    tags = ["short"] if words < 5 else ["long"]
    return Report(title=text[:20] or "(empty)", words=words, tags=tags)


@mcp.tool
def word_count(text: str) -> int:
    """只返回词数：有 -> int 注解时，会额外包一层 {"result": n}。"""
    return len(text.split())


@mcp.tool
def analyze_verbose(text: str) -> ToolResult:
    """需要同时给「人读的摘要」和「机器读的结构」时，用 ToolResult。"""
    words = len(text.split())
    return ToolResult(
        content=f"文本共 {words} 个词，长度 {len(text)} 个字符。",
        structured_content={"words": words, "chars": len(text)},
        meta={"analyzer": "rule-based", "version": 1},
    )


@mcp.tool
def badge(text: str) -> Image:
    """返回一张图片内容块（这里用 1x1 PNG 占位）。"""
    return Image(data=TINY_PNG, format="png")


if __name__ == "__main__":
    mcp.run()
