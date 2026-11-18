"""0205 · 被代理的独立服务器：演示 create_proxy 的 stdio 子进程形态。"""

from fastmcp import FastMCP

math_server = FastMCP(name="MathServer", instructions="独立进程里的算术服务。")


@math_server.tool
def multiply(a: int, b: int) -> int:
    """把两个整数相乘。"""
    return a * b


if __name__ == "__main__":
    math_server.run()
