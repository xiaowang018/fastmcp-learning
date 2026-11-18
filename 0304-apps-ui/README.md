# 0304 · MCP Apps：工具返回可交互 UI

> 目标：理解 `app=True` 的渲染链路，并为「宿主不支持 Apps」准备一条 HTML 降级路径。
> 难度 ★★★★ ｜ 前置：0103 0201 ｜ 依赖：可选 `uv sync --group apps` ｜ 端口：8108 ｜ 预计：35 分钟

## 1. 你会学到

- `@mcp.tool(app=True)` + `PrefabApp` 如何让工具返回表格/图表等交互界面。
- 客户端收到的不是图片，而是一棵 **UI 描述树**（`$prefab` + `view`）。
- `fastmcp dev apps` 的本地预览方式。
- 可选依赖失败时的降级设计：`custom_route` 返回静态 HTML。

## 2. 先跑起来

```bash
cd 0304-apps-ui
uv sync --group apps     # 安装 prefab-ui
uv run python client.py
```

预期输出：

```text
prefab-ui 可用：True
工具列表：['get_metrics', 'dashboard']
get_metrics = {'services': 3, 'requests': 4020, 'errors': 14, 'slowest': 'worker'}
dashboard: is_error=False
  view 根节点 = Div
  子节点数   = 1
/dashboard 降级页：status=200，长度=605
  含表格：True
```

```bash
uv run pytest . -q
# 3 passed
```

浏览器预览：

```bash
uv run fastmcp dev apps server.py
# 打开 http://localhost:8080，选 dashboard
```

## 3. 代码地图

| 文件 | 作用 |
|---|---|
| `server.py` | 普通指标工具 + 可选 App 工具 + HTML 降级路由 |
| `client.py` | 检查依赖、调用工具、验证降级页 |
| `test_server.py` | 指标、HTML、App 三条测试（未装 apps 自动 skip） |

## 4. 它到底返回了什么

`dashboard` 的 `result.data` 不是图片，而是：

```python
{
  "$prefab": {"version": "0.3"},
  "view": {
    "type": "Div",
    "children": [
      {"type": "Column", "children": [
        {"type": "Heading", "content": "服务指标"},
        {"type": "DataTable", ...}
      ]}
    ]
  }
}
```

支持 MCP Apps 的宿主会把这棵树渲染进沙箱 iframe；不支持的宿主只显示文本内容。所以：

- **不要**把关键信息只放在 UI 里，`content` 也要有一份可读文本；
- UI 是增强，不是唯一通道。

`tools/list` 里 `dashboard` 的 `meta.ui` 会告诉宿主「这个工具返回 UI」。

## 5. 最小写法

```python
from prefab_ui.app import PrefabApp
from prefab_ui.components import Column, Heading, Text

@mcp.tool(app=True)
def dashboard() -> PrefabApp:
    with PrefabApp() as app:
        with Column(gap=4):
            Heading("服务指标")
            Text("3 个服务，4020 次请求")
    return app
```

- `app=True`：注册渲染器、CSP 与 UI 元数据；
- `with PrefabApp() as app:`：所有组件在上下文里声明；
- 返回 `app` 本身。

## 6. 降级路径（必须准备）

```python
@mcp.custom_route("/dashboard", methods=["GET"])
async def dashboard_html(request: Request) -> HTMLResponse:
    return HTMLResponse("<table>...</table>")
```

为什么必须：

- `prefab-ui` 是可选依赖，CI/生产不一定装；
- 宿主支持度不一致（Claude、ChatGPT、Cursor 进度不同）；
- 需要在浏览器里快速看一眼数据时，HTML 最省事。

本案例的测试在没装 `apps` 组时只跑 HTML 路径，保证「核心 20 个案例不装 apps 也全绿」。

## 7. 依赖管理

```bash
uv sync --group apps                      # 只装 apps
uv sync --group api --group apps         # 装多个可选组
uv sync --all-groups                     # 全装
```

注意：`uv sync --group apps` 会把环境**精确同步**成「默认 + apps」，之前装的 `api` 组会被移除。要么一次装多个组，要么用 `--all-groups`。

## 8. 三种验证方式

**client.py**：检查依赖、调用、验证 HTML。

**dev apps**：浏览器里直接交互，最适合调 UI。

**接入宿主**：把 `server.py` 配到支持 MCP Apps 的宿主，调用 `dashboard` 看是否渲染成表格；不支持时确认文本仍可读。

## 9. 常见坑

**① 没装 apps 就 import prefab_ui**

```text
ModuleNotFoundError: No module named 'prefab_ui'
```

本案例用 `try/except ImportError` + `HAS_PREFAB` 降级；生产项目建议把 Apps 做成可选插件。

**② 把 UI 当唯一输出**

不支持 Apps 的宿主只看到一段 JSON 文本。务必同时提供文本摘要。

**③ prefab-ui 版本漂移**

`fastmcp[apps]` 只约束 `>=0.18`，没有上界。用 `uv.lock` 锁定，升级前跑一遍测试。

**④ 在 App 里做阻塞 IO**

组件声明是同步的，但工具函数可以是 async。数据查询放工具里，不要把网络请求写进组件构造。

**⑤ 以为 `app=True` 会自动生成 HTML 页面**

它返回的是 UI 描述树，需要宿主渲染。想在浏览器直接看，用 `fastmcp dev apps` 或自己写 `custom_route`。

## 10. 与 2.x / 3.x 的差异

- Apps 从 3.2 引入，4.x 继续演进；2.x 没有这个能力。
- `app=True` 的参数在 4.x 接受 `AppConfig` / dict，可配置 CSP、渲染器等。
- 4.x 的 UI 元数据放在工具 `meta.ui`，宿主据此决定是否渲染。
- 完整差异见 [`docs/03-compat.md`](../docs/03-compat.md)。

## 11. 练习

1. 给 `dashboard` 加一个 `PieChart`，按服务统计请求占比。
2. 加一个 `Form`（prefab 表单）收集筛选条件，提交后返回新的表格。
3. 把 HTML 降级页做成可排序的（引入一小段原生 JS），对比与 Apps 的开发成本。

## 12. 延伸阅读

- FastMCP Apps：<https://gofastmcp.com/docs/apps/overview>
- Apps Quickstart：<https://gofastmcp.com/docs/apps/quickstart>
- Prefab UI：<https://prefab.prefect.io>
