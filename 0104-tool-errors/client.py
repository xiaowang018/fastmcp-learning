"""0104 · 逐条触发五类失败，打印客户端实际收到的异常类型与消息。

运行：uv run python client.py
"""

import asyncio

from fastmcp import Client
from fastmcp.exceptions import ToolError
from server import mcp


async def main() -> None:
    async with Client(mcp, timeout=10) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}
        print("get_balance 的注解：", tools["get_balance"].annotations)
        print("slow 的注解：", tools["slow"].annotations)

        print("\n① 参数校验失败（a 传了字符串）")
        try:
            await client.call_tool("divide", {"a": "abc", "b": 2})
        except ToolError as exc:
            print(f"   ToolError: {str(exc).splitlines()[0]}")

        print("\n② 业务错误（余额不足）")
        try:
            await client.call_tool("withdraw", {"amount": 500})
        except ToolError as exc:
            print(f"   ToolError: {exc}")

        print("\n③ 未捕获异常（mask_error_details=False，详情会泄漏）")
        try:
            await client.call_tool("crash", {})
        except ToolError as exc:
            print(f"   ToolError: {exc}")

        print("\n③b 不抛异常，直接看原始结果")
        result = await client.call_tool("crash", {}, raise_on_error=False)
        print(f"   is_error={result.is_error} content={result.content[0].text!r}")

        print("\n④ 服务端超时（工具声明 timeout=0.3s）")
        try:
            await client.call_tool("slow", {"seconds": 2})
        except ToolError as exc:
            print(f"   ToolError: {exc}")

        print("\n⑤ 客户端取消（0.1s 后 cancel 任务）")
        task = asyncio.create_task(client.call_tool("slow", {"seconds": 2}))
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            print("   CancelledError：取消不是错误，是调用方主动放弃")


if __name__ == "__main__":
    asyncio.run(main())
