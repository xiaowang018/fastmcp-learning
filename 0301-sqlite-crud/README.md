# 0301 · 实战：SQLite 待办服务

> 目标：把工具、资源、提示、lifespan、错误处理、分页、状态机拼成一个能落地的服务。
> 难度 ★★★★ ｜ 前置：01 篇 + 0202 ｜ 依赖：无（标准库 sqlite3）｜ 端口：无 ｜ 预计：45 分钟

## 1. 你会学到

- 用 `lifespan` 持有一个 `sqlite3.Connection` + `asyncio.Lock`，进程内复用。
- 阻塞库（sqlite3）如何通过 `asyncio.to_thread` 不阻塞事件循环。
- 服务端强制状态机（`todo → doing → done`），错误文案直接给模型。
- 分页协议：`total / limit / offset / items`。
- 测试如何用临时数据库隔离，避免「跑一遍脏一次」。

## 2. 先跑起来

```bash
cd 0301-sqlite-crud
uv run python client.py
```

预期输出（截断）：

```text
--- 建表语句 ---
CREATE TABLE tasks ( ...

--- 创建三张任务 ---
  #1 写周报 [high]
  #2 修 bug [high]
  #3 看文档 [low]

--- 分页 ---
  total=3 items=['看文档', '修 bug']

--- 状态流转 ---
  #1 → doing
  跳步（todo→done）→ is_error=True 不能从 todo 直接改为 done；允许：['doing']

--- 统计 / 资源 / 提示 ---
  stats = {'doing': 1, 'todo': 2}
  tasks://doing = [{"id":1,...}]
```

```bash
uv run pytest . -q
# 5 passed
```

## 3. 代码地图

| 文件 | 作用 |
|---|---|
| `server.py` | 4 个工具 + 2 条资源 + 1 个提示 + lifespan |
| `client.py` | 完整业务流：创建→分页→流转→统计→资源→删除 |
| `test_server.py` | 每个测试一个临时库，覆盖 CRUD/分页/状态机/资源 |
| `tasks.db` | 运行时生成，已在 `.gitignore` 里 |

## 4. 为什么用 lifespan 管连接

```python
@asynccontextmanager
async def lifespan(server):
    conn = sqlite3.connect(db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    lock = asyncio.Lock()
    try:
        yield {"conn": conn, "lock": lock}
    finally:
        conn.close()
```

- `sqlite3` 连接**不能跨线程随便用**，`check_same_thread=False` 只是关闭检查；
- 我们用一把 `asyncio.Lock` 把所有数据库操作串行化；
- 查询本身用 `asyncio.to_thread` 丢到线程池，避免阻塞事件循环；
- 连接在进程内复用，比每次调用重新打开快得多。

这是「阻塞库接入 async 服务」的标准写法，换 MySQL/Redis 也是同一套结构。

## 5. 状态机

```python
ALLOWED = {"todo": {"doing"}, "doing": {"done", "todo"}, "done": set()}

if status not in ALLOWED[current]:
    raise ToolError(f"不能从 {current} 直接改为 {status}；允许：{sorted(ALLOWED[current]) or '无'}")
```

为什么放服务端而不是让模型判断：

- 模型可能记错规则；
- 并发下「先查再改」会竞态，服务端可以加锁；
- 错误文案能直接告诉模型下一步怎么做。

`set_status` 还标了 `idempotentHint=True`：重复设置同一状态是安全的。

## 6. 分页协议

```python
{"total": 42, "limit": 10, "offset": 0, "items": [...]}
```

- `limit` 限制在 1-50，防止模型一次拉爆上下文；
- 返回 `total`，模型才知道要不要翻页；
- 偏移分页在数据频繁插入时会重复/漏项，生产可换游标（`id > last_id`）。

## 7. 资源与提示

- `db://schema`：只读，暴露建表语句，帮助模型理解字段；
- `tasks://{status}`：模板资源，按状态取列表；
- `daily_plan`：Prompt，把「读哪个资源、按什么格式输出」固化下来。

再次强调 0105 的判定：**读数据用 Resource，改数据用 Tool，固定指令用 Prompt。**

## 8. 三种验证方式

**client.py**：完整业务流，最直观。

**Inspector**：调用 `create_task` 后，在 Resources 里读 `tasks://todo`，能看到同一份数据。

**接入宿主**：配置同 0101。在对话里说「建一个高优先级任务：写周报，然后开始做」，观察模型是否会连续调用 `create_task` + `set_status`。

## 9. 常见坑

**① 每个工具里都 `sqlite3.connect()`**

连接开销大，且容易忘记关闭。用 lifespan 管一个连接。

**② 忘记 `check_same_thread=False`**

```text
ProgrammingError: SQLite objects created in a thread can only be used in that same thread.
```

**③ 用 f-string 拼 SQL**

```python
f"SELECT * FROM tasks WHERE status = '{status}'"   # 注入风险
```

一律参数化：`WHERE status = ?` + `(status,)`。

**④ 在 async 工具里直接 `conn.execute`**

阻塞事件循环，并发请求会排队。用 `asyncio.to_thread`。

**⑤ 测试共用 `tasks.db`**

测试之间互相污染，顺序一变就红。用 `monkeypatch.setenv("TASK_DB", tmp_path/...)`。

**⑥ 忘记提交事务**

`INSERT/UPDATE/DELETE` 后要 `conn.commit()`。本案例的 `_execute` 统一处理了。

## 10. 与 2.x / 3.x 的差异

- `lifespan` + `ctx.lifespan_context` 的写法在 2.x/3.x 基本一致。
- 4.x 的现代协议不保留会话，但 lifespan 仍然是进程级，适合放连接池。
- `ToolAnnotations` 的字段名在 4.x 是 snake_case（`idempotent_hint`），JSON 里是 camelCase。
- 完整差异见 [`docs/03-compat.md`](../docs/03-compat.md)。

## 11. 练习

1. 加一个 `batch_create(tasks: list[dict])`，用事务保证「要么全成功，要么全回滚」。
2. 把偏移分页改成游标分页：`after_id: int | None`，返回 `next_cursor`。
3. 加一个 `search_tasks(keyword)`，用 SQL `LIKE` 并限制返回条数。
4. 用 `PRAGMA journal_mode=WAL` 提升并发读性能，测量前后差异。

## 12. 延伸阅读

- sqlite3 官方文档：<https://docs.python.org/3/library/sqlite3.html>
- FastMCP Lifespans：<https://gofastmcp.com/docs/servers/lifespan>
- MCP 资源模板：<https://gofastmcp.com/docs/servers/resources>
