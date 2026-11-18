"""0303 · 本地 Markdown 知识库：Resource 读原文，Tool 做检索，Prompt 固定回答格式。

不引入向量库：用「标题命中 + 正文词频」做一个可解释的基线检索。
真实项目可以把它替换成 BM25 / 向量检索，接口保持不变。
"""

import re
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.exceptions import ResourceError, ToolError

mcp = FastMCP(
    name="DocsKB",
    instructions="本地 Markdown 知识库：支持检索、读取原文与带引用的回答模板。",
)

DOCS_DIR = (Path(__file__).parent / "data").resolve()


def load_docs() -> dict[str, str]:
    """启动时读取全部 Markdown；文件很少，直接进内存。"""
    return {path.stem: path.read_text(encoding="utf-8") for path in sorted(DOCS_DIR.glob("*.md"))}


DOCS = load_docs()


def tokenize(text: str) -> list[str]:
    """中英文混合的极简分词：英文按单词，中文按 2 字滑窗。"""
    words = re.findall(r"[a-zA-Z0-9_]+", text.lower())
    chinese = re.findall(r"[\u4e00-\u9fff]+", text)
    grams: list[str] = []
    for block in chinese:
        grams.extend(block[index : index + 2] for index in range(max(1, len(block) - 1)))
    return words + grams


@mcp.tool
def search(query: str, limit: int = 3) -> dict:
    """检索知识库，返回带出处与评分的片段。

    Args:
        query: 关键词，中英文均可。
        limit: 返回条数，1-5。
    """
    if not 1 <= limit <= 5:
        raise ToolError("limit 必须在 1-5 之间")

    terms = tokenize(query)
    if not terms:
        return {"query": query, "hits": []}

    hits = []
    for name, text in DOCS.items():
        title = text.splitlines()[0].lstrip("# ").strip()
        title_hits = sum(1 for term in terms if term in title.lower())
        body_hits = sum(text.lower().count(term) for term in terms)
        score = title_hits * 5 + body_hits
        if score == 0:
            continue
        snippet = next(
            (line.strip() for line in text.splitlines() if any(term in line.lower() for term in terms)),
            text.splitlines()[0],
        )
        hits.append({"source": f"kb://{name}", "title": title, "score": score, "snippet": snippet[:160]})

    hits.sort(key=lambda item: item["score"], reverse=True)
    return {"query": query, "hits": hits[:limit]}


@mcp.resource("kb://index", mime_type="application/json")
def index() -> list[dict]:
    """知识库目录：文件名、标题、字数。"""
    return [
        {"name": name, "title": text.splitlines()[0].lstrip("# ").strip(), "chars": len(text)}
        for name, text in DOCS.items()
    ]


@mcp.resource("kb://{name}", mime_type="text/markdown")
def read_doc(name: str) -> str:
    """按文件名读取原文（单层，不允许路径分隔符）。"""
    if "/" in name or "\\" in name or name not in DOCS:
        raise ResourceError(f"文档不存在：{name}")
    return DOCS[name]


@mcp.prompt
def answer_with_citations(question: str, limit: int = 3) -> str:
    """生成一段「先检索、再回答、必须带出处」的指令。"""
    return (
        f"请先调用 search 工具检索：{question}（limit={limit}）。\n"
        "然后只根据检索结果回答，每个结论后用 [来源](kb://文件名) 标注出处。\n"
        "如果检索结果不足以回答，请明确说「知识库中没有相关信息」，不要编造。"
    )


if __name__ == "__main__":
    mcp.run()
