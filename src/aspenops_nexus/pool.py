from __future__ import annotations

import queue
import threading
import time
import uuid
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

from . import RUNTIME_SCHEMA, __version__
from .cache import CacheWaitTimeoutError, ResultCache
from .hashing import canonical_hash, sha256_file
from .models import EvaluationRequest, EvaluationResult
from .registry import NodeRegistry
from .worker import WorkerHandle, evaluate_on_worker, start_worker, stop_worker

_TaskMode = Literal["OWNER", "WAIT", "UNCACHED"]


@dataclass(slots=True)
class _EvaluationTask:
    mode: _TaskMode
    key: str
    request: EvaluationRequest
    indexes: list[int]
    owner_token: str | None
    deadline_monotonic: float


class CasePool:
    """Persistent, process-isolated simulator pool.

    Each Worker owns one staged model, one COM STA and one simulator document. Threads only
    dispatch IPC; COM proxies never cross process or apartment boundaries.
    """

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

    def _requires_recycle(self, handle: WorkerHandle) -> bool:
        return (
            not handle.process.is_alive()
            or handle.evaluations >= self.worker_max_points
            or time.monotonic() - handle.started_monotonic >= self.worker_max_age_s
        )

    def _replace(self, index: int) -> WorkerHandle:
        with self._replace_lock:
            old = self._handles[index]
            stop_worker(old)
            self._generation[old.worker_id] = old.generation + 1
            new = self._new_handle(old.worker_id)
            self._handles[index] = new
            return new

    def cache_key(self, request: EvaluationRequest) -> str:
        identity = {
            "schema": RUNTIME_SCHEMA,
            "runtime_version": __version__,
            "backend": self.backend_name,
            "model_sha256": self.model_sha256,
            "registry_sha256": self.registry.sha256,
            "request": request.physical_identity(),
        }
        return canonical_hash(identity)

    def _cacheable(self, request: EvaluationRequest, result: EvaluationResult) -> bool:
        if not request.reinitialize:
            return False
        return result.ok or self.cache_failures

    @staticmethod
    def _assign_result(
        output: list[EvaluationResult | None],
        result: EvaluationResult,
        indexes: list[int],
        *,
        cached: bool,
        result_lock: threading.Lock,
    ) -> None:
        with result_lock:
            for ordinal, index in enumerate(indexes):
                clone = EvaluationResult.from_dict(result.to_dict())
                clone.cache_hit = cached or ordinal > 0
                output[index] = clone

    def evaluate_many(self, requests: list[EvaluationRequest]) -> list[EvaluationResult]:
        if not requests:
            return []
        if not self._handles:
            self.start()
        output: list[EvaluationResult | None] = [None] * len(requests)
        grouped: dict[str, tuple[EvaluationRequest, list[int]]] = {}
        uncached: list[tuple[str, EvaluationRequest, list[int]]] = []
        for index, request in enumerate(requests):
            key = self.cache_key(request)
            if request.reinitialize:
                grouped.setdefault(key, (request, []))[1].append(index)
            else:
                # Warm-start requests are stateful experiments. Even identical documents must run
                # independently and in order rather than being coalesced as cache-equivalent work.
                uncached.append((key, request, [index]))

        tasks: queue.Queue[_EvaluationTask] = queue.Queue()
        now_monotonic = time.monotonic()
        for key, request, indexes in uncached:
            tasks.put(
                _EvaluationTask(
                    mode="UNCACHED",
                    key=key,
                    request=request,
                    indexes=indexes,
                    owner_token=None,
                    deadline_monotonic=now_monotonic + request.timeout_s,
                )
            )
        for key, (request, indexes) in grouped.items():
            owner_token = f"pool-{uuid.uuid4().hex}"
            lease_seconds = max(1.0, request.timeout_s + 30.0)
            reservation = self.cache.reserve(key, owner_token, lease_seconds)
            if reservation.state == "HIT":
                assert reservation.payload is not None
                result = EvaluationResult.from_dict(reservation.payload)
                result.cache_hit = True
                result.request_hash = key
                for index in indexes:
                    output[index] = EvaluationResult.from_dict(result.to_dict())
                continue
            tasks.put(
                _EvaluationTask(
                    mode=reservation.state,
                    key=key,
                    request=request,
                    indexes=indexes,
                    owner_token=owner_token,
                    deadline_monotonic=now_monotonic + request.timeout_s,
                )
            )

        if tasks.empty():
            return [replace(item) for item in output if item is not None]

        result_lock = threading.Lock()
        errors: list[Exception] = []

        def worker_loop(handle_index: int) -> None:
            handle = self._handles[handle_index]
            while True:
                try:
                    task = tasks.get_nowait()
                except queue.Empty:
                    return
                owner_token = task.owner_token
                try:
                    if task.mode == "WAIT":
                        while True:
                            remaining = task.deadline_monotonic - time.monotonic()
                            if remaining <= 0.0:
                                raise CacheWaitTimeoutError(
                                    f"Total request deadline expired while waiting for {task.key!r}"
                                )
                            payload = self.cache.wait_for_ready(task.key, timeout_s=remaining)
                            if payload is not None:
                                result = EvaluationResult.from_dict(payload)
                                result.request_hash = task.key
                                self._assign_result(
                                    output,
                                    result,
                                    task.indexes,
                                    cached=True,
                                    result_lock=result_lock,
                                )
                                break
                            owner_token = f"pool-{uuid.uuid4().hex}"
                            remaining = task.deadline_monotonic - time.monotonic()
                            if remaining <= 0.0:
                                raise CacheWaitTimeoutError(
                                    f"Total request deadline expired before takeover of {task.key!r}"
                                )
                            reservation = self.cache.reserve(
                                task.key,
                                owner_token,
                                lease_seconds=max(1.0, remaining + 30.0),
                            )
                            if reservation.state == "HIT":
                                assert reservation.payload is not None
                                result = EvaluationResult.from_dict(reservation.payload)
                                result.request_hash = task.key
                                self._assign_result(
                                    output,
                                    result,
                                    task.indexes,
                                    cached=True,
                                    result_lock=result_lock,
                                )
                                break
                            if reservation.state == "WAIT":
                                continue
                            task.mode = "OWNER"
                            task.owner_token = owner_token
                            break
                        if task.mode == "WAIT":
                            continue
                    remaining = task.deadline_monotonic - time.monotonic()
                    if remaining <= 0.0:
                        raise TimeoutError(
                            f"Total request deadline expired before worker execution of {task.key!r}"
                        )
                    if self._requires_recycle(handle):
                        handle = self._replace(handle_index)
                    effective_request = replace(task.request, timeout_s=remaining)
                    result = evaluate_on_worker(handle, effective_request)
                    if not handle.process.is_alive():
                        handle = self._replace(handle_index)
                    result.request_hash = task.key
                    if task.mode == "OWNER":
                        assert owner_token is not None
                        if self._cacheable(task.request, result):
                            self.cache.publish(task.key, owner_token, result.to_dict())
                        else:
                            self.cache.abandon(task.key, owner_token)
                    self._assign_result(
                        output,
                        result,
                        task.indexes,
                        cached=False,
                        result_lock=result_lock,
                    )
                except Exception as exc:
                    if task.mode == "OWNER" and owner_token is not None:
                        self.cache.abandon(task.key, owner_token)
                    with result_lock:
                        errors.append(exc)
                finally:
                    tasks.task_done()

        thread_count = min(len(self._handles), tasks.qsize())
        threads = [
            threading.Thread(target=worker_loop, args=(index,), name=f"aspenops-dispatch-{index}")
            for index in range(thread_count)
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
