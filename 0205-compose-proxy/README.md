# 0205 · 组合与代理：把小服务拼成网关

> 目标：用 `mount(namespace=...)` 消歧同名工具，用 `create_proxy` 把独立进程/远程服务挂进来。
> 难度 ★★★ ｜ 前置：0109 0204 ｜ 依赖：无 ｜ 端口：无（本地组合）｜ 预计：35 分钟

## 1. 你会学到

- `mount()` 的「实时链接」语义：挂载后子服务器新增的工具会立刻可见。
- `namespace` 如何改写工具名、资源 URI、提示名。
- `create_proxy(Path(...))` 把独立脚本代理成子进程，调用时自动拉起。
- 组合 vs ClientGroup：什么时候用哪个。

## 2. 先跑起来

```bash
cd 0205-compose-proxy
uv run python client.py
```

预期输出（截断）：

```text
网关工具：
  - calendar_add_event
  - calendar_get_weather
  - math_multiply
  - weather_get_weather

同名工具已被 namespace 消歧：
  weather_get_weather(北京) = {'city': '北京', 'temperature': 18, ...}
  calendar_get_weather(2026-11-15) = {'date': '2026-11-15', 'busy': True, 'meetings': 3}

代理的独立进程工具：
  math_multiply(6, 7) = 42

资源也被 namespace 了：['weather://weather/cities']
提示：['weather_weather_brief']
```

```bash
uv run pytest . -q
# 4 passed
```

## 3. 代码地图

| 文件 | 作用 |
|---|---|
| `weather_server.py` | 子服务器 A：天气 + 资源 + 提示，工具名 `get_weather` |
| `calendar_server.py` | 子服务器 B：日历，**故意同名** `get_weather` |
| `math_server.py` | 独立脚本，作为代理目标 |
| `server.py` | 网关：两个 mount + 一个 create_proxy |
| `client.py` / `test_server.py` | 验证命名、路由、资源、提示 |

## 4. mount：实时组合

```python
mcp.mount(weather, namespace="weather")
mcp.mount(calendar, namespace="calendar")
```

- `mount` 是**实时链接**：挂载后给子服务器加工具，网关立刻能看到（不需要重启）。
- 本地 `FastMCP` 实例是进程内组合，零网络开销。
- 子服务器的 lifespan 会跟随父服务器启动/关闭。

## 5. namespace 改写规则

| 组件 | 无 namespace | `namespace="weather"` |
|---|---|---|
| Tool | `get_weather` | `weather_get_weather` |
| Prompt | `weather_brief` | `weather_weather_brief` |
| Resource | `weather://cities` | `weather://weather/cities` |
| Template | `weather://{city}` | `weather://weather/{city}` |

注意资源的改写是**在 scheme 后插入 namespace**，不是简单加前缀。这也是为什么客户端读的时候要写 `weather://weather/cities`。

没有 `://` 的 URI（如 `urn:example:config`）不会被改写，需要自己避免冲突。

## 6. create_proxy：把独立进程挂进来

```python
from fastmcp.server import create_proxy

mcp.mount(create_proxy(Path(__file__).parent / "math_server.py"), namespace="math")
```

- 第一次调用时启动子进程，之后复用；
- 也可以传 URL（远程 HTTP 服务）或 MCP 配置字典（npx / uvx 包）；
- 代理层会转发工具、资源、提示，并按 namespace 改写；
- 父进程退出时会关闭子进程。

适用场景：语言不通（Node 写的 MCP）、权限隔离（独立进程）、复用现成服务器。

## 7. 冲突解决

同名且同 namespace 时：

1. 有版本号 → 取最高版本；
2. 同版本/无版本 → **先挂载的赢**。

所以生产环境建议**总是显式 namespace**，不要依赖挂载顺序。

## 8. 组合 vs ClientGroup

| | `mount`（服务器侧） | `ClientGroup`（客户端侧） |
|---|---|---|
| 谁聚合 | 一个网关服务器 | 你的 Host 进程 |
| 对外形态 | 一个 MCP 端点 | 本地工具目录 |
| 适合 | 给第三方一个统一入口 | 自己写 Agent，聚合多个现成服务 |
| 额外进程 | 代理会增加 | 无 |

简单判据：**要给别人连** → mount；**只给自己用** → ClientGroup。

## 9. 性能与生命周期

- 本地 mount：1-2ms 级；
- 代理 HTTP 服务器：300-400ms 级（每次 `list_tools` 都可能触发上游查询）；
- 深层嵌套会放大延迟，尽量控制在两层；
- 代理子进程的生命周期跟随父服务器，异常退出需要重连策略。

## 10. 三种验证方式

**client.py**：一次看全命名、路由、资源、提示。

**Inspector**：连上网关，观察工具列表里全部带前缀；点 `math_multiply` 时会在服务端拉起子进程。

**接入宿主**：宿主只会看到一个网关，配置同 0101，指向 `server.py`。

## 11. 常见坑

**① 忘记 namespace，后挂载的工具静默丢失**

默认行为是「先挂载的赢」，没有报错。用 `FastMCP(..., on_duplicate="error")` 让冲突启动即失败。

**② 资源 URI 仍按原样读**

namespace 后的 URI 是 `weather://weather/cities`，不是 `weather://cities`。

**③ 代理脚本路径用相对路径**

`Client(Path)`/`create_proxy(Path)` 的相对路径按**当前工作目录**解析。用 `Path(__file__).parent / "math_server.py"` 最稳。

**④ 以为 mount 会复制工具**

它是实时链接。子服务器删掉工具，网关也立刻看不到。

**⑤ 在挂载服务器上重复加同名中间件**

父子中间件都会执行；审计日志会重复。想只记一次就把审计放在父层。

## 12. 与 2.x / 3.x 的差异

- 2.x 用 `import_server`（复制）与 `mount`（链接）两种语义；4.x 统一为 `mount`。
- `namespace` 是 3.0 新增；2.x 需要手动改工具名。
- `as_proxy` 在 3.x 改名为 `create_proxy`，4.x 继续使用。
- 完整差异见 [`docs/03-compat.md`](../docs/03-compat.md)。

## 13. 练习

1. 给网关加第三个子服务器，namespace 设为 `math2`，验证同名工具不冲突。
2. 用 `create_proxy("http://127.0.0.1:8101/mcp")` 代理 0201 的 HTTP 服务，比较与本地 mount 的延迟。
3. 用 `tool_names={"get_weather": "weather_now"}` 在 mount 时重命名单个工具，观察最终名字。

## 14. 延伸阅读

- 组合服务器：<https://gofastmcp.com/docs/servers/composition>
- 代理：<https://gofastmcp.com/docs/servers/providers/proxy>
- Transforms：<https://gofastmcp.com/docs/servers/transforms/transforms>
