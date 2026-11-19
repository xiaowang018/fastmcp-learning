# 0207 · 测试：怎样写出能抓住 bug 的测试

> 目标：把「跑通一次」变成「以后改坏会被发现」。五类测试覆盖正常、边界、错误、契约、真实通路。
> 难度 ★★★ ｜ 前置：0109 0202 ｜ 依赖：无 ｜ 端口：无 ｜ 预计：30 分钟

## 1. 你会学到

- MCP 服务器的测试金字塔：纯函数 → 进程内 Client → stdio 子进程。
- `pytest-asyncio` 的 `asyncio_mode="auto"` 在本仓库怎么用。
- 参数化、异常断言、schema 契约、资源 MIME 断言。
- 一个「永远为真」的坏测试，以及怎么改成有效断言。
- markers 与 CI 分层跑法。

## 2. 先跑起来

```bash
cd 0207-testing
uv run python client.py     # 4 组快速自检
uv run pytest . -q          # 9 个测试
uv run pytest . -q -m "not slow"   # 跳过 stdio 子进程测试
```

预期：

```text
4 组自检通过。真正的测试在 test_server.py，运行：uv run pytest . -q
.........
9 passed
```

## 3. 代码地图

| 文件 | 作用 |
|---|---|
| `server.py` | 一个除零错误、一个参数校验、一个资源，足够覆盖五类测试 |
| `client.py` | 不依赖 pytest 的快速自检 |
| `test_server.py` | 参数化 / 异常 / schema / 资源 / stdio 五类测试 |

## 4. 测试金字塔

| 层级 | 连接方式 | 速度 | 能抓到什么 |
|---|---|---|---|
| 纯函数 | 直接调用业务函数 | 微秒 | 算法与边界 |
| 进程内 Client | `Client(mcp)` | 毫秒 | schema、序列化、错误映射 |
| stdio 子进程 | `Client(Path("server.py"))` | 秒级 | `__main__`、环境、编码、协议握手 |
| HTTP | `serve_http(mcp)` | 秒级 | 传输、鉴权、健康检查 |

**只测进程内会漏掉一半问题**：`__main__` 里写错 transport、print 污染 stdout、Windows 编码错误，都只有子进程测试能发现。

## 5. 五类测试怎么写

### 正常路径 + 参数化

```python
@pytest.mark.parametrize(("a", "b", "expected"), [(9, 3, 3.0), (1, 2, 0.5)])
async def test_divide_normal_cases(a, b, expected):
    async with Client(SERVER.mcp) as client:
        assert (await client.call_tool("divide", {"a": a, "b": b})).data == expected
```

### 业务错误：断言消息，不只断言抛异常

```python
with pytest.raises(ToolError) as info:
    await client.call_tool("divide", {"a": 1, "b": 0})
assert "除数不能为 0" in str(info.value)
```

消息是给模型看的契约。只写 `pytest.raises(ToolError)`，消息退化成「出错了」也测不出来。

### schema 契约

```python
divide = tools["divide"].input_schema
assert divide["required"] == ["a", "b"]
echo = tools["echo"].input_schema
assert echo["properties"]["repeat"]["default"] == 1
```

改参数名、加必填、改类型都会破坏宿主和模型的调用，必须有测试兜住。

### 资源

```python
content = await client.read_resource("config://flags")
assert content[0].mime_type == "application/json"
```

### 真实 stdio

```python
async with Client(CASE_DIR / "server.py", timeout=20) as client:
    assert (await client.call_tool("echo", {"text": "hi"})).data == "hi"
```

## 6. 一个抓不到 bug 的测试

```python
async def test_bad():
    result = await client.call_tool("divide", {"a": 1, "b": 2})
    assert result is not None      # 只要不抛异常就通过
```

它测不出「返回值算错了」「结构变了」「错误消息丢了」。有效版本：

```python
assert result.data == 0.5
assert result.structured_content == {"result": 0.5}
```

判断标准：**把实现改坏一行，这个测试会不会红？** 不会红就是假测试。

## 7. 本仓库的测试约定

| 约定 | 原因 |
|---|---|
| `asyncio_mode = "auto"` | 不用每个测试加 `@pytest.mark.asyncio` |
| `--import-mode=importlib` | 22 个同名 `test_server.py` 不会 import mismatch |
| `load_server("0101-hello-mcp")` | 数字目录不能 import，按绝对路径加载 |
| `Client` 写在测试体内 | 避免 fixture 与事件循环生命周期错位 |
| `port=0` + `serve_http` | 并行测试不抢端口 |
| 子进程 env 带 `PYTHONUTF8=1` | Windows 中文不乱码 |

## 8. markers 与 CI 分层

```bash
uv run pytest -q                              # 默认：排除 manual / network
uv run pytest -q -m "not slow"                # 快速反馈
uv run pytest -q -m "not manual and not network and not apps"  # 离线子集
uv run pytest -q -m apps                      # 只跑 Apps 案例（需装 apps 组）
```

建议 CI 分三层：

1. **PR 快速层**：`-m "not slow"`，30 秒内；
2. **合并层**：全量 + 覆盖率；
3. **夜间层**：`-m "network or slow"`，允许失败重试。

## 9. 三种验证方式

**pytest**：本案例的主入口。

**client.py**：不装 pytest 也能自检的最小脚本。

**覆盖率**：`uv run pytest --cov=. --cov-report=term-missing`（需额外安装 pytest-cov）。

## 10. 常见坑

**① 在 fixture 里 `async with Client(...)`**

事件循环作用域容易错位。fixture 只产出 server 对象，连接写在测试体内。

**② 测试之间共享可变状态**

模块级 `TICKETS` / `QUOTA` 要在每个测试前重置（见 0109/0203 的 autouse fixture）。

**③ 只断言 `is_error`，不断言消息**

错误文案是模型可操作性的关键。至少断言一个关键词。

**④ 用 `sleep` 等 HTTP 服务就绪**

用 `serve_http` 轮询启动与端口，避免 flaky。

**⑤ 把 `print` 当断言**

CI 里看不到 print 的输出语义，只有断言才会失败。

## 11. 与 2.x / 3.x 的差异

- pytest-asyncio 1.x 的 `asyncio_mode="auto"` 与旧版配置项不同；旧教程里的 `asyncio_default_fixture_loop_scope` 警告在 1.5 已处理。
- `Client` 的 `raise_on_error` 在 3.x 之后稳定；2.x 需要手动检查 `isError`。
- 4.x 的 `protocol_version` 可用于断言协议分支。
- 完整差异见 [`docs/03-compat.md`](../docs/03-compat.md)。

## 12. 练习

1. 给 `divide` 加一个 `precision: int = 2` 参数，先写会失败的测试，再实现（TDD）。
2. 写一个 `test_no_stdout_pollution`：用子进程连接，断言 `server.py` 没有向 stdout 写非 JSON 内容。
3. 用 `pytest.mark.parametrize` 覆盖 `echo` 的 `repeat` 边界：0、1、5、6。

## 13. 延伸阅读

- FastMCP Testing：<https://gofastmcp.com/docs/servers/testing>
- pytest-asyncio：<https://pytest-asyncio.readthedocs.io/>
- pytest markers：<https://docs.pytest.org/en/stable/how-to/mark.html>
