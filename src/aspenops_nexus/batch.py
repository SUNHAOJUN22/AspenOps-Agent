from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import Settings
from .errors import ValidationError
from .jsonio import ensure_json_array, ensure_json_object, json_bytes, read_json_object
from .models import EvaluationRequest, VariableWrite
from .policy import Policy
from .pool import CasePool
from .registry import NodeRegistry

_BATCH_FIELDS = {
    "model_path",
    "registry_path",
    "backend",
    "workers",
    "reads",
    "constraints",
    "balances",
    "reset_mode",
    "reinitialize",
    "timeout_s",
    "metadata",
    "base_writes",
    "points",
}
_POINT_FIELDS = {"writes", "metadata"}
_VALID_BACKENDS = {"mock", "aspen_plus", "hysys"}


def _object(value: Any, name: str) -> dict[str, Any]:
    return ensure_json_object(value, name=name)


def _array(value: Any, name: str) -> list[Any]:
    return ensure_json_array(value, name=name)


def _reject_unknown(data: dict[str, Any], allowed: set[str], name: str) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ValidationError(f"Unknown fields in {name}: {', '.join(unknown)}")


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValidationError(f"{name} must be an integer >= 1")
    return value


def _requested_workers(data: dict[str, Any], settings: Settings) -> int:
    workers = _positive_int(data.get("workers", settings.effective_workers), "workers")
    if workers > settings.effective_workers:
        raise ValidationError(
            f"workers={workers} exceeds effective worker cap {settings.effective_workers}"
        )
    return workers


def _operation_count(request: EvaluationRequest) -> int:
    balance_terms = sum(len(balance.terms) for balance in request.balances)
    return len(request.writes) + len(request.reads) + len(request.constraints) + balance_terms


def _bounded_snapshot(data: dict[str, Any], settings: Settings) -> dict[str, Any]:
    request = ensure_json_object(data, name="Batch request")
    encoded = json_bytes(request, indent=None)
    if len(encoded) > settings.max_request_bytes:
        raise ValidationError(
            f"Batch request is {len(encoded)} bytes; maximum is {settings.max_request_bytes} bytes"
        )
    return read_json_object_bytes(encoded, name="Batch request")


def read_json_object_bytes(raw: bytes, *, name: str) -> dict[str, Any]:
    from .jsonio import strict_json_object

    return strict_json_object(raw, name=name)


def expand_batch_document(
    data: dict[str, Any],
    *,
    default_backend: str = "mock",
    max_points: int = 10_000,
    max_operations_per_request: int = 10_000,
) -> list[EvaluationRequest]:
    batch = _object(data, "Batch request")
    _reject_unknown(batch, _BATCH_FIELDS, "Batch request")
    if "model_path" not in batch or "registry_path" not in batch:
        raise ValidationError("Batch request requires model_path and registry_path")
    if default_backend not in _VALID_BACKENDS:
        raise ValidationError(f"Unsupported default backend: {default_backend!r}")
    backend = batch.get("backend", default_backend)
    if not isinstance(backend, str) or backend not in _VALID_BACKENDS:
        raise ValidationError(f"Unsupported backend: {backend!r}")
    point_limit = _positive_int(max_points, "max_points")
    operation_limit = _positive_int(
        max_operations_per_request,
        "max_operations_per_request",
    )
    common: dict[str, Any] = {
        "model_path": batch["model_path"],
        "registry_path": batch["registry_path"],
        "backend": backend,
        "reads": _array(batch.get("reads", []), "reads"),
        "constraints": _array(batch.get("constraints", []), "constraints"),
        "balances": _array(batch.get("balances", []), "balances"),
        "timeout_s": batch.get("timeout_s", 1200.0),
        "metadata": _object(batch.get("metadata", {}), "metadata"),
    }
    if "reset_mode" in batch:
        common["reset_mode"] = batch["reset_mode"]
    if "reinitialize" in batch:
        common["reinitialize"] = batch["reinitialize"]
    base_writes = [
        VariableWrite.from_dict(_object(item, "base write"))
        for item in _array(batch.get("base_writes", []), "base_writes")
    ]
    points = _array(batch.get("points", [{}]), "points")
    if not points:
        raise ValidationError("points must be a non-empty list")
    if len(points) > point_limit:
        raise ValidationError(f"points count {len(points)} exceeds maximum {point_limit}")
    requests: list[EvaluationRequest] = []
    for point_index, point in enumerate(points):
        writes = list(base_writes)
        point_metadata: dict[str, Any] = {}
        if isinstance(point, list):
            writes.extend(
                VariableWrite.from_dict(_object(item, f"point {point_index} write"))
                for item in point
            )
        elif isinstance(point, dict):
            point_object = _object(point, f"Point {point_index}")
            _reject_unknown(point_object, _POINT_FIELDS, f"Point {point_index}")
            writes.extend(
                VariableWrite.from_dict(_object(item, f"point {point_index} write"))
                for item in _array(point_object.get("writes", []), f"Point {point_index} writes")
            )
            point_metadata = _object(
                point_object.get("metadata", {}),
                f"Point {point_index} metadata",
            )
        else:
            raise ValidationError(f"Point {point_index} must be an object or a writes list")
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
        request = EvaluationRequest.from_dict(request_data)
        operations = _operation_count(request)
        if operations > operation_limit:
            raise ValidationError(
                f"Point {point_index} has {operations} semantic operations; "
                f"maximum is {operation_limit}"
            )
        requests.append(request)
    return requests


def _expand_with_settings(data: dict[str, Any], settings: Settings) -> list[EvaluationRequest]:
    snapshot = _bounded_snapshot(data, settings)
    return expand_batch_document(
        snapshot,
        default_backend=settings.backend,
        max_points=settings.max_batch_points,
        max_operations_per_request=settings.max_operations_per_request,
    )


def _input_paths(
    requests: list[EvaluationRequest],
    settings: Settings,
) -> tuple[Path, Path]:
    policy = Policy(settings.mode, settings.allowed_roots)
    model_path = policy.assert_input_file(requests[0].model_path)
    registry_path = policy.assert_input_file(
        requests[0].registry_path,
        max_bytes=settings.max_request_bytes,
        suffixes=(".json",),
    )
    return model_path, registry_path


def dry_run_document(data: dict[str, Any], settings: Settings) -> dict[str, Any]:
    requests = _expand_with_settings(data, settings)
    workers = _requested_workers(data, settings)
    model_path, registry_path = _input_paths(requests, settings)
    policy = Policy(settings.mode, settings.allowed_roots)
    registry = NodeRegistry(registry_path)
    checked = 0
    writes = 0
    reads = 0
    for request in requests:
        if request.backend != requests[0].backend:
            raise ValidationError("All requests in one batch must use the same backend")
        if request.writes:
            policy.assert_writes_allowed()
        for write in request.writes:
            node = registry.resolve(write.key, write.identifiers)
            registry.validate_backend(node, request.backend)
            registry.validate_write(node, write.value, write.unit)
            writes += 1
            checked += 1
        for read in request.reads:
            node = registry.resolve(read.key, read.identifiers)
            registry.validate_backend(node, request.backend)
            reads += 1
            checked += 1
        for constraint in request.constraints:
            node = registry.resolve(constraint.key, constraint.identifiers)
            registry.validate_backend(node, request.backend)
            checked += 1
        for balance in request.balances:
            for term in balance.terms:
                node = registry.resolve(term.key, term.identifiers)
                registry.validate_backend(node, request.backend)
                checked += 1
    return {
        "ok": True,
        "backend": requests[0].backend,
        "model_path": str(model_path),
        "registry_path": str(registry_path),
        "registry_sha256": registry.sha256,
        "evaluations": len(requests),
        "writes": writes,
        "reads": reads,
        "semantic_operations": checked,
        "requested_workers": workers,
        "effective_worker_cap": settings.effective_workers,
    }


def run_batch_document(data: dict[str, Any], settings: Settings) -> list[dict[str, Any]]:
    dry_run_document(data, settings)
    requests = _expand_with_settings(data, settings)
    workers = _requested_workers(data, settings)
    model_path, registry_path = _input_paths(requests, settings)
    cache_path = settings.state_dir / "cache.sqlite3"
    with CasePool(
        backend_name=requests[0].backend,
        model_path=model_path,
        registry_path=registry_path,
        workers=workers,
        visible=settings.visible,
        cache_path=cache_path,
        worker_max_points=settings.worker_max_points,
        worker_max_age_s=settings.worker_max_age_s,
        startup_timeout_s=settings.startup_timeout_s,
        cache_failures=settings.cache_failures,
    ) as pool:
        return [result.to_dict() for result in pool.evaluate_many(requests)]


def run_batch_file(path: str | Path, settings: Settings) -> list[dict[str, Any]]:
    policy = Policy(settings.mode, settings.allowed_roots)
    request_path = policy.assert_input_file(
        path,
        max_bytes=settings.max_request_bytes,
        suffixes=(".json",),
    )
    data = read_json_object(request_path, max_bytes=settings.max_request_bytes)
    return run_batch_document(data, settings)
