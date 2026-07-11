import asyncio

from aspenops.mcp_server import create_server


def test_mcp_server_registers_narrow_tool_surface() -> None:
    server = create_server()
    tools = asyncio.run(server.list_tools())
    names = {tool.name for tool in tools}
    assert names == {
        "system_info",
        "open_session",
        "close_session",
        "get_values",
        "set_values",
        "reinitialize",
        "run_simulation",
        "diagnose_session",
        "save_case",
    }
