from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import Settings
from .models import EvaluationRequest, VariableWrite
from .policy import Policy
from .pool import CasePool
from .registry import NodeRegistry


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
    checked = 0
    writes = 0
    reads = 0
    for request in requests:
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
            registry.resolve(constraint.key, constraint.identifiers)
            checked += 1
        for balance in request.balances:
            for term in balance.terms:
                registry.resolve(term.key, term.identifiers)
                checked += 1
    return {
        "ok": True,
        "model_path": str(model_path),
        "registry_path": str(registry_path),
        "registry_sha256": registry.sha256,
        "evaluations": len(requests),
        "writes": writes,
        "reads": reads,
        "semantic_operations": checked,
        "requested_workers": int(data.get("workers", settings.effective_workers)),
        "effective_worker_cap": settings.effective_workers,
    }


def run_batch_document(data: dict[str, Any], settings: Settings) -> list[dict[str, Any]]:
    dry_run_document(data, settings)
    policy = Policy(settings.mode, settings.allowed_roots)
    model_path = policy.assert_path(data["model_path"])
    registry_path = policy.assert_path(data["registry_path"])
    requests = expand_batch_document(data)
    workers = max(
        1, min(int(data.get("workers", settings.effective_workers)), settings.effective_workers)
    )
    cache_path = settings.state_dir / "cache.sqlite3"
    with CasePool(
        backend_name=str(data.get("backend", settings.backend)),
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
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return run_batch_document(data, settings)
