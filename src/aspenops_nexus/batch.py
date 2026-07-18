from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .config import Settings
from .evaluation_plan import EvaluationPlanCompiler
from .models import EvaluationRequest, VariableWrite
from .policy import Policy
from .pool import CasePool
from .registry import NodeRegistry

if TYPE_CHECKING:
    from .pool_manager import PoolManager


def expand_batch_document(data: dict[str, Any]) -> list[EvaluationRequest]:
    if not isinstance(data, dict):
        raise ValueError("Batch request must be a JSON object")
    common = {
        "model_path": data["model_path"],
        "registry_path": data["registry_path"],
        "backend": data.get("backend", "mock"),
        "reads": data.get("reads", []),
        "constraints": data.get("constraints", []),
        "balances": data.get("balances", []),
        "reset_mode": data.get(
            "reset_mode", "reinitialize" if data.get("reinitialize", True) else "warm_start"
        ),
        "timeout_s": data.get("timeout_s", 1200),
        "metadata": data.get("metadata", {}),
    }
    base_writes = [VariableWrite.from_dict(x) for x in data.get("base_writes", [])]
    points = data.get("points", [{}])
    if not isinstance(points, list) or not points:
        raise ValueError("points must be a non-empty list")
    requests: list[EvaluationRequest] = []
    for point_index, point in enumerate(points):
        writes = list(base_writes)
        point_metadata: dict[str, Any] = {}
        if isinstance(point, list):
            writes.extend(VariableWrite.from_dict(x) for x in point)
        elif isinstance(point, dict):
            raw_writes = point.get("writes", [])
            if not isinstance(raw_writes, list):
                raise ValueError(f"Point {point_index} writes must be a list")
            writes.extend(VariableWrite.from_dict(x) for x in raw_writes)
            point_metadata = dict(point.get("metadata", {}))
        else:
            raise ValueError(f"Point {point_index} must be an object or a writes list")
        request_data = dict(common)
        request_data["writes"] = [
            {
                "key": item.key,
                "identifiers": item.identifiers,
                "value": item.value,
                "unit": item.unit,
            }
            for item in writes
        ]
        metadata = dict(common["metadata"])
        metadata.update(point_metadata)
        metadata["point_index"] = point_index
        request_data["metadata"] = metadata
        requests.append(EvaluationRequest.from_dict(request_data))
    return requests


def dry_run_document(data: dict[str, Any], settings: Settings) -> dict[str, Any]:
    policy = Policy(settings.mode, settings.allowed_roots)
    model_path = policy.assert_path(data["model_path"])
    registry_path = policy.assert_path(data["registry_path"])
    requests = expand_batch_document(data)
    registry = NodeRegistry(registry_path)
    plans = [EvaluationPlanCompiler.compile(registry, request, policy) for request in requests]
    writes = sum(plan.estimated_io.declared_writes for plan in plans)
    declared_reads = sum(plan.estimated_io.declared_reads for plan in plans)
    unique_reads = sum(plan.estimated_io.unique_read_nodes for plan in plans)
    semantic_operations = writes + declared_reads
    return {
        "ok": True,
        "model_path": str(model_path),
        "registry_path": str(registry_path),
        "registry_sha256": registry.sha256,
        "evaluations": len(requests),
        "writes": writes,
        "reads": len(requests[0].reads) * len(requests),
        "declared_reads": declared_reads,
        "unique_read_nodes": unique_reads,
        "avoided_duplicate_reads": declared_reads - unique_reads,
        "semantic_operations": semantic_operations,
        "requested_workers": int(data.get("workers", settings.effective_workers)),
        "effective_worker_cap": settings.effective_workers,
    }


def _run_on_pool(
    pool: CasePool,
    requests: list[EvaluationRequest],
    *,
    cancel_check: Callable[[], bool] | None,
    pool_observer: Callable[[CasePool | None], None] | None,
) -> list[dict[str, Any]]:
    if pool_observer is not None:
        pool_observer(pool)
    try:
        return [
            result.to_dict() for result in pool.evaluate_many(requests, cancel_check=cancel_check)
        ]
    finally:
        if pool_observer is not None:
            pool_observer(None)


def _evaluate_with_new_pool(
    *,
    backend_name: str,
    model_path: Path,
    registry_path: Path,
    workers: int,
    settings: Settings,
    requests: list[EvaluationRequest],
    cancel_check: Callable[[], bool] | None,
    pool_observer: Callable[[CasePool | None], None] | None,
) -> list[dict[str, Any]]:
    with CasePool(
        backend_name=backend_name,
        model_path=model_path,
        registry_path=registry_path,
        workers=workers,
        visible=settings.visible,
        cache_path=settings.state_dir / "cache.sqlite3",
        worker_max_points=settings.worker_max_points,
        worker_max_age_s=settings.worker_max_age_s,
        startup_timeout_s=settings.startup_timeout_s,
        cache_failures=settings.cache_failures,
    ) as pool:
        return _run_on_pool(
            pool,
            requests,
            cancel_check=cancel_check,
            pool_observer=pool_observer,
        )


def run_batch_document(
    data: dict[str, Any],
    settings: Settings,
    *,
    pool_manager: PoolManager | None = None,
    cancel_check: Callable[[], bool] | None = None,
    pool_observer: Callable[[CasePool | None], None] | None = None,
) -> list[dict[str, Any]]:
    dry_run_document(data, settings)
    policy = Policy(settings.mode, settings.allowed_roots)
    model_path = policy.assert_path(data["model_path"])
    registry_path = policy.assert_path(data["registry_path"])
    requests = expand_batch_document(data)
    workers = max(
        1, min(int(data.get("workers", settings.effective_workers)), settings.effective_workers)
    )
    backend_name = str(data.get("backend", settings.backend))
    if pool_manager is None:
        return _evaluate_with_new_pool(
            backend_name=backend_name,
            model_path=model_path,
            registry_path=registry_path,
            workers=workers,
            settings=settings,
            requests=requests,
            cancel_check=cancel_check,
            pool_observer=pool_observer,
        )
    with pool_manager.acquire(
        backend_name=backend_name,
        model_path=model_path,
        registry_path=registry_path,
        workers=workers,
        visible=settings.visible,
    ) as pool:
        return _run_on_pool(
            pool,
            requests,
            cancel_check=cancel_check,
            pool_observer=pool_observer,
        )


def run_batch_file(path: str | Path, settings: Settings) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return run_batch_document(data, settings)
