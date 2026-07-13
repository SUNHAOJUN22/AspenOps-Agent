import asyncio

from aspenops_nexus.mcp_server import build_server


def test_mcp_surface_is_narrow_and_typed() -> None:
    async def list_names() -> list[str]:
        server = build_server()
        tools = await server.list_tools()
        return [tool.name for tool in tools]

    names = asyncio.run(list_names())
    assert names == [
        "system_info",
        "list_semantic_variables",
        "dry_run_request",
        "run_batch_sync",
        "submit_batch",
        "job_status",
        "job_result",
        "list_recent_jobs",
        "cancel_job",
        "verify_evidence_bundle",
    ]
    forbidden = {"execute_code", "call_com_method", "run_shell", "run_vba", "eval"}
    assert forbidden.isdisjoint(names)
