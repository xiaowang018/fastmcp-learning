"""0104 · 五类失败：校验、业务错误、未捕获异常、超时、取消。

重点不是「怎么不报错」，而是「报错时客户端到底收到什么」。
"""

import asyncio

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

mcp = FastMCP(
    name="ErrorDemo",
    instructions="演示 MCP 工具的五类失败路径，以及客户端如何区分它们。",
    # 学习时先关闭掩码，看清真实报错；生产建议开启，见 README 第 7 节。
    mask_error_details=False,
)

BALANCE = 100


@mcp.tool(
    annotations=ToolAnnotations(
        title="查询余额",
        readOnlyHint=True,
        idempotentHint=True,
        openWorldHint=False,
    )
)
def get_balance() -> dict:
    """查询账户余额（只读操作）。"""
    return {"balance": BALANCE, "currency": "CNY"}


@mcp.tool
def withdraw(amount: int) -> dict:
    """从账户取款。

    Args:
        amount: 取款金额，必须大于 0 且不超过余额。
    """
    if amount <= 0:
        raise ToolError("amount 必须大于 0")
    if amount > BALANCE:
        raise ToolError(f"余额不足：当前 {BALANCE} 元，尝试取出 {amount} 元")
    return {"withdrawn": amount, "balance": BALANCE - amount}


@mcp.tool
def divide(a: float, b: float) -> float:
    """做除法；除数为 0 时抛业务错误。"""
    if b == 0:
        raise ToolError("除数不能为 0，请换一个 b")
    return a / b


@mcp.tool
def crash() -> str:
    """故意抛未捕获异常，观察错误详情是否会泄漏给客户端。"""
    raise RuntimeError("数据库连接串：postgres://user:secret@localhost/db")


@mcp.tool(timeout=0.3)
async def slow(seconds: float = 2.0) -> str:
    """睡指定秒数；默认超过 0.3s 的服务端超时。"""
    await asyncio.sleep(seconds)
    return "done"


if __name__ == "__main__":
    mcp.run()
