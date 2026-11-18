"""0105 · 读取四种资源，并验证路径穿越会被拒绝。

运行：uv run python client.py
"""

import asyncio

from fastmcp import Client
from server import mcp


async def main() -> None:
    async with Client(mcp) as client:
        resources = await client.list_resources()
        templates = await client.list_resource_templates()
        print(f"静态资源：{[str(item.uri) for item in resources]}")
        print(f"模板资源：{[item.uri_template for item in templates]}")

        print("\n--- 静态 docs://guide ---")
        content = await client.read_resource("docs://guide")
        print(content[0].text.splitlines()[0])

        print("\n--- 模板 docs://intro ---")
        content = await client.read_resource("docs://intro")
        print(content[0].text.splitlines()[0])

        print("\n--- 通配 files://advanced/tips ---")
        content = await client.read_resource("files://advanced/tips")
        print(content[0].text.splitlines()[0])

        print("\n--- 查询参数 items://catalog?limit=1&tag=mcp ---")
        content = await client.read_resource("items://catalog?limit=1&tag=mcp")
        print(content[0].text)

        print("\n--- 多内容 report://summary ---")
        content = await client.read_resource("report://summary")
        print([(item.mime_type, item.text[:30]) for item in content])

        print("\n--- 路径穿越 files://../secret ---")
        try:
            await client.read_resource("files://../secret")
        except Exception as exc:  # 客户端看到的是协议层错误，不是服务端的 ResourceError
            print(f"已拒绝（{type(exc).__name__}）：{exc}")
        else:
            raise SystemExit("路径穿越竟然成功了，资源安全配置有问题！")


if __name__ == "__main__":
    asyncio.run(main())
