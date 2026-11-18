"""0107 · Context：工具与服务器之间的那根线。

Context 让工具能：上报进度、写日志、读资源、拿请求/会话标识、存取请求内状态。
注意：协议 2026-07-28 起，每次调用都是独立会话，set_state 不会跨调用保留。
"""

import asyncio
import json
import sys

from fastmcp import Context, FastMCP

mcp = FastMCP(
    name="ContextDemo",
    instructions="演示 Context 的进度、日志、资源读取与请求内状态。",
)


@mcp.resource("policy://summary")
def summary_policy() -> str:
    """摘要规范：工具在运行时读取它，而不是把规则硬编码在函数里。"""
    return "摘要要求：不超过 80 字；保留数字与结论；不要加入原文没有的推断。"


@mcp.tool
async def summarize(text: str, ctx: Context) -> dict:
    """按 policy://summary 的规范生成摘要（演示 read_resource + 进度）。"""
    await ctx.report_progress(0, 2, "读取摘要规范")
    policy = await ctx.read_resource("policy://summary")
    # Context.read_resource 返回 ResourceResult，内容在 .contents[0].content
    rule = policy.contents[0].content

    await ctx.report_progress(1, 2, "处理文本")
    await asyncio.sleep(0.05)

    await ctx.report_progress(2, 2, "完成")
    return {
        "rule": rule,
        "chars": len(text),
        "preview": text[:40],
    }


@mcp.tool
async def long_task(steps: int = 3, ctx: Context = None) -> str:
    """带进度的长任务；steps 控制进度条步数。"""
    for index in range(1, steps + 1):
        await asyncio.sleep(0.05)
        await ctx.report_progress(index, steps, f"第 {index}/{steps} 步")
    return f"完成 {steps} 步"


@mcp.tool
async def state_demo(value: str, ctx: Context = None) -> dict:
    """演示请求内状态：同一次调用里 set/get 有效，跨调用会重置。"""
    before = await ctx.get_state("draft")
    await ctx.set_state("draft", value)
    after = await ctx.get_state("draft")
    return {
        "before": before,
        "after": after,
        "request_id": ctx.request_id,
        "session_id": ctx.session_id,
    }


@mcp.tool
async def logging_demo(message: str, ctx: Context = None) -> str:
    """演示日志：ctx.info 走 MCP 日志通知；stderr 是 stdio 服务器唯一安全的旁路。"""
    print(f"[stderr] 这条只进服务端日志，不污染协议流：{message}", file=sys.stderr)
    await ctx.info(f"收到消息：{message}")
    await ctx.warning("这是一个 warning 级别示例")
    return json.dumps({"logged": message}, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
