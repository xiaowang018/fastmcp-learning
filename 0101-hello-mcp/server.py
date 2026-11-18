"""0101 · 最小 MCP 服务器。

这里只有一个工具和一条资源，用来观察 MCP 的最小闭环：
发现（tools/list）→ 调用（tools/call）→ 读取（resources/read）。
"""

from fastmcp import FastMCP

mcp = FastMCP(
    name="HelloMCP",
    instructions="这是一个最小 MCP 服务器：提供一个 add 工具和一条服务器信息资源。",
)


@mcp.tool
def add(a: int, b: int) -> int:
    """把两个整数相加。

    Args:
        a: 第一个整数。
        b: 第二个整数。
    """
    return a + b


@mcp.resource("info://server")
def server_info() -> str:
    """返回服务器自述信息，供客户端在不调用工具的情况下了解服务。"""
    return "HelloMCP v1 · 由 FastMCP 4.2 提供"


if __name__ == "__main__":
    # 默认 transport=stdio：由宿主（Claude Desktop / Cursor / Inspector）拉起本进程。
    mcp.run()
