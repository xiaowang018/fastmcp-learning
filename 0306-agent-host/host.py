"""0306 · 最小 MCP Host：确定性 planner + 工具调用循环。

真实 Host 里，LLM 负责「生成计划」；执行、参数校验、错误恢复、结果汇总
仍然由代码完成。这个文件用固定计划替代 LLM，所以离线、可断言、可调试。
"""

from dataclasses import dataclass, field

from fastmcp import Client, ClientGroup


@dataclass
class Step:
    tool: str
    arguments: dict
    note: str = ""


@dataclass
class Trace:
    events: list[dict] = field(default_factory=list)

    def add(self, kind: str, tool: str, detail: str, data=None) -> None:
        self.events.append({"kind": kind, "tool": tool, "detail": detail, "data": data})


class Host:
    """一个只做四件事的 Host：发现、路由、校验、错误回灌。"""

    def __init__(self, group: ClientGroup):
        self.group = group
        self.schemas: dict[str, dict] = {}
        self.failures: list[tuple[Step, str]] = []

    async def discover(self) -> list[str]:
        tools = await self.group.list_tools()
        self.schemas = {tool.name: tool.input_schema for tool in tools}
        return sorted(self.schemas)

    def validate(self, step: Step) -> str | None:
        if step.tool not in self.schemas:
            return f"未知工具：{step.tool}"
        required = self.schemas[step.tool].get("required", [])
        missing = [key for key in required if key not in step.arguments]
        if missing:
            return f"缺少必填参数：{missing}"
        return None

    async def run(self, steps: list[Step], trace: Trace) -> dict:
        results: dict = {}
        self.failures = []
        for index, step in enumerate(steps, 1):
            problem = self.validate(step)
            if problem:
                trace.add("skip", step.tool, problem)
                continue

            trace.add("call", step.tool, f"step {index}: {step.arguments}")
            result = await self.group.call_tool(step.tool, step.arguments, raise_on_error=False)
            if result.is_error:
                message = result.content[0].text
                trace.add("error", step.tool, message)
                results[step.tool] = {"error": message}
                self.failures.append((step, message))
            else:
                trace.add("ok", step.tool, str(result.data), result.data)
                results[step.tool] = result.data
        return results


async def execute_plan(steps: list[Step], servers: dict | None = None) -> tuple[Trace, dict]:
    """执行计划；servers 不传时按当前目录导入两个内置服务器。"""
    if servers is None:
        from pricing_server import pricing
        from server import inventory

        servers = {"inventory": inventory, "pricing": pricing}

    trace = Trace()
    group = ClientGroup({name: Client(server) for name, server in servers.items()})

    async with group:
        host = Host(group)
        names = await host.discover()
        trace.add("discover", "-", f"{len(names)} 个工具：{names}")

        results = await host.run(steps, trace)
        failures = list(host.failures)

        # 确定性恢复：预占失败时，查可用量并按可用量重试一次
        for step, message in failures:
            if step.tool != "inventory_reserve" or "库存不足" not in message:
                continue

            sku = step.arguments["sku"]
            check = await host.run([Step("inventory_check_stock", {"sku": sku})], trace)
            available = (check.get("inventory_check_stock") or {}).get("available", 0)
            if available > 0:
                retry = await host.run(
                    [Step("inventory_reserve", {"sku": sku, "qty": available}, "按可用量重试")],
                    trace,
                )
                outcome = retry.get("inventory_reserve")
                if isinstance(outcome, dict) and "error" not in outcome:
                    results["inventory_reserve"] = outcome
    return trace, results
