"""0206 · 一个普通的 FastAPI 应用，稍后被转成 MCP 服务器。

注意 operation_id：它决定 MCP 工具名。不写的话 FastAPI 会生成
`list_products_products_get` 这类名字，再在第一个 __ 处截断，可读性很差。
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Shop API", version="1.0.0")


class ProductIn(BaseModel):
    name: str = Field(description="商品名")
    price: float = Field(gt=0, description="单价（元）")
    category: str = Field(default="general", description="分类")


class Product(ProductIn):
    id: int


DB: dict[int, Product] = {
    1: Product(id=1, name="机械键盘", price=499, category="electronics"),
    2: Product(id=2, name="人体工学椅", price=1299, category="furniture"),
    3: Product(id=3, name="马克杯", price=39, category="life"),
}
ORDERS = [{"id": 101, "product_id": 1, "qty": 2}, {"id": 102, "product_id": 3, "qty": 5}]


@app.get("/products", operation_id="list_products", response_model=list[Product])
def list_products(category: str | None = None, max_price: float | None = None) -> list[Product]:
    """列出商品，可按分类与价格上限过滤。"""
    items = list(DB.values())
    if category:
        items = [item for item in items if item.category == category]
    if max_price is not None:
        items = [item for item in items if item.price <= max_price]
    return items


@app.get("/products/{product_id}", operation_id="get_product", response_model=Product)
def get_product(product_id: int) -> Product:
    """按 ID 获取商品。"""
    if product_id not in DB:
        raise HTTPException(status_code=404, detail=f"商品 {product_id} 不存在")
    return DB[product_id]


@app.post("/products", operation_id="create_product", response_model=Product, status_code=201)
def create_product(payload: ProductIn) -> Product:
    """创建商品。"""
    new_id = max(DB) + 1
    product = Product(id=new_id, **payload.model_dump())
    DB[new_id] = product
    return product


@app.get("/orders", operation_id="list_orders")
def list_orders() -> list[dict]:
    """列出订单。"""
    return ORDERS
