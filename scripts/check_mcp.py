from __future__ import annotations

import asyncio
import json

from aspenops_nexus.mcp_server import build_server


async def main() -> None:
    server = build_server()
    tools = await server.list_tools()
    print(json.dumps({"count": len(tools), "tools": [tool.name for tool in tools]}))


if __name__ == "__main__":
    asyncio.run(main())
