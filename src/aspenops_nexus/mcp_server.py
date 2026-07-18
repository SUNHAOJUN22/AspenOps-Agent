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
5. Poll job_status and fetch job_result. Preserve the returned integrity bundle.
6. Accept a process result only when ok=true. Communication, engine return, convergence,
   feasibility and balances are separate states.

Never invent Aspen tree paths, bypass allowed roots, overwrite the source model, expose arbitrary
Python/VBA/shell/COM execution, or represent Mock output as licensed Aspen physical validation.
""".strip()


def build_server(
    settings: Settings | None = None,
    *,
    start_scheduler: bool = True,
) -> Any:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError("Install the 'agent' extra: uv sync --extra agent") from exc

    active_settings = settings or Settings.from_env()
    active_settings.state_dir.mkdir(parents=True, exist_ok=True)
    scheduler = BackgroundScheduler(active_settings)
    if start_scheduler:
        scheduler.start()
    mcp = FastMCP("AspenOps 2.0", instructions=INSTRUCTIONS)

    @mcp.tool()
    def system_info() -> dict[str, Any]:
        """Return runtime, policy, worker limits and locally registered Aspen COM candidates."""
        result = diagnose(active_settings, probe=False)
        result["pool_manager"] = scheduler.pool_manager.stats()
        return result

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
        results = run_batch_document(
            request,
            active_settings,
            pool_manager=scheduler.pool_manager,
        )
        return {"validation": validation, "results": results}

    @mcp.tool()
    def submit_batch(request: dict[str, Any]) -> dict[str, str]:
        """Validate and submit a durable background batch; returns a stable job ID."""
        return {"job_id": scheduler.submit(request)}

    @mcp.tool()
    def submit_optimization(request: dict[str, Any]) -> dict[str, str]:
        """Submit a durable budgeted optimization job."""
        if "optimization" not in request:
            raise ValueError("Optimization request requires an optimization object")
        return {"job_id": scheduler.submit(request)}

    @mcp.tool()
    def optimization_status(job_id: str) -> dict[str, Any]:
        """Return durable optimization lease, progress and cancellation state."""
        record = scheduler.store.get(job_id)
        return {"found": record is not None, "job": record}

    @mcp.tool()
    def optimization_result(job_id: str) -> dict[str, Any]:
        """Return the completed or cancelled optimization result."""
        record = scheduler.store.get(job_id)
        if record is None:
            return {"found": False}
        results = record.get("results")
        result = None
        if isinstance(results, list) and results:
            result = results[0]
        return {
            "found": True,
            "status": record["status"],
            "result": result,
            "bundle_path": record["bundle_path"],
            "error": record["error"],
        }

    @mcp.tool()
    def cancel_optimization(job_id: str) -> dict[str, Any]:
        """Cancel a pending optimization or enforce its active worker deadline."""
        return {"cancel_requested": scheduler.cancel(job_id)}

    @mcp.tool()
    def job_status(job_id: str) -> dict[str, Any]:
        """Return durable leased job state and progress metadata."""
        record = scheduler.store.get(job_id)
        return {"found": record is not None, "job": record}

    @mcp.tool()
    def job_result(job_id: str) -> dict[str, Any]:
        """Return completed or cancelled point results and integrity-bundle path."""
        record = scheduler.store.get(job_id)
        if record is None:
            return {"found": False}
        if record["status"] not in {"completed", "cancelled"}:
            return {
                "found": True,
                "status": record["status"],
                "error": record["error"],
                "error_class": record["error_class"],
                "cancel_requested": record["cancel_requested"],
                "last_completed_point": record["last_completed_point"],
            }
        return {
            "found": True,
            "status": record["status"],
            "results": record["results"],
            "bundle_path": record["bundle_path"],
            "last_completed_point": record["last_completed_point"],
        }

    @mcp.tool()
    def list_recent_jobs(limit: int = 20) -> dict[str, Any]:
        """List recent durable jobs without exposing request bodies or proprietary model data."""
        return {"jobs": scheduler.store.list_recent(limit)}

    @mcp.tool()
    def cancel_job(job_id: str) -> dict[str, Any]:
        """Cancel pending work or enforce a deadline on an active isolated worker call."""
        return {"cancel_requested": scheduler.cancel(job_id)}

    @mcp.tool()
    def verify_evidence_bundle(bundle_path: str) -> dict[str, Any]:
        """Verify request/result hashes and structural integrity of a run bundle."""
        path = Policy(active_settings.mode, active_settings.allowed_roots).assert_path(bundle_path)
        return verify_run_bundle(path)

    return mcp


def main() -> None:
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
