"""0105 · 资源的四种形态：静态、模板、通配、查询参数。

资源是「可读取的数据」，不应该有副作用。本例把本地 Markdown 目录暴露成 MCP 资源。
"""

from pathlib import Path

from fastmcp import FastMCP
from fastmcp.exceptions import ResourceError
from fastmcp.resources import ResourceContent, ResourceResult

mcp = FastMCP(
    name="ResourceDemo",
    instructions="演示静态资源、URI 模板、通配路径、查询参数，以及路径穿越防护。",
)

DATA_DIR = (Path(__file__).parent / "data").resolve()
DOCS_DIR = (DATA_DIR / "docs").resolve()


@mcp.resource("docs://guide", mime_type="text/markdown")
def guide() -> str:
    """静态资源：内容固定在代码里，不依赖任何文件。"""
    return """# 资源使用指南

- `docs://guide`：就是你正在读的这条静态资源。
- `docs://{filename}`：读取 `data/docs/` 下的单层 Markdown 文件。
- `files://{path*}`：读取 `data/docs/` 下的多级路径。
- `items://catalog{?limit,tag}`：带查询参数的资源。
"""


@mcp.resource("docs://{filename}", mime_type="text/markdown")
def read_doc(filename: str) -> str:
    """模板资源：URI 里的 {filename} 会作为参数传入函数。"""
    path = (DOCS_DIR / filename).with_suffix(".md").resolve()
    # FastMCP 4 会在调用前拦截 ../ 和绝对路径，这里再做一次根目录包含检查（纵深防御）。
    if not path.is_relative_to(DOCS_DIR) or not path.is_file():
        raise ResourceError(f"文档不存在：{filename}")
    return path.read_text(encoding="utf-8")


@mcp.resource("files://{path*}", mime_type="text/markdown")
def read_nested(path: str) -> str:
    """通配资源：{path*} 可以跨越多级目录，例如 advanced/tips。"""
    target = (DOCS_DIR / f"{path}.md").resolve()
    if not target.is_relative_to(DOCS_DIR) or not target.is_file():
        raise ResourceError(f"文件不存在：{path}")
    return target.read_text(encoding="utf-8")


@mcp.resource("items://catalog{?limit,tag}", mime_type="application/json")
def catalog(limit: int = 10, tag: str = "all") -> dict:
    """查询参数资源：limit / tag 是可选项，必须带默认值。"""
    items = [
        {"id": 1, "name": "MCP 入门", "tag": "mcp"},
        {"id": 2, "name": "工具设计", "tag": "mcp"},
        {"id": 3, "name": "Pydantic 实践", "tag": "python"},
    ]
    if tag != "all":
        items = [item for item in items if item["tag"] == tag]
    return {"total": len(items), "items": items[:limit]}


@mcp.resource("report://summary")
def summary() -> ResourceResult:
    """一条资源返回多个内容项：Markdown 摘要 + JSON 明细。"""
    return ResourceResult(
        contents=[
            ResourceContent("# 资源示例\n共 3 条数据，2 条 mcp 标签。", mime_type="text/markdown"),
            ResourceContent({"count": 3, "tags": ["mcp", "python"]}, mime_type="application/json"),
        ],
        meta={"generated_by": "0105"},
    )


if __name__ == "__main__":
    mcp.run()
