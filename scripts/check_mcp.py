from __future__ import annotations

import asyncio
import json
from pathlib import Path

from aspenops_nexus.mcp_server import _require_supported_mcp_sdk, build_server
from aspenops_nexus.wheel_metadata import inspect_wheel


async def main() -> None:
    sdk_version = _require_supported_mcp_sdk()
    server = build_server(start_scheduler=False)
    tools = await server.list_tools()

    dist_dir = Path("dist")
    wheel_candidates = sorted(dist_dir.glob("aspenops_nexus-*.whl"))
    wheel_metadata: dict[str, object]
    if wheel_candidates:
        wheel_metadata = inspect_wheel(dist_dir)
    else:
        wheel_metadata = {
            "ok": None,
            "status": "not_checked",
            "reason": "no built AspenOps Wheel found",
        }

    print(
        json.dumps(
            {
                "sdk_version": sdk_version,
                "count": len(tools),
                "tools": [tool.name for tool in tools],
                "wheel_metadata": wheel_metadata,
            },
            ensure_ascii=False,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
