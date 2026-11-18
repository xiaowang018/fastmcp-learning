"""0207 · 一个专门用来被测试的服务器。

它足够小，能把「测试怎么写才有价值」讲清楚：
- 正常路径
- 业务错误
- schema 契约
- stdio 真实通路
- 资源读取
"""

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

mcp = FastMCP(name="TestingDemo", instructions="用于演示 MCP 服务器的测试策略。")


@mcp.tool
def divide(a: float, b: float) -> float:
    """做除法；除数为 0 时返回业务错误。

    Args:
        a: 被除数。
        b: 除数，不能为 0。
    """
    if b == 0:
        raise ToolError("除数不能为 0")
    return a / b


@mcp.tool
def echo(text: str, repeat: int = 1) -> str:
    """把文本重复 repeat 次；repeat 限制在 1-5。"""
    if not 1 <= repeat <= 5:
        raise ToolError("repeat 必须在 1-5 之间")
    return text * repeat


@mcp.resource("config://flags", mime_type="application/json")
def flags() -> dict:
    """一份固定的功能开关，便于断言。"""
    return {"beta": False, "max_items": 20}


if __name__ == "__main__":
    mcp.run()
