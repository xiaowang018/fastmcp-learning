"""0306 · Host 的发现、校验、执行与错误恢复。"""

import pytest

from helpers import load_server

INVENTORY = load_server("0306-agent-host")
PRICING = load_server("0306-agent-host", "pricing_server.py")
HOST = load_server("0306-agent-host", "host.py")

SERVERS = {"inventory": INVENTORY.inventory, "pricing": PRICING.pricing}


@pytest.fixture(autouse=True)
def _reset_stock():
    INVENTORY.STOCK.update({"KEYBOARD": 5, "MOUSE": 3, "MONITOR": 0})
    INVENTORY.RESERVED.clear()
    yield


async def test_plan_executes_and_recovers() -> None:
    steps = [
        HOST.Step("inventory_check_stock", {"sku": "KEYBOARD"}),
        HOST.Step("pricing_quote", {"sku": "KEYBOARD", "qty": 3}),
        HOST.Step("inventory_reserve", {"sku": "KEYBOARD", "qty": 3}),
        HOST.Step("inventory_reserve", {"sku": "MOUSE", "qty": 99}),
    ]

    trace, results = await HOST.execute_plan(steps, SERVERS)
    kinds = [event["kind"] for event in trace.events]

    assert "discover" in kinds
    assert results["pricing_quote"]["total"] == round(499 * 3 * 0.95, 2)
    # 超量预占先失败，随后按可用量恢复成功
    assert "error" in kinds
    assert INVENTORY.STOCK["MOUSE"] == 0


async def test_host_skips_unknown_tool_and_missing_args() -> None:
    steps = [
        HOST.Step("inventory_nope", {}),
        HOST.Step("pricing_quote", {"sku": "KEYBOARD"}),
    ]
    trace, results = await HOST.execute_plan(steps, SERVERS)
    skipped = [event for event in trace.events if event["kind"] == "skip"]
    assert len(skipped) == 2
    assert "未知工具" in skipped[0]["detail"]
    assert "缺少必填参数" in skipped[1]["detail"]
    assert results == {}


async def test_reservation_changes_stock() -> None:
    steps = [HOST.Step("inventory_reserve", {"sku": "KEYBOARD", "qty": 2})]
    await HOST.execute_plan(steps, SERVERS)
    assert INVENTORY.STOCK["KEYBOARD"] == 3
