"""0102 · 工具 schema 的三层写法。

同一个「搜索」需求，用三种签名实现，观察模型看到的 JSON Schema 如何逐步变清晰：
1. 裸类型注解：只有类型，没有约束和参数说明。
2. Annotated + Field：补上描述、长度、范围、枚举。
3. Pydantic 模型：复杂参数收口成一个对象，支持嵌套。
"""

from typing import Annotated, Literal

from fastmcp import FastMCP
from pydantic import BaseModel, Field

mcp = FastMCP(
    name="ToolSchemaDemo",
    instructions="对比三种工具签名写法，理解 schema 就是模型看到的工具契约。",
)

ARTICLES = [
    {"title": "FastMCP 入门", "tag": "mcp", "date": "2026-11-01"},
    {"title": "MCP 协议速览", "tag": "mcp", "date": "2026-10-20"},
    {"title": "Python 类型注解实践", "tag": "python", "date": "2026-09-15"},
    {"title": "Pydantic 校验进阶", "tag": "python", "date": "2026-08-08"},
]


@mcp.tool
def search_basic(query: str, limit: int = 5) -> list[dict]:
    """按关键词搜索文章（基础版：只有类型注解）。"""
    hits = [item for item in ARTICLES if query.lower() in item["title"].lower()]
    return hits[:limit]


@mcp.tool
def search_annotated(
    query: Annotated[str, Field(description="搜索关键词，至少 2 个字符", min_length=2)],
    limit: Annotated[int, Field(description="返回条数，1-20", ge=1, le=20)] = 5,
    sort: Annotated[
        Literal["relevance", "newest"], Field(description="排序方式：相关度或最新")
    ] = "relevance",
) -> dict:
    """按关键词搜索文章（进阶版：参数有描述、范围和枚举）。"""
    hits = [item for item in ARTICLES if query.lower() in item["title"].lower()]
    if sort == "newest":
        hits.sort(key=lambda item: item["date"], reverse=True)
    return {"query": query, "sort": sort, "total": len(hits), "items": hits[:limit]}


class DateRange(BaseModel):
    """时间范围。"""

    start: str = Field(description="开始日期，格式 YYYY-MM-DD")
    end: str = Field(description="结束日期，格式 YYYY-MM-DD")


class SearchRequest(BaseModel):
    """一次结构化搜索请求。"""

    query: str = Field(min_length=2, description="搜索关键词")
    tags: list[str] = Field(default_factory=list, description="标签过滤，多个标签取交集")
    date_range: DateRange | None = Field(default=None, description="可选的时间范围")
    limit: int = Field(default=5, ge=1, le=20, description="返回条数")


@mcp.tool
def search_structured(request: SearchRequest) -> dict:
    """按关键词搜索文章（结构版：复杂参数用一个 Pydantic 模型收口）。"""
    hits = [item for item in ARTICLES if request.query.lower() in item["title"].lower()]
    if request.tags:
        hits = [item for item in hits if item["tag"] in request.tags]
    if request.date_range:
        hits = [
            item
            for item in hits
            if request.date_range.start <= item["date"] <= request.date_range.end
        ]
    return {"total": len(hits), "items": hits[: request.limit]}


if __name__ == "__main__":
    mcp.run()
