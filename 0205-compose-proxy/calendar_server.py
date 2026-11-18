"""0205 · 子服务器 B：日历。工具名与天气服务器冲突，用来演示 namespace。"""

from fastmcp import FastMCP

calendar = FastMCP(name="CalendarServer", instructions="提供日程管理。")


@calendar.tool
def get_weather(date: str) -> dict:
    """查某个日期的「日程天气」（这里故意与天气服务器同名）。"""
    return {"date": date, "busy": date.endswith("15"), "meetings": 3}


@calendar.tool
def add_event(title: str, date: str) -> dict:
    """新增一个日程。"""
    return {"title": title, "date": date, "created": True}
