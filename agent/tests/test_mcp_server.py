import asyncio
import os
import sys

import pytest

mcp = pytest.importorskip("mcp")
from mcp.client.stdio import stdio_client


def test_stdio_client_discovers_tools_and_validates_arguments(tmp_path):
    async def interact():
        options = mcp.StdioServerParameters(
            command=sys.executable,
            args=["-m", "agrireg_agent.mcp_server"],
            env={**os.environ, "AGENT_MILVUS_URI": "", "AGENT_DATA_DIR": str(tmp_path)},
        )
        async with stdio_client(options) as (receive, send):
            async with mcp.ClientSession(receive, send) as session:
                await session.initialize()
                tools = {tool.name: tool for tool in (await session.list_tools()).tools}
                assert set(tools) == {"find_relation_path", "search_documents", "search_entity"}
                assert tools["find_relation_path"].inputSchema["required"] == ["source", "target"]
                invalid = await session.call_tool("search_entity", {"keyword": " "})
                assert invalid.isError
                disabled = await session.call_tool("search_documents", {"request": {"query": "登记状态"}})
                assert disabled.isError
                assert "not configured" in disabled.content[0].text

    asyncio.run(asyncio.wait_for(interact(), timeout=15))
