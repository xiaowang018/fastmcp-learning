"""0302 · 一个本地 mock 天气 API，用来演示「包装外部 REST」。

它不依赖任何外部密钥，断网也能跑。
"""

import asyncio

from fastapi import FastAPI, HTTPException, Query

app = FastAPI(title="Mock Weather API", version="1.0.0")

CITIES = {
    "北京": {"temperature": 18, "condition": "晴", "humidity": 32},
    "上海": {"temperature": 22, "condition": "多云", "humidity": 68},
    "深圳": {"temperature": 27, "condition": "阵雨", "humidity": 80},
}


@app.get("/weather")
async def weather(city: str = Query(description="城市名")) -> dict:
    if city not in CITIES:
        raise HTTPException(status_code=404, detail=f"未收录城市：{city}")
    return {"city": city, **CITIES[city]}


@app.get("/forecast")
async def forecast(city: str, days: int = 3) -> dict:
    if city not in CITIES:
        raise HTTPException(status_code=404, detail=f"未收录城市：{city}")
    base = CITIES[city]["temperature"]
    return {
        "city": city,
        "days": [{"day": index + 1, "temperature": base + index} for index in range(days)],
    }


@app.get("/boom")
async def boom() -> dict:
    raise HTTPException(status_code=500, detail="上游数据库连接失败")


@app.get("/slow")
async def slow() -> dict:
    await asyncio.sleep(2)
    return {"ok": True}
