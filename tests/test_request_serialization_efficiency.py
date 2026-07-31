from __future__ import annotations

import json
from dataclasses import asdict
from types import SimpleNamespace
from typing import Any

from aspenops_nexus import RUNTIME_SCHEMA, __version__
from aspenops_nexus.hashing import canonical_hash
from aspenops_nexus.models import EvaluationRequest
from aspenops_nexus.pool import CasePool


def _request() -> EvaluationRequest:
    return EvaluationRequest.from_dict(
        {
            "model_path": "model.bkp",
            "registry_path": "registry.json",
            "backend": "mock",
            "writes": [
                {
                    "key": "stream.input.temperature",
                    "identifiers": {"stream": "FEED", "stage": 1},
                    "value": 80.0,
                    "unit": "C",
                }
            ],
            "reads": [
                {
                    "key": "stream.output.purity",
                    "identifiers": {"stream": "PRODUCT"},
                    "unit": "fraction",
                    "required": True,
                }
            ],
            "constraints": [
                {
                    "key": "stream.output.purity",
                    "identifiers": {"stream": "PRODUCT"},
                    "operator": ">=",
                    "value": 0.95,
                    "unit": "fraction",
                    "name": "purity",
                    "tolerance": 1e-6,
                }
            ],
            "balances": [
                {
                    "name": "mass",
                    "terms": [
                        {
                            "key": "stream.input.flow",
                            "identifiers": {"stream": "FEED"},
                            "coefficient": 1.0,
                            "unit": "kg/s",
                        },
                        {
                            "key": "stream.output.flow",
                            "identifiers": {"stream": "PRODUCT"},
                            "coefficient": -1.0,
                            "unit": "kg/s",
                        },
                    ],
                    "expected": 0.0,
                    "abs_tol": 1e-6,
                    "rel_tol": 1e-6,
                    "floor": 1e-12,
                }
            ],
            "reset_mode": "reinitialize",
            "timeout_s": 30.0,
            "metadata": {"source": "test"},
        }
    )


def _legacy_physical_identity(request: EvaluationRequest) -> dict[str, Any]:
    return {
        "backend": request.backend,
        "reset_mode": request.reset_mode,
        "writes": [asdict(item) for item in request.writes],
        "reads": [asdict(item) for item in request.reads],
        "constraints": [asdict(item) for item in request.constraints],
        "balances": [asdict(item) for item in request.balances],
    }


def _legacy_document(request: EvaluationRequest) -> dict[str, Any]:
    return {
        "model_path": request.model_path,
        "registry_path": request.registry_path,
        "backend": request.backend,
        "writes": [asdict(item) for item in request.writes],
        "reads": [asdict(item) for item in request.reads],
        "constraints": [asdict(item) for item in request.constraints],
        "balances": [asdict(item) for item in request.balances],
        "reset_mode": request.reset_mode,
        "timeout_s": request.timeout_s,
        "metadata": dict(request.metadata),
    }


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def test_request_document_is_directly_round_trippable_and_isolated() -> None:
    request = _request()
    document = request.to_dict()

    balances = document["balances"]
    assert isinstance(balances, list)
    assert isinstance(balances[0]["terms"], list)
    assert EvaluationRequest.from_dict(document) == request
    assert _canonical_json(document) == _canonical_json(_legacy_document(request))

    document["writes"][0]["identifiers"]["stream"] = "MUTATED"
    document["balances"][0]["terms"][0]["identifiers"]["stream"] = "MUTATED"
    assert request.writes[0].identifiers["stream"] == "FEED"
    assert request.balances[0].terms[0].identifiers["stream"] == "FEED"


def test_physical_identity_preserves_exact_python_shape_and_isolation() -> None:
    request = _request()
    identity = request.physical_identity()
    legacy = _legacy_physical_identity(request)

    assert identity == legacy
    assert isinstance(identity["balances"][0]["terms"], tuple)
    identity["reads"][0]["identifiers"]["stream"] = "MUTATED"
    identity["balances"][0]["terms"][0]["identifiers"]["stream"] = "MUTATED"
    assert request.reads[0].identifiers["stream"] == "PRODUCT"
    assert request.balances[0].terms[0].identifiers["stream"] == "FEED"


def test_cache_key_bytes_are_unchanged() -> None:
    request = _request()
    pool = object.__new__(CasePool)
    pool.backend_name = "mock"
    pool.model_sha256 = "m" * 64
    pool.registry = SimpleNamespace(sha256="r" * 64)
    pool._handles = []

    legacy_cache_identity = {
        "schema": RUNTIME_SCHEMA,
        "runtime_version": __version__,
        "backend": "mock",
        "runtime_identity": {"backend": "mock"},
        "model_sha256": "m" * 64,
        "registry_sha256": "r" * 64,
        "request": _legacy_physical_identity(request),
    }
    assert pool.cache_key(request) == canonical_hash(legacy_cache_identity)
