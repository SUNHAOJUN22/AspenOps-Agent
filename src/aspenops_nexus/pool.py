from __future__ import annotations

import queue
import threading
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from . import RUNTIME_SCHEMA, __version__
from .cache import ResultCache
from .hashing import canonical_hash, sha256_file
from .models import EvaluationRequest, EvaluationResult
from .registry import NodeRegistry
from .worker import WorkerHandle, evaluate_on_worker, start_worker, stop_worker


class CasePool:
    """Persistent, process-isolated simulator pool."""

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
        self.model_sha256 = sha256_file(self.model_path)
        self._handles: list[WorkerHandle] = []
        self._generation: dict[int, int] = {}
        self._replace_lock = threading.Lock()

    def __enter__(self) -> CasePool:
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        del exc_type, exc, traceback
        self.close()

    def start(self) -> None:
        if self._handles:
            return
        started: list[WorkerHandle] = []
        try:
            for worker_id in range(self.workers):
                self._generation[worker_id] = 0
                handle = self._new_handle(worker_id)
                started.append(handle)
            self._handles = started
        except Exception:
            for handle in started:
                stop_worker(handle)
            raise

    def close(self) -> None:
        for handle in self._handles:
            stop_worker(handle)
        self._handles.clear()

    def _new_handle(self, worker_id: int) -> WorkerHandle:
        return start_worker(
            worker_id=worker_id,
            backend_name=self.backend_name,
            model_path=self.model_path,
            registry_path=self.registry_path,
            visible=self.visible,
            startup_timeout_s=self.startup_timeout_s,
            generation=self._generation.get(worker_id, 0),
        )

    def _recycle_reason(self, handle: WorkerHandle) -> str | None:
        if not handle.process.is_alive():
            return "crash"
        if handle.evaluations >= self.worker_max_points:
            return "point_budget"
        if time.monotonic() - handle.started_monotonic >= self.worker_max_age_s:
            return "age"
        return None

    def _requires_recycle(self, handle: WorkerHandle) -> bool:
        return self._recycle_reason(handle) is not None

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

    def _replace(self, index: int) -> WorkerHandle:
        with self._replace_lock:
            old = self._handles[index]
            stop_worker(old)
            self._generation[old.worker_id] = old.generation + 1
            new = self._new_handle(old.worker_id)
            self._handles[index] = new
            return new

    def _runtime_cache_identity(self) -> dict[str, Any]:
        if not self._handles:
            return {"backend": self.backend_name}
        identity = dict(self._handles[0].runtime)
        identity.pop("model_path", None)
        return identity

    def cache_key(self, request: EvaluationRequest) -> str:
        identity = {
            "schema": RUNTIME_SCHEMA,
            "runtime_version": __version__,
            "backend": self.backend_name,
            "runtime_identity": self._runtime_cache_identity(),
            "model_sha256": self.model_sha256,
            "registry_sha256": self.registry.sha256,
            "request": request.physical_identity(),
        }
        return canonical_hash(identity)

    def _cacheable(self, request: EvaluationRequest, result: EvaluationResult) -> bool:
        if not request.reinitialize:
            return False
        return result.ok or self.cache_failures

    def evaluate_many(self, requests: list[EvaluationRequest]) -> list[EvaluationResult]:
        if not requests:
            return []
        if not self._handles:
            self.start()
        output: list[EvaluationResult | None] = [None] * len(requests)
        unique: dict[str, tuple[EvaluationRequest, list[int]]] = {}
        for index, request in enumerate(requests):
            key = self.cache_key(request)
            if request.reinitialize:
                cached = self.cache.get(key)
                if cached is not None:
                    result = EvaluationResult.from_dict(cached)
                    result.cache_source = "persistent_cache"
                    result.cache_hit = True
                    result.request_hash = key
                    output[index] = result
                    continue
            unique.setdefault(key, (request, []))[1].append(index)

        tasks: queue.Queue[tuple[str, EvaluationRequest, list[int]]] = queue.Queue()
        for key, (request, indexes) in unique.items():
            tasks.put((key, request, indexes))
        result_lock = threading.Lock()
        errors: list[BaseException] = []

        def worker_loop(handle_index: int) -> None:
            nonlocal output
            handle = self._handles[handle_index]
            while True:
                try:
                    key, request, indexes = tasks.get_nowait()
                except queue.Empty:
                    return
                try:
                    recycle_event: tuple[str, int, int] | None = None
                    pre_reason = self._recycle_reason(handle)
                    if pre_reason is not None:
                        old_generation = handle.generation
                        handle = self._replace(handle_index)
                        recycle_event = (pre_reason, old_generation, handle.generation)

                    result = evaluate_on_worker(handle, request)
                    result.cache_source = "computed"
                    result.cache_hit = False
                    post_reason = self._result_recycle_reason(handle, result)
                    if post_reason is not None:
                        old_generation = handle.generation
                        handle = self._replace(handle_index)
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
                    if self._cacheable(request, result):
                        self.cache.put(key, result.to_dict())
                    with result_lock:
                        for ordinal, index in enumerate(indexes):
                            clone = EvaluationResult.from_dict(result.to_dict())
                            if ordinal > 0:
                                clone.cache_source = "same_batch_dedup"
                                clone.cache_hit = True
                            output[index] = clone
                except BaseException as exc:
                    with result_lock:
                        errors.append(exc)
                finally:
                    tasks.task_done()

        threads = [
            threading.Thread(target=worker_loop, args=(index,), name=f"aspenops-dispatch-{index}")
            for index in range(min(len(self._handles), max(1, len(unique))))
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        if errors:
            raise RuntimeError(f"CasePool dispatch failed: {errors[0]}") from errors[0]
        if any(item is None for item in output):
            raise RuntimeError("Internal scheduler error: one or more results were not assigned")
        return [replace(item) for item in output if item is not None]
