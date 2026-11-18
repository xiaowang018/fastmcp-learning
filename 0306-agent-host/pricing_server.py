"""0306 · 定价服务器：Host 案例的第二个成员。"""

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

pricing = FastMCP(name="PricingServer", instructions="简单阶梯定价。")

PRICES = {"KEYBOARD": 499, "MOUSE": 129, "MONITOR": 1899}


@pricing.tool
def quote(sku: str, qty: int) -> dict:
    """按数量计算总价：>=3 件 95 折，>=5 件 9 折。"""
    if sku not in PRICES:
        raise ToolError(f"未知 SKU：{sku}")
    if qty <= 0:
        raise ToolError("qty 必须大于 0")

    unit = PRICES[sku]
    discount = 0.95 if qty >= 3 else 1.0
    if qty >= 5:
        discount = 0.9
    total = round(unit * qty * discount, 2)
    return {"sku": sku, "qty": qty, "unit": unit, "discount": discount, "total": total}


if __name__ == "__main__":
    pricing.run()
