from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from aspenops_nexus import RUNTIME_SCHEMA, __version__
from aspenops_nexus.backends.aspen_plus import AspenPlusBackend
from aspenops_nexus.backends.hysys import HysysBackend
from aspenops_nexus.backends.mock import MockBackend
from aspenops_nexus.evaluation import evaluate
from aspenops_nexus.hashing import canonical_hash
from aspenops_nexus.models import EvaluationRequest, EvaluationResult
from aspenops_nexus.pool import CasePool
from aspenops_nexus.registry import NodeRegistry
from aspenops_nexus.worker import WorkerHandle

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src/aspenops_nexus/data/mock-case.json"
REGISTRY = ROOT / "src/aspenops_nexus/data/node-registry.json"
TEMPERATURE = "stream.input.temperature:stream=FEED"


def test_hysys_solver_reset_does_not_restore_a_written_input() -> None:
    cell = SimpleNamespace(CellValue=25.0)
    sheet = SimpleNamespace(Cell=lambda address: cell)
    solver = SimpleNamespace(CanSolve=True)
    backend = HysysBackend()
    backend.case = SimpleNamespace(
        Solver=solver,
        Flowsheet=SimpleNamespace(Operations=SimpleNamespace(Item=lambda name: sheet)),
    )
    node = NodeRegistry(REGISTRY).resolve("stream.input.temperature", {"stream": "FEED"})
    node.locator.update({"spreadsheet": "CONTROLLED_FIXTURE", "cell": "A1"})
    backend.write(node, 95.0)
    backend.reinitialize()
    assert solver.CanSolve is True
    assert backend.read(node) == 95.0


class RetainedInputBackend(MockBackend):
    """Controlled simulator state; resetting calculations leaves inputs intact."""

    def reinitialize(self) -> None:
        self._solve()


def native_runtime(backend_name: str, generation: int, *, version: str = "15") -> dict[str, Any]:
    model_path = Path(f"private-worker-generation-{generation}") / "model-case"
    case = SimpleNamespace(Version=version, Name="model-case", FullName=str(model_path))
    backend: AspenPlusBackend | HysysBackend
    if backend_name == "aspen_plus":
        backend = AspenPlusBackend()
        backend.document = case
    else:
        backend = HysysBackend()
        backend.case = case
        backend.application = SimpleNamespace(Version=version, Name="HYSYS")
    backend.model_path = model_path
    return backend.runtime_identity()


@pytest.mark.parametrize("backend_name", ["aspen_plus", "hysys"])
def test_native_runtime_binds_version_but_not_private_case_location(backend_name: str) -> None:
    first = native_runtime(backend_name, 0)
    replacement = native_runtime(backend_name, 1)
    upgraded = native_runtime(backend_name, 1, version="16")
    assert first["model_path"] != replacement["model_path"]
    assert CasePool._stable_runtime_value(first) == CasePool._stable_runtime_value(replacement)
    assert CasePool._stable_runtime_value(first) != CasePool._stable_runtime_value(upgraded)


@pytest.fixture(params=["aspen_plus", "hysys"])
def native_pool(
    request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Any:
    backend_name = request.param
    registry_payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    for node in registry_payload["nodes"].values():
        node["backend"] = backend_name
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps(registry_payload), encoding="utf-8")
    registry = NodeRegistry(registry_path)
    backends: dict[int, RetainedInputBackend] = {}

    def start(**kwargs: Any) -> WorkerHandle:
        backend = RetainedInputBackend()
        backend.name = backend_name
        backend.open(MODEL)
        handle = WorkerHandle(
            worker_id=kwargs["worker_id"],
            process=SimpleNamespace(is_alive=lambda: True),
            connection=SimpleNamespace(),
            staged_model=MODEL,
            runtime=native_runtime(backend_name, kwargs["generation"]),
            generation=kwargs["generation"],
            model_sha256=kwargs["expected_model_sha256"],
            registry_sha256=kwargs["expected_registry_sha256"],
        )
        backends[id(handle)] = backend
        return handle

    def stop(handle: WorkerHandle) -> None:
        backend = backends.pop(id(handle), None)
        if backend is not None:
            backend.close()

    def execute(handle: WorkerHandle, evaluation: EvaluationRequest) -> EvaluationResult:
        result = evaluate(backends[id(handle)], registry, evaluation, worker_id=handle.worker_id)
        handle.evaluations += 1
        return result

    monkeypatch.setattr("aspenops_nexus.pool.start_worker", start)
    monkeypatch.setattr("aspenops_nexus.pool.stop_worker", stop)
    monkeypatch.setattr("aspenops_nexus.pool.abort_worker", stop)
    monkeypatch.setattr("aspenops_nexus.pool.evaluate_on_worker", execute)
    with CasePool(
        backend_name=backend_name,
        model_path=MODEL,
        registry_path=registry_path,
        workers=1,
        visible=False,
        cache_path=tmp_path / "cache.sqlite3",
    ) as pool:
        yield pool


def evaluation_request(
    pool: CasePool, temperature: float | None = None, *, warm: bool = False
) -> EvaluationRequest:
    return EvaluationRequest.from_dict(
        {
            "model_path": str(MODEL),
            "registry_path": str(pool.registry_path),
            "backend": pool.backend_name,
            "reset_mode": "warm_start" if warm else "reinitialize",
            "writes": (
                []
                if temperature is None
                else [
                    {
                        "key": "stream.input.temperature",
                        "identifiers": {"stream": "FEED"},
                        "value": temperature,
                        "unit": "C",
                    }
                ]
            ),
            "reads": [
                {
                    "key": "stream.input.temperature",
                    "identifiers": {"stream": "FEED"},
                    "unit": "C",
                }
            ],
        }
    )


def test_cold_point_restores_pristine_inputs_after_a_partial_predecessor(
    native_pool: CasePool,
) -> None:
    baseline = json.loads(MODEL.read_text(encoding="utf-8"))["inputs"]["feed_temperature_C"]
    changed, independent = native_pool.evaluate_many(
        [evaluation_request(native_pool, 95.0), evaluation_request(native_pool)]
    )
    assert changed.ok and independent.ok
    assert changed.values[TEMPERATURE] == 95.0
    assert independent.values[TEMPERATURE] == baseline
    assert independent.diagnostics["worker"]["recycle_reason"] == "model_baseline"
    assert independent.diagnostics["execution_identity"]["worker_generation"] == 1


def test_explicit_warm_point_keeps_prior_inputs_and_generation(native_pool: CasePool) -> None:
    cold = native_pool.evaluate_many([evaluation_request(native_pool, 95.0)])[0]
    warm = native_pool.evaluate_many([evaluation_request(native_pool, warm=True)])[0]
    assert cold.ok and warm.ok
    assert warm.values[TEMPERATURE] == 95.0
    assert native_pool._handles[0].generation == 0
    assert "worker" not in warm.diagnostics


def test_cold_request_cannot_replay_old_solver_only_reset_cache(native_pool: CasePool) -> None:
    evaluation = evaluation_request(native_pool)
    legacy_key = canonical_hash(
        {
            "schema": RUNTIME_SCHEMA,
            "runtime_version": __version__,
            "backend": native_pool.backend_name,
            "runtime_identity": native_pool._runtime_cache_identity(),
            "model_sha256": native_pool.model_sha256,
            "registry_sha256": native_pool.registry_sha256,
            "request": evaluation.physical_identity(),
        }
    )
    stale_result = EvaluationResult(
        ok=True,
        communication_ok=True,
        engine_ok=True,
        converged=True,
        feasible=True,
        values={TEMPERATURE: 95.0},
        units={TEMPERATURE: "C"},
        violations=[],
        diagnostics={},
        elapsed_s=0.0,
    )
    native_pool.cache.put(legacy_key, stale_result.to_dict())
    result = native_pool.evaluate_many([evaluation])[0]
    baseline = json.loads(MODEL.read_text(encoding="utf-8"))["inputs"]["feed_temperature_C"]
    assert result.ok
    assert result.cache_source == "computed"
    assert result.values[TEMPERATURE] == baseline
