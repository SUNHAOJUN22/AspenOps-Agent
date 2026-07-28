from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .config import Settings
from .evaluation_plan import EvaluationPlanCompiler
from .models import EvaluationRequest, VariableWrite
from .policy import Policy, PolicyError
from .pool import CasePool
from .registry import NodeRegistry

if TYPE_CHECKING:
    from .pool_manager import PoolManager


@dataclass(frozen=True, slots=True)
class _PreparedBatch:
    model_path: Path
    registry_path: Path
    backend_name: str
    requests: tuple[EvaluationRequest, ...]
    requested_workers: int
    effective_workers: int
    request_bytes: int
    registry_sha256: str
    writes: int
    declared_reads: int
    unique_read_nodes: int
    semantic_operations: int


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return {str(key): item for key, item in value.items()}


def _array(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    return value


def _object_array(value: Any, label: str) -> list[dict[str, Any]]:
    return [_object(item, f"{label}[{index}]") for index, item in enumerate(_array(value, label))]


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    if value < 1:
        raise ValueError(f"{label} must be positive")
    return value


def _request_size_bytes(data: dict[str, Any]) -> int:
    try:
        encoded = json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("Batch request must contain finite JSON-compatible values") from exc
    return len(encoded)


def expand_batch_document(
    data: dict[str, Any],
    *,
    default_backend: str = "mock",
) -> list[EvaluationRequest]:
    root = _object(data, "Batch request")
    missing = [name for name in ("model_path", "registry_path") if name not in root]
    if missing:
        raise ValueError(f"Batch request is missing required fields: {', '.join(missing)}")

    reads = _object_array(root.get("reads", []), "reads")
    constraints = _object_array(root.get("constraints", []), "constraints")
    balances = _object_array(root.get("balances", []), "balances")
    metadata = _object(root.get("metadata", {}), "metadata")
    common = {
        "model_path": root["model_path"],
        "registry_path": root["registry_path"],
        "backend": root.get("backend", default_backend),
        "reads": reads,
        "constraints": constraints,
        "balances": balances,
        "reset_mode": root.get(
            "reset_mode",
            "reinitialize" if root.get("reinitialize", True) else "warm_start",
        ),
        "timeout_s": root.get("timeout_s", 1200),
        "metadata": metadata,
    }
    base_writes = [
        VariableWrite.from_dict(item)
        for item in _object_array(root.get("base_writes", []), "base_writes")
    ]
    points = _array(root.get("points", [{}]), "points")
    if not points:
        raise ValueError("points must be a non-empty list")

    requests: list[EvaluationRequest] = []
    for point_index, raw_point in enumerate(points):
        writes = list(base_writes)
        point_metadata: dict[str, Any] = {}
        if isinstance(raw_point, list):
            point_writes = _object_array(raw_point, f"points[{point_index}]")
            writes.extend(VariableWrite.from_dict(item) for item in point_writes)
        elif isinstance(raw_point, dict):
            point = _object(raw_point, f"points[{point_index}]")
            point_writes = _object_array(
                point.get("writes", []),
                f"points[{point_index}].writes",
            )
            writes.extend(VariableWrite.from_dict(item) for item in point_writes)
            point_metadata = _object(
                point.get("metadata", {}),
                f"points[{point_index}].metadata",
            )
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
        merged_metadata = dict(metadata)
        merged_metadata.update(point_metadata)
        merged_metadata["point_index"] = point_index
        request_data["metadata"] = merged_metadata
        requests.append(EvaluationRequest.from_dict(request_data))
    return requests


def _validate_real_backend_policy(backend_name: str, settings: Settings) -> None:
    if backend_name == "mock":
        return
    if not settings.allowed_roots:
        raise PolicyError("Real simulator requests require ASPENOPS_ALLOWED_ROOTS")
    if backend_name != settings.backend:
        raise PolicyError("Real simulator request backend must match ASPENOPS_BACKEND")

    root_paths = tuple(root.expanduser() for root in settings.allowed_roots)
    if any(not root.is_absolute() for root in root_paths):
        raise PolicyError("Real simulator allowed roots must be absolute")

    state_path = settings.state_dir.expanduser()
    if not state_path.is_absolute():
        raise PolicyError("Real simulator state directory must be absolute")

    state_dir = state_path.resolve()
    roots = tuple(root.resolve() for root in root_paths)
    if not any(state_dir == root or root in state_dir.parents for root in roots):
        raise PolicyError("Real simulator state directory must be inside ASPENOPS_ALLOWED_ROOTS")


def _prepare_batch_document(data: dict[str, Any], settings: Settings) -> _PreparedBatch:
    root = _object(data, "Batch request")
    request_bytes = _request_size_bytes(root)
    if request_bytes > settings.max_request_bytes:
        raise ValueError(
            f"Batch request is {request_bytes} bytes; limit is {settings.max_request_bytes}"
        )

    raw_points = _array(root.get("points", [{}]), "points")
    if len(raw_points) > settings.max_batch_points:
        raise ValueError(
            f"Batch contains {len(raw_points)} points; limit is {settings.max_batch_points}"
        )

    requested_workers = _positive_int(
        root.get("workers", settings.effective_workers),
        "workers",
    )
    backend_name = str(root.get("backend", settings.backend)).strip().lower()
    _validate_real_backend_policy(backend_name, settings)

    policy = Policy(settings.mode, settings.allowed_roots)
    model_path = policy.assert_path(root.get("model_path", ""))
    registry_path = policy.assert_path(root.get("registry_path", ""))
    requests = expand_batch_document(root, default_backend=backend_name)
    if len(requests) > settings.max_batch_points:
        raise ValueError(
            f"Batch contains {len(requests)} points; limit is {settings.max_batch_points}"
        )

    registry = NodeRegistry(registry_path)
    plans = [EvaluationPlanCompiler.compile(registry, request, policy) for request in requests]
    writes = sum(plan.estimated_io.declared_writes for plan in plans)
    declared_reads = sum(plan.estimated_io.declared_reads for plan in plans)
    unique_reads = sum(plan.estimated_io.unique_read_nodes for plan in plans)
    semantic_operations = writes + declared_reads
    if semantic_operations > settings.max_semantic_operations:
        raise ValueError(
            "Batch requests "
            f"{semantic_operations} semantic operations; limit is "
            f"{settings.max_semantic_operations}"
        )

    return _PreparedBatch(
        model_path=model_path,
        registry_path=registry_path,
        backend_name=backend_name,
        requests=tuple(requests),
        requested_workers=requested_workers,
        effective_workers=min(requested_workers, settings.effective_workers),
        request_bytes=request_bytes,
        registry_sha256=registry.sha256,
        writes=writes,
        declared_reads=declared_reads,
        unique_read_nodes=unique_reads,
        semantic_operations=semantic_operations,
    )


def dry_run_document(data: dict[str, Any], settings: Settings) -> dict[str, Any]:
    prepared = _prepare_batch_document(data, settings)
    return {
        "ok": True,
        "model_path": str(prepared.model_path),
        "registry_path": str(prepared.registry_path),
        "registry_sha256": prepared.registry_sha256,
        "request_bytes": prepared.request_bytes,
        "evaluations": len(prepared.requests),
        "writes": prepared.writes,
        "reads": len(prepared.requests[0].reads) * len(prepared.requests),
        "declared_reads": prepared.declared_reads,
        "unique_read_nodes": prepared.unique_read_nodes,
        "avoided_duplicate_reads": prepared.declared_reads - prepared.unique_read_nodes,
        "semantic_operations": prepared.semantic_operations,
        "requested_workers": prepared.requested_workers,
        "effective_workers": prepared.effective_workers,
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
    prepared = _prepare_batch_document(data, settings)
    requests = list(prepared.requests)
    if pool_manager is None:
        return _evaluate_with_new_pool(
            backend_name=prepared.backend_name,
            model_path=prepared.model_path,
            registry_path=prepared.registry_path,
            workers=prepared.effective_workers,
            settings=settings,
            requests=requests,
            cancel_check=cancel_check,
            pool_observer=pool_observer,
        )
    with pool_manager.acquire(
        backend_name=prepared.backend_name,
        model_path=prepared.model_path,
        registry_path=prepared.registry_path,
        workers=prepared.effective_workers,
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
    if not isinstance(data, dict):
        raise ValueError("Batch request must be a JSON object")
    return run_batch_document(data, settings)
