"""0109 · 第二个服务器，用来演示 ClientGroup 的多服务器聚合。"""

from fastmcp import FastMCP

math_mcp = FastMCP(name="MathServer", instructions="一个只做算术的小服务器。")


@math_mcp.tool
def multiply(a: int, b: int) -> int:
    """把两个整数相乘。"""
    return a * b


@math_mcp.tool
def power(base: int, exponent: int) -> int:
    """计算 base 的 exponent 次方（指数限制在 0-10）。"""
    if not 0 <= exponent <= 10:
        raise ValueError("exponent 必须在 0-10 之间")
    return base**exponent


if __name__ == "__main__":
    math_mcp.run()
