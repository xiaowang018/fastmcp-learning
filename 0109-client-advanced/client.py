"""0109 · 完整调用面 + ClientGroup + 最小 Host。

运行：uv run python client.py
"""

import asyncio
import json

from fastmcp import Client, ClientGroup
from math_server import math_mcp
from server import mcp


async def call_surface() -> None:
    async with Client(mcp) as client:
        print("--- 1. 发现 ---")
        tools = await client.list_tools()
        print(f"tools = {[tool.name for tool in tools]}")
        print(f"resources = {[str(item.uri) for item in await client.list_resources()]}")
        print(f"prompts = {[item.name for item in await client.list_prompts()]}")

        print("\n--- 2. 调用工具 ---")
        created = await client.call_tool("create_ticket", {"title": "登录页 500", "priority": "high"})
        print(f"create_ticket = {created.data}")
        listed = await client.call_tool("list_tickets", {"priority": "high"})
        print(f"list_tickets = {listed.data}")

        print("\n--- 3. 读资源 / 取提示 ---")
        payload = await client.read_resource("tickets://all")
        print(f"tickets://all = {json.loads(payload[0].text)}")
        prompt = await client.get_prompt("triage", {"ticket_id": 1})
        print(f"triage = {prompt.messages[0].content.text}")

        print("\n--- 4. 错误分支 ---")
        bad = await client.call_tool("close_ticket", {"ticket_id": 999}, raise_on_error=False)
        print(f"is_error = {bad.is_error}, content = {bad.content[0].text}")


async def client_group() -> None:
    print("\n--- 5. ClientGroup：一个入口聚合两个服务器 ---")
    group = ClientGroup({"ticket": Client(mcp), "math": Client(math_mcp)})
    async with group:
        tools = await group.list_tools()
        print(f"聚合后的工具 = {[tool.name for tool in tools]}")
        print(f"ticket_list_tickets = {(await group.call_tool('ticket_list_tickets', {})).data}")
        print(f"math_multiply = {(await group.call_tool('math_multiply', {'a': 6, 'b': 7})).data}")


async def mini_host() -> None:
    """最小 Host：不依赖 LLM，按计划发现-调用-汇总。

    LLM 在这里负责的只是「生成 PLAN」；执行、参数校验、错误回灌都是 Host 的职责。
    """
    print("\n--- 6. 最小 Host：按计划执行 ---")
    plan = [
        ("ticket_create_ticket", {"title": "支付回调超时", "priority": "high"}),
        ("ticket_create_ticket", {"title": "文档错别字", "priority": "low"}),
        ("ticket_list_tickets", {"priority": "high"}),
        ("math_power", {"base": 2, "exponent": 10}),
    ]

    group = ClientGroup({"ticket": Client(mcp), "math": Client(math_mcp)})
    async with group:
        schemas = {tool.name: tool.input_schema for tool in await group.list_tools()}

        for name, arguments in plan:
            # Host 的职责之一：调用前确认工具存在、必填参数齐全
            if name not in schemas:
                print(f"  [skip] 未知工具 {name}")
                continue
            missing = [key for key in schemas[name].get("required", []) if key not in arguments]
            if missing:
                print(f"  [skip] {name} 缺少参数 {missing}")
                continue

            result = await group.call_tool(name, arguments, raise_on_error=False)
            status = "error" if result.is_error else "ok"
            print(f"  [{status}] {name} → {result.data}")


async def main() -> None:
    await call_surface()
    await client_group()
    await mini_host()


if __name__ == "__main__":
    asyncio.run(main())
