"""0205 · 组合服务器：把多个小服务挂成一个网关。

- weather / calendar 是本地 FastMCP 实例，用 mount(namespace=...) 组合。
- math 是一个独立脚本，用 create_proxy(Path(...)) 代理成子进程。
- 同名工具通过 namespace 消歧：weather_get_weather / calendar_get_weather。
"""

from pathlib import Path

from calendar_server import calendar
from fastmcp import FastMCP
from fastmcp.server import create_proxy
from weather_server import weather

mcp = FastMCP(
    name="Gateway",
    instructions="把天气、日历、算术三个服务器组合成一个入口。",
)

mcp.mount(weather, namespace="weather")
mcp.mount(calendar, namespace="calendar")
mcp.mount(create_proxy(Path(__file__).parent / "math_server.py"), namespace="math")


if __name__ == "__main__":
    mcp.run()
