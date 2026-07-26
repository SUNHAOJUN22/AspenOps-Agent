from __future__ import annotations

import asyncio
import json

from aspenops_nexus.mcp_server import _require_supported_mcp_sdk, build_server


async def main() -> None:
    sdk_version = _require_supported_mcp_sdk()
    server = build_server(start_scheduler=False)
    tools = await server.list_tools()
    print(
        json.dumps(
            {
                "sdk_version": sdk_version,
                "count": len(tools),
                "tools": [tool.name for tool in tools],
            }
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
