"""MCP 客户端封装：以 stdio 方式连接本地 sqlite-tools MCP Server。"""
from __future__ import annotations

import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPClient:
    """同步封装 MCP 调用，供各 Agent 使用。"""

    def __init__(self, db_path: str | Path, server_script: str | Path | None = None):
        self.db_path = str(Path(db_path).resolve())
        self.server_script = str(Path(server_script or Path(__file__).parent.parent / "mcp_servers" / "sqlite_tools_server.py").resolve())

    @asynccontextmanager
    async def _session(self):
        params = StdioServerParameters(
            command=sys.executable,  # 与客户端同一解释器，保证子进程可导入 mcp
            args=[self.server_script, "--db", self.db_path],
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session

    async def call_tool_async(self, name: str, arguments: dict) -> dict:
        async with self._session() as session:
            result = await session.call_tool(name, arguments)
            text = result.content[0].text if result.content else "{}"
            return json.loads(text)

    def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        """同步入口：调用 MCP 工具并返回解析后的 dict。"""
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.call_tool_async(name, arguments or {}))
        # 已在异步环境中时新建线程跑事件循环，避免嵌套冲突
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(1) as pool:
            return pool.submit(asyncio.run, self.call_tool_async(name, arguments or {})).result()
