from __future__ import annotations

from typing import Any

from .batch import dry_run_document, run_batch_document
from .config import Settings
from .doctor import diagnose
from .policy import Policy
from .provenance import verify_run_bundle
from .registry import NodeRegistry
from .scheduler import BackgroundScheduler

INSTRUCTIONS = """
AspenOps is a deterministic execution fabric, not an unrestricted COM shell.

Required workflow:
1. Call system_info.
2. Inspect the case-specific semantic registry with list_semantic_variables.
3. Call dry_run_request before any write or solve.
4. Use run_batch_sync only for small bounded work; submit_batch for DOE/optimization.
5. Poll job_status and fetch job_result. Preserve the returned evidence bundle.
6. Accept a process result only when ok=true. Communication, engine return, convergence,
   feasibility and balances are separate states.

Never invent Aspen tree paths, bypass allowed roots, overwrite the source model, expose arbitrary
Python/VBA/shell/COM execution, or represent Mock output as licensed Aspen physical validation.
""".strip()


def build_server(settings: Settings | None = None) -> Any:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError("Install the 'agent' extra: uv sync --extra agent") from exc

    active_settings = settings or Settings.from_env()
    active_settings.state_dir.mkdir(parents=True, exist_ok=True)
    scheduler = BackgroundScheduler(active_settings)
    scheduler.start()
    mcp = FastMCP("AspenOps 1.0", instructions=INSTRUCTIONS)

    @mcp.tool()
    def system_info() -> dict[str, Any]:
        """Return runtime, policy, worker limits and locally registered Aspen COM candidates."""
        return diagnose(active_settings, probe=False)

    @mcp.tool()
    def list_semantic_variables(registry_path: str) -> dict[str, Any]:
        """List allowlisted variables, units, identifiers and verification status."""
        policy = Policy(active_settings.mode, active_settings.allowed_roots)
        path = policy.assert_path(registry_path)
        registry = NodeRegistry(path)
        return {
            "name": registry.name,
            "version": registry.version,
            "schema": registry.schema,
            "sha256": registry.sha256,
            "variables": registry.describe(),
        }

    @mcp.tool()
    def dry_run_request(request: dict[str, Any]) -> dict[str, Any]:
        """Validate paths, policy, semantic keys, identifiers, units, bounds and worker caps."""
        return dry_run_document(request, active_settings)

    @mcp.tool()
    def run_batch_sync(request: dict[str, Any]) -> dict[str, Any]:
        """Run a small batch synchronously; prefer submit_batch for long simulator work."""
        validation = dry_run_document(request, active_settings)
        if validation["evaluations"] > 16:
            raise ValueError("Synchronous MCP runs are limited to 16 points; use submit_batch")
        return {"validation": validation, "results": run_batch_document(request, active_settings)}

    @mcp.tool()
    def submit_batch(request: dict[str, Any]) -> dict[str, str]:
        """Validate and submit a durable background batch; returns a stable job ID."""
        return {"job_id": scheduler.submit(request)}

    @mcp.tool()
    def job_status(job_id: str) -> dict[str, Any]:
        """Return durable pending/running/completed/failed/cancelled/interrupted state."""
        record = scheduler.store.get(job_id)
        return {"found": record is not None, "job": record}

    @mcp.tool()
    def job_result(job_id: str) -> dict[str, Any]:
        """Return completed point results and immutable evidence-bundle path."""
        record = scheduler.store.get(job_id)
        if record is None:
            return {"found": False}
        if record["status"] != "completed":
            return {
                "found": True,
                "status": record["status"],
                "error": record["error"],
                "cancel_requested": record["cancel_requested"],
            }
        return {
            "found": True,
            "status": "completed",
            "results": record["results"],
            "bundle_path": record["bundle_path"],
        }

    @mcp.tool()
    def list_recent_jobs(limit: int = 20) -> dict[str, Any]:
        """List recent durable jobs without exposing request bodies or proprietary model data."""
        return {"jobs": scheduler.store.list_recent(limit)}

    @mcp.tool()
    def cancel_job(job_id: str) -> dict[str, Any]:
        """Cancel pending work or mark running work for cancellation after its isolated call."""
        return {"cancel_requested": scheduler.store.cancel(job_id)}

    @mcp.tool()
    def verify_evidence_bundle(bundle_path: str) -> dict[str, Any]:
        """Verify request/result hashes and structural integrity of a run evidence bundle."""
        path = Policy(active_settings.mode, active_settings.allowed_roots).assert_path(bundle_path)
        return verify_run_bundle(path)

    return mcp


def main() -> None:
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
