"""0306 · 库存服务器：Host 案例的第一个成员。"""

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

inventory = FastMCP(name="InventoryServer", instructions="内存库存服务。")

STOCK = {"KEYBOARD": 5, "MOUSE": 3, "MONITOR": 0}
RESERVED: list[dict] = []


@inventory.tool
def check_stock(sku: str) -> dict:
    """查询库存；未知 SKU 返回业务错误。"""
    if sku not in STOCK:
        raise ToolError(f"未知 SKU：{sku}")
    return {"sku": sku, "available": STOCK[sku]}


@inventory.tool
def reserve(sku: str, qty: int) -> dict:
    """预占库存；数量不足时返回可用数量。"""
    if sku not in STOCK:
        raise ToolError(f"未知 SKU：{sku}")
    if qty <= 0:
        raise ToolError("qty 必须大于 0")
    if STOCK[sku] < qty:
        raise ToolError(f"库存不足：{sku} 仅剩 {STOCK[sku]} 件，请求 {qty} 件")
    STOCK[sku] -= qty
    RESERVED.append({"sku": sku, "qty": qty})
    return {"sku": sku, "reserved": qty, "remaining": STOCK[sku]}


@inventory.tool
def reserved_total() -> dict:
    """返回已预占明细与总量。"""
    return {"items": RESERVED, "total": sum(item["qty"] for item in RESERVED)}


if __name__ == "__main__":
    inventory.run()
