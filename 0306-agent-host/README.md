# 0306 · 实战：写一个最小 MCP Host

> 目标：不调用 LLM，用确定性 planner 走完「发现 → 校验 → 调用 → 错误恢复 → 汇总」，看清 Host 到底负责什么。
> 难度 ★★★★ ｜ 前置：0109 0301 ｜ 概念相关：0302（代码不 import）｜ 依赖：无 ｜ 端口：无 ｜ 预计：40 分钟

## 1. 你会学到

- Host / Client / Server 的分工：模型只负责「生成计划」。
- `ClientGroup` 如何把库存、定价两个服务器聚合成一个工具目录。
- 调用前校验（工具存在、必填参数齐全）为什么必须由 Host 做。
- 错误回灌与确定性恢复：预占失败 → 查可用量 → 按可用量重试。
- 一条可断言的 trace，怎么用于调试与评测。

## 2. 先跑起来

```bash
cd 0306-agent-host
uv run python client.py
```

预期输出（截断）：

```text
--- 执行轨迹 ---
  [discover] -                        2 个工具：['inventory_check_stock', ...]
  [call    ] inventory_check_stock    step 1: {'sku': 'KEYBOARD'}
  [ok      ] inventory_check_stock    {'sku': 'KEYBOARD', 'available': 5}
  [call    ] pricing_quote            step 2: {'sku': 'KEYBOARD', 'qty': 3}
  [ok      ] pricing_quote            {'total': 1422.15, ...}
  [call    ] inventory_reserve        step 4: {'sku': 'MOUSE', 'qty': 99}
  [error   ] inventory_reserve        库存不足：MOUSE 仅剩 3 件，请求 99 件
  [call    ] inventory_check_stock    step 1: {'sku': 'MOUSE'}
  [ok      ] inventory_reserve        {'sku': 'MOUSE', 'reserved': 3, 'remaining': 0}

--- 最终结果 ---
  pricing_quote = {'total': 1422.15, ...}
  inventory_reserve = {'sku': 'MOUSE', 'reserved': 3, 'remaining': 0}
```

```bash
uv run pytest . -q
# 3 passed
```

## 3. 代码地图

| 文件 | 作用 |
|---|---|
| `server.py` | 库存服务：查库存、预占、汇总 |
| `pricing_server.py` | 定价服务：阶梯折扣 |
| `host.py` | Host：发现、校验、执行、恢复、trace |
| `client.py` | 固定计划 + 打印轨迹 |
| `test_server.py` | 计划执行、跳过非法步骤、库存变化 |

## 4. Host 的四项职责

```text
LLM（或规则） → 计划（调哪个工具、传什么参数）
Host          → 发现、校验、调用、错误处理、结果汇总
Server        → 真正执行
```

| 职责 | 代码 | 不做的后果 |
|---|---|---|
| 发现 | `group.list_tools()` 缓存 schema | 调不存在的工具 |
| 路由 | `{server}_{tool}` 前缀 | 同名工具串台 |
| 校验 | 比对 `required` | 参数缺失，浪费一次调用 |
| 错误回灌 | `raise_on_error=False` + trace | 一条失败中断整个计划 |

**LLM 只替代第一行**。把执行逻辑写进 Prompt 或让模型「记住」工具状态，都是把 Host 的职责错放。

## 5. 确定性 planner 的价值

本例的 `steps` 是写死的：

```python
steps = [
    Step("inventory_check_stock", {"sku": "KEYBOARD"}),
    Step("pricing_quote", {"sku": "KEYBOARD", "qty": 3}),
    Step("inventory_reserve", {"sku": "KEYBOARD", "qty": 3}),
    Step("inventory_reserve", {"sku": "MOUSE", "qty": 99}),
]
```

好处：

- 离线可跑，不依赖 API key；
- 每次执行结果一致，可写断言；
- 出问题时能逐条对比 trace，而不是猜模型为什么这么调。

真实项目可以先用确定性 planner 把链路跑通，再把「生成 steps」替换成 LLM，执行层完全不用改。

## 6. 错误恢复策略

```python
for step, message in failures:
    if step.tool != "inventory_reserve" or "库存不足" not in message:
        continue
    check = await host.run([Step("inventory_check_stock", {"sku": sku})], trace)
    available = check["inventory_check_stock"]["available"]
    if available > 0:
        await host.run([Step("inventory_reserve", {"sku": sku, "qty": available})], trace)
```

这是一个**确定性策略**，不是「让模型再试一次」：

- 只对特定错误（库存不足）生效；
- 先查真实可用量，再决定重试数量；
- 每次恢复都写入 trace，可审计。

生产里可以把策略换成「查替代品」「拆单」「通知人工」，但结构不变。

## 7. 三种验证方式

**client.py**：看完整轨迹与最终结果。

**pytest**：断言「先失败后恢复」「跳过非法步骤」「库存真的减少」。

**接入 LLM（练习）**：把 `steps` 换成一个函数 `plan(goal, tools) -> list[Step]`，内部调用任意模型；其余代码不变。

## 8. 常见坑

**① 把 `raise_on_error` 留在默认 True**

第一条失败就抛异常，计划中断，trace 也断了。

**② 不校验参数就调用**

模型可能漏参数、传错类型。Host 至少检查 `required`，更好的是用 JSON Schema 校验。

**③ 用工具名当唯一键存结果**

同一工具调用多次会互相覆盖。用 `(step_index, tool)` 或列表保存。

**④ 恢复逻辑写在工具里**

工具只应报告「库存不足」，不该自己决定「查替代品还是拆单」。策略属于 Host。

**⑤ 没有 trace**

出问题只能看最终结果，无法定位是哪一步、参数是什么、错误原文是什么。

**⑥ ClientGroup 名字拼错**

工具名是 `{server}_{tool}`，例如 `inventory_check_stock`。调试时先打印 `list_tools()`。

## 9. 与 2.x / 3.x 的差异

- `ClientGroup` 是 4.0 新增；2.x 需要自己维护多个 Client 的路由表。
- `call_tool(..., raise_on_error=False)` 在 3.x 之后稳定。
- 4.x 的 `structured_content` / `data` 让 Host 更容易做结构化汇总。
- 完整差异见 [`docs/03-compat.md`](../docs/03-compat.md)。

## 10. 练习

1. 把 `steps` 换成 LLM 生成：给定目标「给 5 人团队买键盘，预算 2500」，让模型输出 `list[Step]`，执行层不变。
2. 加一个「预算校验」：报价超过预算时，自动降规格或减少数量。
3. 把 trace 存成 JSONL，写一个脚本统计每步耗时与失败率。
4. 给 Host 加并发：无依赖的步骤用 `asyncio.gather` 并行执行。

## 11. 延伸阅读

- FastMCP Client Groups：<https://gofastmcp.com/docs/clients/client-groups>
- 调用工具与错误：<https://gofastmcp.com/docs/clients/tools>
- MCP 架构：<https://modelcontextprotocol.io/docs/learn/architecture>
