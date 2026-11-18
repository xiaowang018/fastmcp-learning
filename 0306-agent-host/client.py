"""0306 · 用确定性计划跑一遍「查库存 → 报价 → 预占 → 恢复」。

运行：uv run python client.py
"""

import asyncio

from host import Step, execute_plan


async def main() -> None:
    steps = [
        Step("inventory_check_stock", {"sku": "KEYBOARD"}, "先看有没有货"),
        Step("pricing_quote", {"sku": "KEYBOARD", "qty": 3}, "算总价"),
        Step("inventory_reserve", {"sku": "KEYBOARD", "qty": 3}, "预占 3 件"),
        Step("inventory_reserve", {"sku": "MOUSE", "qty": 99}, "故意超量：触发恢复"),
        Step("inventory_check_stock", {"sku": "UNKNOWN"}, "未知 SKU：触发业务错误"),
    ]

    trace, results = await execute_plan(steps)

    print("--- 执行轨迹 ---")
    for event in trace.events:
        print(f"  [{event['kind']:8s}] {event['tool']:24s} {event['detail']}")

    print("\n--- 最终结果 ---")
    for tool, value in results.items():
        print(f"  {tool} = {value}")


if __name__ == "__main__":
    asyncio.run(main())
