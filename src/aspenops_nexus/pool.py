from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from dataclasses import replace as _dataclass_replace
from pathlib import Path
from typing import Any, cast

from . import RUNTIME_SCHEMA, __version__
from .cache import ResultCache
from .hashing import canonical_hash, sha256_file
from .models import EvaluationRequest, EvaluationResult
from .registry import NodeRegistry
from .worker import (
    WorkerHandle,
    abort_worker,
    evaluate_on_worker,
    start_worker,
    stop_worker,
)

# Public compatibility hook used by operation-count and regression guards.
replace = _dataclass_replace


@dataclass(slots=True)
class _InflightEvaluation:
    event: threading.Event
    result: EvaluationResult | None = None
    error: BaseException | None = None


class CasePool:
    """Persistent, process-isolated simulator pool bound to immutable artifact digests."""

    def __init__(
        self,
        *,
        backend_name: str,
        model_path: Path,
        registry_path: Path,
        workers: int,
        visible: bool,
        cache_path: Path,
        worker_max_points: int = 200,
        worker_max_age_s: float = 14_400.0,
        startup_timeout_s: float = 90.0,
        cache_failures: bool = False,
    ) -> None:
        self.backend_name = backend_name
        self.model_path = model_path.resolve()
        self.registry_path = registry_path.resolve()
        self.workers = max(1, workers)
        self.visible = visible
        self.cache = ResultCache(cache_path)
        self.worker_max_points = max(1, worker_max_points)
        self.worker_max_age_s = max(1.0, worker_max_age_s)
        self.startup_timeout_s = max(0.001, startup_timeout_s)
        self.cache_failures = cache_failures
        self.registry = NodeRegistry(self.registry_path)
        # These are approval digests. Every private Worker copy must match them before COM opens.
        self.model_sha256 = sha256_file(self.model_path)
        self.registry_sha256 = self.registry.sha256
        self._handles: list[WorkerHandle] = []
        self._generation: dict[int, int] = {}
        self._replace_lock = threading.RLock()
        self._operation_lock = threading.Lock()
        self._singleflight_lock = threading.Lock()
        self._inflight: dict[str, _InflightEvaluation] = {}

    def __enter__(self) -> CasePool:
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        del exc_type, exc, traceback
        self.close()

    def _registry_digest(self) -> str:
        digest = getattr(self, "registry_sha256", None)
        if isinstance(digest, str) and digest:
            return digest
        fallback = getattr(getattr(self, "registry", None), "sha256", None)
        if not isinstance(fallback, str) or not fallback:
            raise RuntimeError("CasePool registry identity is unavailable")
        return fallback

    def _assert_handle_identity(self, handle: WorkerHandle) -> None:
        model_digest = getattr(handle, "model_sha256", self.model_sha256)
        registry_digest = getattr(handle, "registry_sha256", self._registry_digest())
        if isinstance(handle, WorkerHandle) and (not model_digest or not registry_digest):
            raise RuntimeError("Worker omitted required execution artifact identity")
        if model_digest != self.model_sha256:
            raise RuntimeError("Worker model snapshot digest differs from CasePool identity")
        if registry_digest != self._registry_digest():
            raise RuntimeError("Worker registry snapshot digest differs from CasePool identity")

    def _bind_execution_identity(
        self,
        result: EvaluationResult,
        handle: WorkerHandle,
    ) -> None:
        runtime = getattr(handle, "runtime", {})
        backend = runtime.get("backend") if isinstance(runtime, dict) else None
        result.diagnostics["execution_identity"] = {
            "model_sha256": self.model_sha256,
            "registry_sha256": self._registry_digest(),
            "backend": backend or self.backend_name,
            "worker_generation": getattr(handle, "generation", 0),
        }

    def start(self) -> None:
        with self._replace_lock:
            if self._handles:
                return
            started: list[WorkerHandle] = []
            try:
                for worker_id in range(self.workers):
                    self._generation[worker_id] = 0
                    handle = self._new_handle(worker_id)
                    self._assert_handle_identity(handle)
                    started.append(handle)
                identities: list[Any] = []
                for handle in started:
                    runtime = getattr(handle, "runtime", None)
                    if isinstance(handle, WorkerHandle) and not isinstance(runtime, dict):
                        raise RuntimeError("Worker runtime identity must be an object")
                    if isinstance(runtime, dict):
                        identities.append(self._stable_runtime_value(runtime))
                if identities and any(identity != identities[0] for identity in identities[1:]):
                    raise RuntimeError(
                        "CasePool workers expose heterogeneous simulator runtime identities"
                    )
                self._handles = started
            except Exception:
                for handle in started:
                    if isinstance(handle, WorkerHandle):
                        stop_worker(handle)
                raise

    def close(self) -> None:
        with self._replace_lock:
            handles = list(self._handles)
            self._handles.clear()
        for handle in handles:
            stop_worker(handle)
        self.cache.close()

    def _new_handle(self, worker_id: int) -> WorkerHandle:
        return start_worker(
            worker_id=worker_id,
            backend_name=self.backend_name,
            model_path=self.model_path,
            registry_path=self.registry_path,
            visible=self.visible,
            startup_timeout_s=self.startup_timeout_s,
            generation=self._generation.get(worker_id, 0),
            expected_model_sha256=self.model_sha256,
            expected_registry_sha256=self._registry_digest(),
        )

    def _recycle_reason(self, handle: WorkerHandle) -> str | None:
        if not handle.process.is_alive():
            return "crash"
        if handle.evaluations >= self.worker_max_points:
            return "point_budget"
        if time.monotonic() - handle.started_monotonic >= self.worker_max_age_s:
            return "age"
        return None

    @staticmethod
    def _result_recycle_reason(handle: WorkerHandle, result: EvaluationResult) -> str | None:
        if bool(result.diagnostics.get("worker_tainted")):
            return "tainted"
        violations = set(result.violations)
        if "worker_timeout" in violations:
            return "timeout"
        if violations.intersection(
            {"worker_protocol_error", "worker_send_failed", "worker_receive_failed"}
        ):
            return "protocol_error"
        if not handle.process.is_alive():
            return "crash"
        return None

    @staticmethod
    def _annotate_recycle(
        result: EvaluationResult,
        *,
        reason: str,
        old_generation: int,
        new_generation: int,
    ) -> None:
        worker_diagnostics = result.diagnostics.get("worker")
        if not isinstance(worker_diagnostics, dict):
            worker_diagnostics = {}
            result.diagnostics["worker"] = worker_diagnostics
        worker_diagnostics.update(
            {
                "worker_recycled": True,
                "recycle_reason": reason,
                "old_generation": old_generation,
                "new_generation": new_generation,
            }
        )

    def _replace(
        self,
        index: int,
        *,
        expected: WorkerHandle | None = None,
        force: bool = False,
    ) -> WorkerHandle:
        with self._replace_lock:
            current = self._handles[index]
            if expected is not None and current is not expected:
                return current
            if force:
                abort_worker(current)
            else:
                stop_worker(current)
            self._generation[current.worker_id] = current.generation + 1
            new = self._new_handle(current.worker_id)
            try:
                self._assert_handle_identity(new)
                expected_runtime = self._runtime_cache_identity()
                observed_runtime = self._stable_runtime_value(new.runtime)
                if observed_runtime != expected_runtime:
                    raise RuntimeError(
                        "Replacement worker runtime identity differs from the CasePool identity"
                    )
            except Exception:
                abort_worker(new)
                raise
            self._handles[index] = new
            return new

    def force_recycle_all(self, reason: str = "cancel_deadline") -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        with self._replace_lock:
            for index in range(len(self._handles)):
                expected = self._handles[index]
                old_generation = expected.generation
                replacement = self._replace(index, expected=expected, force=True)
                if replacement is expected:
                    continue
                events.append(
                    {
                        "worker_id": expected.worker_id,
                        "reason": reason,
                        "old_generation": old_generation,
                        "new_generation": replacement.generation,
                    }
                )
        return events

    @staticmethod
    def _stable_runtime_value(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                str(key): CasePool._stable_runtime_value(item)
                for key, item in value.items()
                if key
                not in {
                    "model_path",
                    "staged_model_path",
                    "staged_registry_path",
                    "worker_pid",
                    "pid",
                    "error",
                }
            }
        if isinstance(value, list):
            return [CasePool._stable_runtime_value(item) for item in value]
        if isinstance(value, tuple):
            return tuple(CasePool._stable_runtime_value(item) for item in value)
        return value

    def _runtime_cache_identity(self) -> dict[str, Any]:
        if not self._handles:
            return {"backend": self.backend_name}
        identities = [self._stable_runtime_value(handle.runtime) for handle in self._handles]
        stable = identities[0]
        if not isinstance(stable, dict):
            raise RuntimeError("Worker runtime identity must be an object")
        if any(identity != stable for identity in identities[1:]):
            raise RuntimeError("CasePool workers expose heterogeneous runtime identities")
        return stable

    def cache_key(self, request: EvaluationRequest) -> str:
        identity = {
            "schema": RUNTIME_SCHEMA,
            "runtime_version": __version__,
            "backend": self.backend_name,
            "runtime_identity": self._runtime_cache_identity(),
            "model_sha256": self.model_sha256,
            "registry_sha256": self._registry_digest(),
            "request": request.physical_identity(),
        }
        return canonical_hash(identity)

    def _key_requests(
        self,
        requests: list[EvaluationRequest],
    ) -> list[tuple[str, EvaluationRequest]]:
        """Reuse cache-key work when the same immutable request object repeats in a batch."""

        by_identity: dict[int, tuple[EvaluationRequest, str]] = {}
        keyed: list[tuple[str, EvaluationRequest]] = []
        for request in requests:
            identity = id(request)
            existing = by_identity.get(identity)
            if existing is not None and existing[0] is request:
                key = existing[1]
            else:
                key = self.cache_key(request)
                by_identity[identity] = (request, key)
            keyed.append((key, request))
        return keyed

    def _cacheable(self, request: EvaluationRequest, result: EvaluationResult) -> bool:
        if not request.reinitialize:
            return False
        execution_identity = result.diagnostics.get("execution_identity")
        if execution_identity is not None:
            if not isinstance(execution_identity, dict):
                return False
            if execution_identity.get("model_sha256") != self.model_sha256:
                return False
            if execution_identity.get("registry_sha256") != self._registry_digest():
                return False
        if result.ok:
            return True
        if not self.cache_failures:
            return False
        return (
            result.communication_ok
            and result.engine_ok
            and not bool(result.diagnostics.get("worker_tainted"))
        )

    @staticmethod
    def _cancelled_result(request_hash: str) -> EvaluationResult:
        return EvaluationResult(
            ok=False,
            communication_ok=False,
            engine_ok=False,
            converged=False,
            feasible=False,
            values={},
            units={},
            violations=["batch_cancelled"],
            diagnostics={"cancelled_before_execution": True},
            elapsed_s=0.0,
            cache_source="computed",
            cache_hit=False,
            request_hash=request_hash,
        )

    def _wait_for_flight(
        self,
        flight: _InflightEvaluation,
        request_hash: str,
        cancel_check: Callable[[], bool] | None,
    ) -> EvaluationResult:
        while not flight.event.wait(0.05):
            if cancel_check is not None and cancel_check():
                return self._cancelled_result(request_hash)
        if flight.error is not None:
            raise RuntimeError("Singleflight leader failed") from flight.error
        if flight.result is None:
            raise RuntimeError("Singleflight completed without a result")
        result = deepcopy(flight.result)
        result.cache_source = "inflight_singleflight"
        result.cache_hit = True
        return result

    def _evaluate_singleflight(
        self,
        request: EvaluationRequest,
        cancel_check: Callable[[], bool] | None,
    ) -> EvaluationResult:
        if not self._handles:
            self.start()
        if not request.reinitialize:
            with self._operation_lock:
                return self._evaluate_many_locked([request], cancel_check=cancel_check)[0]

        request_hash = self.cache_key(request)
        cached = self.cache.get(request_hash)
        if cached is not None:
            result = EvaluationResult.from_dict(cached)
            result.cache_source = "persistent_cache"
            result.cache_hit = True
            result.request_hash = request_hash
            return result

        with self._singleflight_lock:
            flight = self._inflight.get(request_hash)
            leader = flight is None
            if flight is None:
                flight = _InflightEvaluation(threading.Event())
                self._inflight[request_hash] = flight
        if not leader:
            return self._wait_for_flight(flight, request_hash, cancel_check)

        try:
            with self._operation_lock:
                result = self._evaluate_many_locked([request], cancel_check=cancel_check)[0]
            flight.result = deepcopy(result)
            return result
        except BaseException as exc:
            flight.error = exc
            raise
        finally:
            with self._singleflight_lock:
                if self._inflight.get(request_hash) is flight:
                    self._inflight.pop(request_hash, None)
            flight.event.set()

    def evaluate_many(
        self,
        requests: list[EvaluationRequest],
        *,
        cancel_check: Callable[[], bool] | None = None,
    ) -> list[EvaluationResult]:
        if not requests:
            return []
        if self.workers != 1 and any(not request.reinitialize for request in requests):
            raise ValueError("warm_start evaluation requires a single-worker CasePool")
        warm_start_requests = [request for request in requests if not request.reinitialize]
        if warm_start_requests:
            if len(warm_start_requests) != len(requests):
                raise ValueError("Cannot mix reinitialize and warm_start requests in one pool call")
            if self.workers != 1:
                raise ValueError("warm_start pool calls require exactly one worker")
            trajectories = [
                (
                    str(request.metadata["warm_start_session"]),
                    int(request.metadata["warm_start_step"]),
                )
                for request in warm_start_requests
            ]
            if len(set(trajectories)) != len(trajectories):
                raise ValueError("warm_start trajectory steps must be unique")
            with self._operation_lock:
                return self._evaluate_many_locked(requests, cancel_check=cancel_check)
        if len(requests) == 1:
            return [self._evaluate_singleflight(requests[0], cancel_check)]
        with self._operation_lock:
            return self._evaluate_many_locked(requests, cancel_check=cancel_check)

    def _evaluate_many_locked(
        self,
        requests: list[EvaluationRequest],
        *,
        cancel_check: Callable[[], bool] | None,
    ) -> list[EvaluationResult]:
        if not self._handles:
            self.start()
        keyed_requests = self._key_requests(requests)
        cached_payloads = self.cache.get_many(
            [key for key, request in keyed_requests if request.reinitialize]
        )
        output: list[EvaluationResult | None] = [None] * len(requests)
        unique: dict[str, tuple[EvaluationRequest, list[int]]] = {}
        cached_results: dict[str, EvaluationResult] = {}
        for index, (key, request) in enumerate(keyed_requests):
            cached = cached_payloads.get(key) if request.reinitialize else None
            if cached is not None:
                template = cached_results.get(key)
                if template is None:
                    result = EvaluationResult.from_dict(cached)
                    result.cache_source = "persistent_cache"
                    result.cache_hit = True
                    result.request_hash = key
                    cached_results[key] = result
                else:
                    result = deepcopy(template)
                output[index] = result
                continue
            unique.setdefault(key, (request, []))[1].append(index)

        if not unique:
            if any(item is None for item in output):
                raise RuntimeError("Internal cache error: one or more results were not assigned")
            return cast(list[EvaluationResult], output)

        tasks: queue.Queue[tuple[str, EvaluationRequest, list[int]]] = queue.Queue()
        for key, (request, indexes) in unique.items():
            tasks.put((key, request, indexes))
        result_lock = threading.Lock()
        errors: list[BaseException] = []
        cache_payloads: dict[str, dict[str, Any]] = {}

        def worker_loop(handle_index: int) -> None:
            nonlocal output
            handle = self._handles[handle_index]
            while True:
                try:
                    key, request, indexes = tasks.get_nowait()
                except queue.Empty:
                    return
                try:
                    if cancel_check is not None and cancel_check():
                        cancelled = self._cancelled_result(key)
                        with result_lock:
                            for index in indexes:
                                output[index] = deepcopy(cancelled)
                        continue

                    recycle_event: tuple[str, int, int] | None = None
                    pre_reason = self._recycle_reason(handle)
                    if pre_reason is not None:
                        old_generation = handle.generation
                        handle = self._replace(handle_index, expected=handle)
                        recycle_event = (pre_reason, old_generation, handle.generation)

                    result = evaluate_on_worker(handle, request)
                    self._bind_execution_identity(result, handle)
                    result.cache_source = "computed"
                    result.cache_hit = False
                    post_reason = self._result_recycle_reason(handle, result)
                    if post_reason is not None:
                        old_generation = handle.generation
                        handle = self._replace(handle_index, expected=handle)
                        recycle_event = (post_reason, old_generation, handle.generation)
                    if recycle_event is not None:
                        reason, old_generation, new_generation = recycle_event
                        self._annotate_recycle(
                            result,
                            reason=reason,
                            old_generation=old_generation,
                            new_generation=new_generation,
                        )

                    result.request_hash = key
                    cacheable = self._cacheable(request, result)
                    payload = result.to_dict() if cacheable else None
                    with result_lock:
                        if cacheable:
                            assert payload is not None
                            cache_payloads[key] = payload
                        for ordinal, index in enumerate(indexes):
                            clone = result if ordinal == 0 else deepcopy(result)
                            if ordinal > 0:
                                clone.cache_source = "same_batch_dedup"
                                clone.cache_hit = True
                            output[index] = clone
                except BaseException as exc:
                    with result_lock:
                        errors.append(exc)

        threads = [
            threading.Thread(target=worker_loop, args=(index,), name=f"aspenops-dispatch-{index}")
            for index in range(min(len(self._handles), len(unique)))
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        if cache_payloads:
            self.cache.put_many(cache_payloads)
        if errors:
            raise RuntimeError(f"CasePool dispatch failed: {errors[0]}") from errors[0]
        if any(item is None for item in output):
            raise RuntimeError("Internal scheduler error: one or more results were not assigned")
        return cast(list[EvaluationResult], output)
