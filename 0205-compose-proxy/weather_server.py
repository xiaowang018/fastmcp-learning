"""0205 · 子服务器 A：天气。故意提供一个与日历同名的工具 get_weather。"""

from fastmcp import FastMCP

weather = FastMCP(name="WeatherServer", instructions="提供城市天气查询。")


@weather.tool
def get_weather(city: str) -> dict:
    """查询城市当前天气。"""
    fake = {"北京": 18, "上海": 22, "深圳": 27}
    return {"city": city, "temperature": fake.get(city, 20), "unit": "celsius"}


@weather.resource("weather://cities")
def cities() -> list[str]:
    """支持的城市列表。"""
    return ["北京", "上海", "深圳"]


@weather.prompt
def weather_brief(city: str) -> str:
    """生成一段天气播报指令。"""
    return f"请根据 {city} 的天气数据，写一句适合发朋友圈的天气播报。"
