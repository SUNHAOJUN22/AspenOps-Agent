from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version as distribution_version
from pathlib import Path
from typing import Any

from .batch import dry_run_document, run_batch_document
from .config import Settings
from .doctor import diagnose
from .durable_request import pin_durable_request_paths
from .job_queries import list_recent_job_records
from .policy import Policy
from .provenance import verify_run_bundle
from .registry import NodeRegistry
from .scheduler import BackgroundScheduler

SUPPORTED_MCP_MAJOR = 1
MCP_INSTALL_CONSTRAINT = "mcp>=1.9,<2"

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

TOOL_NAMES = (
    "system_info",
    "list_semantic_variables",
    "dry_run_request",
    "run_batch_sync",
    "submit_batch",
    "submit_optimization",
    "optimization_status",
    "optimization_result",
    "cancel_optimization",
    "job_status",
    "job_result",
    "list_recent_jobs",
    "cancel_job",
    "verify_evidence_bundle",
)


def _require_supported_mcp_sdk() -> str:
    """Return the installed SDK version or fail before importing an incompatible API."""

    try:
        installed = distribution_version("mcp")
    except PackageNotFoundError as exc:
        raise RuntimeError(
            "Install the 'agent' extra: uv sync --frozen --extra agent"
        ) from exc

    major_text = installed.split(".", 1)[0]
    try:
        major = int(major_text)
    except ValueError as exc:
        raise RuntimeError(f"Cannot determine MCP SDK major version from {installed!r}") from exc
    if major != SUPPORTED_MCP_MAJOR:
        raise RuntimeError(
            "AspenOps 2.0 requires MCP Python SDK 1.x; install "
            f"'{MCP_INSTALL_CONSTRAINT}' instead of mcp {installed}."
        )
    return installed


@asynccontextmanager
async def _scheduler_lifespan(
    _server: Any,
    *,
    scheduler: BackgroundScheduler,
    start_scheduler: bool,
) -> AsyncIterator[None]:
    """Tie the durable Worker fabric to the MCP server startup/shutdown boundary."""

    try:
        if start_scheduler:
            scheduler.start()
        yield None
    finally:
        scheduler.stop()


class AspenOpsTools:
    """Transport-independent MCP tool facade over one durable Scheduler."""

    def __init__(self, settings: Settings, scheduler: BackgroundScheduler) -> None:
        self.settings = settings
        self.scheduler = scheduler

    @staticmethod
    def _durable_request(request: dict[str, Any]) -> dict[str, Any]:
        return pin_durable_request_paths(request, submission_cwd=Path.cwd())

    def system_info(self) -> dict[str, Any]:
        """Return runtime, policy, worker limits and locally registered Aspen COM candidates."""
        result = diagnose(self.settings, probe=False)
        result["pool_manager"] = self.scheduler.pool_manager.stats()
        return result

    def list_semantic_variables(self, registry_path: str) -> dict[str, Any]:
        """List allowlisted variables, units, identifiers and verification status."""
        policy = Policy(self.settings.mode, self.settings.allowed_roots)
        path = policy.assert_path(registry_path)
        registry = NodeRegistry(path)
        return {
            "name": registry.name,
            "version": registry.version,
            "schema": registry.schema,
            "sha256": registry.sha256,
            "variables": registry.describe(),
        }

    def dry_run_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Validate paths, policy, semantic keys, identifiers, units, bounds and worker caps."""
        return dry_run_document(request, self.settings)

    def run_batch_sync(self, request: dict[str, Any]) -> dict[str, Any]:
        """Run a small batch synchronously; prefer submit_batch for long simulator work."""
        validation = dry_run_document(request, self.settings)
        if validation["evaluations"] > 16:
            raise ValueError("Synchronous MCP runs are limited to 16 points; use submit_batch")
        results = run_batch_document(
            request,
            self.settings,
            pool_manager=self.scheduler.pool_manager,
        )
        return {"validation": validation, "results": results}

    def submit_batch(self, request: dict[str, Any]) -> dict[str, str]:
        """Validate and submit a durable background batch; returns a stable job ID."""
        return {"job_id": self.scheduler.submit(self._durable_request(request))}

    def submit_optimization(self, request: dict[str, Any]) -> dict[str, str]:
        """Submit a durable budgeted optimization job."""
        if "optimization" not in request:
            raise ValueError("Optimization request requires an optimization object")
        return {"job_id": self.scheduler.submit(self._durable_request(request))}

    def optimization_status(self, job_id: str) -> dict[str, Any]:
        """Return durable optimization lease, progress and cancellation state."""
        record = self.scheduler.store.get(job_id)
        return {"found": record is not None, "job": record}

    def optimization_result(self, job_id: str) -> dict[str, Any]:
        """Return the completed or cancelled optimization result."""
        record = self.scheduler.store.get(job_id)
        if record is None:
            return {"found": False}
        results = record.get("results")
        result = results[0] if isinstance(results, list) and results else None
        return {
            "found": True,
            "status": record["status"],
            "result": result,
            "bundle_path": record["bundle_path"],
            "error": record["error"],
        }

    def cancel_optimization(self, job_id: str) -> dict[str, Any]:
        """Cancel a pending optimization or enforce its active worker deadline."""
        return {"cancel_requested": self.scheduler.cancel(job_id)}

    def job_status(self, job_id: str) -> dict[str, Any]:
        """Return durable leased job state and progress metadata."""
        record = self.scheduler.store.get(job_id)
        return {"found": record is not None, "job": record}

    def job_result(self, job_id: str) -> dict[str, Any]:
        """Return completed or cancelled point results and integrity-bundle path."""
        record = self.scheduler.store.get(job_id)
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

    def list_recent_jobs(self, limit: int = 20) -> dict[str, Any]:
        """List recent durable jobs without exposing request bodies or proprietary model data."""
        return {"jobs": list_recent_job_records(self.scheduler.store.path, limit)}

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        """Cancel pending work or enforce a deadline on an active isolated worker call."""
        return {"cancel_requested": self.scheduler.cancel(job_id)}

    def verify_evidence_bundle(self, bundle_path: str) -> dict[str, Any]:
        """Verify request/result hashes and structural integrity of a run bundle."""
        path = Policy(self.settings.mode, self.settings.allowed_roots).assert_path(bundle_path)
        return verify_run_bundle(path)


def build_server(
    settings: Settings | None = None,
    *,
    start_scheduler: bool = True,
) -> Any:
    _require_supported_mcp_sdk()
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            "The installed MCP 1.x SDK is incomplete; reinstall the 'agent' extra"
        ) from exc

    active_settings = settings or Settings.from_env()
    active_settings.state_dir.mkdir(parents=True, exist_ok=True)
    scheduler = BackgroundScheduler(active_settings)
    tools = AspenOpsTools(active_settings, scheduler)

    @asynccontextmanager
    async def app_lifespan(server: Any) -> AsyncIterator[None]:
        async with _scheduler_lifespan(
            server,
            scheduler=scheduler,
            start_scheduler=start_scheduler,
        ):
            yield None

    mcp = FastMCP("AspenOps 2.0", instructions=INSTRUCTIONS, lifespan=app_lifespan)
    for name in TOOL_NAMES:
        mcp.tool()(getattr(tools, name))
    return mcp


def main() -> None:
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
