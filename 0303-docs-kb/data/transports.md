# 传输与协议

FastMCP 支持三种连接：进程内、stdio 子进程、HTTP。

- 本地宿主（Claude Desktop、Cursor）通常用 stdio。
- 远程与多客户端用 Streamable HTTP。
- 4.x 默认协商无会话的现代协议，跨调用状态不保留。

切换传输不需要改工具代码，只需要改 `mcp.run(transport=...)`。
