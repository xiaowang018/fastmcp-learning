"""0304 · MCP Apps：让工具直接返回可交互的 UI。

依赖是可选的：
- 装了 prefab-ui（uv sync --group apps）：dashboard 工具返回 PrefabApp，宿主可渲染表格/图表。
- 没装：退回 /dashboard 的静态 HTML，案例仍可学习与验证。

运行预览：uv run fastmcp dev apps server.py
"""

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import HTMLResponse

try:  # 可选依赖
    from prefab_ui.app import PrefabApp
    from prefab_ui.components import Column, DataTable, DataTableColumn, Heading, Text

    HAS_PREFAB = True
except ImportError:  # pragma: no cover - 未安装 apps 组时走这里
    HAS_PREFAB = False

ROWS = [
    {"service": "api", "requests": 1280, "errors": 3, "p95_ms": 120},
    {"service": "worker", "requests": 640, "errors": 0, "p95_ms": 340},
    {"service": "web", "requests": 2100, "errors": 11, "p95_ms": 90},
]


def summary() -> dict:
    return {
        "services": len(ROWS),
        "requests": sum(row["requests"] for row in ROWS),
        "errors": sum(row["errors"] for row in ROWS),
        "slowest": max(ROWS, key=lambda row: row["p95_ms"])["service"],
    }


mcp = FastMCP(
    name="AppDemo",
    instructions="演示 @mcp.tool(app=True) 返回交互 UI，以及无 Apps 时的 HTML 降级路径。",
)


@mcp.tool
def get_metrics() -> dict:
    """返回服务指标摘要（普通 JSON 工具）。"""
    return summary()


if HAS_PREFAB:

    @mcp.tool(app=True)
    def dashboard() -> PrefabApp:
        """返回一个可在支持 MCP Apps 的宿主里交互的表格仪表盘。"""
        stats = summary()
        with PrefabApp() as app:
            with Column(gap=4):
                Heading("服务指标")
                Text(f"{stats['services']} 个服务，共 {stats['requests']} 次请求，{stats['errors']} 个错误")
                DataTable(
                    columns=[
                        DataTableColumn(key="service", header="服务", sortable=True),
                        DataTableColumn(key="requests", header="请求数", sortable=True),
                        DataTableColumn(key="errors", header="错误数", sortable=True),
                        DataTableColumn(key="p95_ms", header="P95 (ms)", sortable=True),
                    ],
                    rows=ROWS,
                    search=True,
                )
        return app


@mcp.custom_route("/dashboard", methods=["GET"])
async def dashboard_html(request: Request) -> HTMLResponse:
    """无 Apps 依赖时的降级路径：一张普通 HTML 表格。"""
    body = "".join(
        f"<tr><td>{row['service']}</td><td>{row['requests']}</td>"
        f"<td>{row['errors']}</td><td>{row['p95_ms']}</td></tr>"
        for row in ROWS
    )
    stats = summary()
    return HTMLResponse(
        f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>服务指标</title>
<style>body{{font-family:system-ui;padding:24px}}table{{border-collapse:collapse}}
td,th{{border:1px solid #ddd;padding:6px 12px}}th{{background:#f5f5f5}}</style></head>
<body><h1>服务指标</h1>
<p>{stats['services']} 个服务，共 {stats['requests']} 次请求，{stats['errors']} 个错误；
P95 最高的是 {stats['slowest']}。</p>
<table><thead><tr><th>服务</th><th>请求数</th><th>错误数</th><th>P95 (ms)</th></tr></thead>
<tbody>{body}</tbody></table></body></html>"""
    )


if __name__ == "__main__":
    mcp.run()
