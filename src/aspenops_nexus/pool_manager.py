from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .hashing import canonical_hash, sha256_file
from .pool import CasePool

LookupKey = tuple[str, str, str, str]


@dataclass(frozen=True, slots=True)
class CaseKey:
    backend: str
    runtime_identity_hash: str
    model_digest: str
    registry_digest: str
    compatibility_profile: str


@dataclass(slots=True)
class PoolRecord:
    key: CaseKey
    pool: CasePool
    workers: int
    lookup_key: LookupKey
    last_used_monotonic: float = field(default_factory=time.monotonic)
    leases: int = 0
    execution_lock: threading.Lock = field(default_factory=threading.Lock)


@dataclass(slots=True)
class _PoolCreation:
    workers: int
    event: threading.Event = field(default_factory=threading.Event)
    error: BaseException | None = None


class PoolManager:
    """Own long-lived CasePools and enforce a global resident license budget."""

    def __init__(
        self,
        *,
        cache_path: Path,
        license_slots: int,
        max_resident_cases: int = 2,
        idle_timeout_s: float = 1800.0,
        worker_max_points: int = 200,
        worker_max_age_s: float = 14_400.0,
        startup_timeout_s: float = 90.0,
        cache_failures: bool = False,
    ) -> None:
        self.cache_path = cache_path.resolve()
        self.license_slots = max(1, license_slots)
        self.max_resident_cases = max(1, max_resident_cases)
        self.idle_timeout_s = max(1.0, idle_timeout_s)
        self.worker_max_points = max(1, worker_max_points)
        self.worker_max_age_s = max(1.0, worker_max_age_s)
        self.startup_timeout_s = max(0.001, startup_timeout_s)
        self.cache_failures = cache_failures
        self._records: dict[LookupKey, PoolRecord] = {}
        self._creating: dict[LookupKey, _PoolCreation] = {}
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._closed = False
        self._created_pools = 0
        self._reused_leases = 0
        self._evicted_pools = 0
        self._creating_workers = 0
        self._creation_waiters = 0
        self._creation_failures = 0
        self._startup_parallelism_current = 0
        self._startup_parallelism_peak = 0

    @staticmethod
    def _compatibility_profile(*, workers: int, visible: bool) -> str:
        return canonical_hash({"workers": workers, "visible": visible})

    @staticmethod
    def _runtime_identity_hash(pool: CasePool) -> str:
        return canonical_hash(pool._runtime_cache_identity())

    def _resident_workers(self) -> int:
        return sum(record.workers for record in self._records.values())

    def _close_record(self, lookup_key: LookupKey) -> None:
        record = self._records.pop(lookup_key)
        record.pool.close()
        self._evicted_pools += 1

    def _evict_expired(self, now: float) -> None:
        expired = [
            lookup_key
            for lookup_key, record in self._records.items()
            if record.leases == 0 and now - record.last_used_monotonic >= self.idle_timeout_s
        ]
        for lookup_key in expired:
            self._close_record(lookup_key)

    def _ensure_creation_capacity(self, requested_workers: int, now: float) -> None:
        self._evict_expired(now)
        while (
            len(self._records) + len(self._creating) >= self.max_resident_cases
            or self._resident_workers() + self._creating_workers + requested_workers
            > self.license_slots
        ):
            candidates = [record for record in self._records.values() if record.leases == 0]
            if not candidates:
                raise RuntimeError(
                    "No resident CasePool can be evicted within the configured license budget"
                )
            oldest = min(candidates, key=lambda record: record.last_used_monotonic)
            self._close_record(oldest.lookup_key)

    def _new_record(
        self,
        *,
        lookup_key: LookupKey,
        backend_name: str,
        model_path: Path,
        registry_path: Path,
        workers: int,
        visible: bool,
        model_digest: str,
        registry_digest: str,
        compatibility_profile: str,
    ) -> PoolRecord:
        pool = CasePool(
            backend_name=backend_name,
            model_path=model_path,
            registry_path=registry_path,
            workers=workers,
            visible=visible,
            cache_path=self.cache_path,
            worker_max_points=self.worker_max_points,
            worker_max_age_s=self.worker_max_age_s,
            startup_timeout_s=self.startup_timeout_s,
            cache_failures=self.cache_failures,
        )
        try:
            pool.start()
            if pool.model_sha256 != model_digest:
                raise RuntimeError(
                    "Model changed between PoolManager identity capture and Worker snapshot creation"
                )
            if pool.registry_sha256 != registry_digest:
                raise RuntimeError(
                    "Registry changed between PoolManager identity capture and Worker snapshot creation"
                )
            key = CaseKey(
                backend=backend_name,
                runtime_identity_hash=self._runtime_identity_hash(pool),
                model_digest=pool.model_sha256,
                registry_digest=pool.registry_sha256,
                compatibility_profile=compatibility_profile,
            )
            return PoolRecord(
                key=key,
                pool=pool,
                workers=workers,
                lookup_key=lookup_key,
            )
        except BaseException:
            pool.close()
            raise

    def _reserve_creation(self, lookup_key: LookupKey, workers: int) -> _PoolCreation:
        self._ensure_creation_capacity(workers, time.monotonic())
        creation = _PoolCreation(workers=workers)
        self._creating[lookup_key] = creation
        self._creating_workers += workers
        self._startup_parallelism_current += 1
        self._startup_parallelism_peak = max(
            self._startup_parallelism_peak,
            self._startup_parallelism_current,
        )
        return creation

    def _finish_creation(
        self,
        lookup_key: LookupKey,
        creation: _PoolCreation,
        *,
        record: PoolRecord | None,
        error: BaseException | None,
    ) -> None:
        current = self._creating.get(lookup_key)
        if current is creation:
            self._creating.pop(lookup_key, None)
        self._creating_workers -= creation.workers
        self._startup_parallelism_current -= 1
        creation.error = error
        if error is not None:
            self._creation_failures += 1
        if record is not None:
            self._records[lookup_key] = record
            self._created_pools += 1
        creation.event.set()
        self._condition.notify_all()

    def _create_record(
        self,
        *,
        creation: _PoolCreation,
        lookup_key: LookupKey,
        backend_name: str,
        model_path: Path,
        registry_path: Path,
        workers: int,
        visible: bool,
        model_digest: str,
        registry_digest: str,
        compatibility_profile: str,
    ) -> PoolRecord:
        try:
            record = self._new_record(
                lookup_key=lookup_key,
                backend_name=backend_name,
                model_path=model_path,
                registry_path=registry_path,
                workers=workers,
                visible=visible,
                model_digest=model_digest,
                registry_digest=registry_digest,
                compatibility_profile=compatibility_profile,
            )
        except BaseException as exc:
            with self._condition:
                self._finish_creation(
                    lookup_key,
                    creation,
                    record=None,
                    error=exc,
                )
            raise

        with self._condition:
            if self._closed:
                error = RuntimeError("PoolManager closed while CasePool was starting")
                self._finish_creation(
                    lookup_key,
                    creation,
                    record=None,
                    error=error,
                )
            else:
                record.leases = 1
                record.last_used_monotonic = time.monotonic()
                self._finish_creation(
                    lookup_key,
                    creation,
                    record=record,
                    error=None,
                )
                return record
        record.pool.close()
        raise error

    @contextmanager
    def acquire(
        self,
        *,
        backend_name: str,
        model_path: Path,
        registry_path: Path,
        workers: int,
        visible: bool,
    ) -> Iterator[CasePool]:
        resolved_model = model_path.resolve()
        resolved_registry = registry_path.resolve()
        effective_workers = max(1, min(workers, self.license_slots))
        model_digest = sha256_file(resolved_model)
        registry_digest = sha256_file(resolved_registry)
        compatibility_profile = self._compatibility_profile(
            workers=effective_workers,
            visible=visible,
        )
        lookup_key: LookupKey = (
            backend_name,
            model_digest,
            registry_digest,
            compatibility_profile,
        )

        creator = False
        creation: _PoolCreation | None = None
        record: PoolRecord | None = None
        while record is None:
            with self._condition:
                if self._closed:
                    raise RuntimeError("PoolManager is closed")
                record = self._records.get(lookup_key)
                if record is not None:
                    self._reused_leases += 1
                    record.leases += 1
                    record.last_used_monotonic = time.monotonic()
                    break
                creation = self._creating.get(lookup_key)
                if creation is None:
                    creation = self._reserve_creation(lookup_key, effective_workers)
                    creator = True
                    break
                self._creation_waiters += 1
            try:
                creation.event.wait()
            finally:
                with self._condition:
                    self._creation_waiters -= 1
            if creation.error is not None:
                raise creation.error

        if creator:
            assert creation is not None
            record = self._create_record(
                creation=creation,
                lookup_key=lookup_key,
                backend_name=backend_name,
                model_path=resolved_model,
                registry_path=resolved_registry,
                workers=effective_workers,
                visible=visible,
                model_digest=model_digest,
                registry_digest=registry_digest,
                compatibility_profile=compatibility_profile,
            )
        assert record is not None

        record.execution_lock.acquire()
        try:
            yield record.pool
        finally:
            record.execution_lock.release()
            with self._condition:
                record.leases -= 1
                record.last_used_monotonic = time.monotonic()
                self._condition.notify_all()

    def evict_idle(self) -> int:
        with self._condition:
            before = len(self._records)
            self._evict_expired(time.monotonic())
            return before - len(self._records)

    def stats(self) -> dict[str, Any]:
        with self._condition:
            return {
                "resident_cases": len(self._records),
                "resident_workers": self._resident_workers(),
                "license_slots": self.license_slots,
                "created_pools": self._created_pools,
                "reused_leases": self._reused_leases,
                "evicted_pools": self._evicted_pools,
                "creating_cases": len(self._creating),
                "creating_workers": self._creating_workers,
                "creation_waiters": self._creation_waiters,
                "creation_failures": self._creation_failures,
                "startup_parallelism_peak": self._startup_parallelism_peak,
                "cases": [
                    {
                        "backend": record.key.backend,
                        "runtime_identity_hash": record.key.runtime_identity_hash,
                        "model_digest": record.key.model_digest,
                        "registry_digest": record.key.registry_digest,
                        "workers": record.workers,
                        "leases": record.leases,
                    }
                    for record in self._records.values()
                ],
            }

    def close(self) -> None:
        with self._condition:
            if self._closed:
                return
            active = [record for record in self._records.values() if record.leases]
            if active:
                raise RuntimeError("Cannot close PoolManager while CasePools are leased")
            self._closed = True
            creations = list(self._creating.values())
        for creation in creations:
            creation.event.wait()
        with self._condition:
            records = list(self._records.values())
            self._records.clear()
        for record in records:
            record.pool.close()

    def __enter__(self) -> PoolManager:
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        del exc_type, exc, traceback
        self.close()
