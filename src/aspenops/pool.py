"""Persistent worker pool for efficient multi-point evaluation."""

from __future__ import annotations

import shutil
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from aspenops.design import nearest_neighbor_order
from aspenops.errors import WorkerError
from aspenops.models import RunReport, ValueRead, ValueResult, ValueWrite
from aspenops.worker import WorkerClient


class CasePool:
    """Keep one open case per worker and reuse it across many evaluations.

    Each worker receives a private staged model copy. A failed worker is
    explicitly replaced and its staged case is reopened, but the failed point is
    never retried silently because its simulator-side effects are unknown.
    """

    def __init__(
        self,
        *,
        backend: str,
        case_path: Path,
        workers: int = 1,
        timeout_s: float = 120.0,
        backend_options: dict[str, Any] | None = None,
    ) -> None:
        if workers <= 0:
            raise ValueError("workers must be positive")
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        self.backend = backend
        self.case_path = case_path
        self.worker_count = workers
        self.timeout_s = timeout_s
        self.backend_options = backend_options or {}
        self._clients: list[WorkerClient] = []
        self._staged_paths: list[Path] = []
        self._client_locks: list[threading.Lock] = []
        self._temp_dir: tempfile.TemporaryDirectory[str] | None = None

    def start(self) -> None:
        if self._clients:
            return
        self._temp_dir = tempfile.TemporaryDirectory(prefix="aspenops-pool-")
        staging_root = Path(self._temp_dir.name)
        clients: list[WorkerClient] = []
        staged_paths: list[Path] = []
        try:
            for index in range(self.worker_count):
                staged = staging_root / f"worker-{index}" / self.case_path.name
                staged.parent.mkdir(parents=True, exist_ok=True)
                if self.case_path.exists():
                    shutil.copy2(self.case_path, staged)
                client = self._open_client(staged)
                clients.append(client)
                staged_paths.append(staged)
        except Exception:
            for client in clients:
                client.shutdown()
            if self._temp_dir is not None:
                self._temp_dir.cleanup()
                self._temp_dir = None
            raise
        self._clients = clients
        self._staged_paths = staged_paths
        self._client_locks = [threading.Lock() for _ in clients]

    def close(self) -> None:
        for client in self._clients:
            client.shutdown()
        self._clients.clear()
        self._staged_paths.clear()
        self._client_locks.clear()
        if self._temp_dir is not None:
            self._temp_dir.cleanup()
            self._temp_dir = None

    def recover_worker(self, index: int) -> None:
        if not self._clients:
            raise RuntimeError("CasePool is not started")
        if index < 0 or index >= len(self._clients):
            raise IndexError("Worker index is out of range")
        with self._client_locks[index]:
            self._recover_worker_locked(index)

    def evaluate_many(
        self,
        points: list[list[ValueWrite]],
        outputs: list[ValueRead],
        *,
        locality_order: bool = True,
        reinitialize: bool = True,
    ) -> list[dict[str, Any]]:
        if not self._clients:
            self.start()
        if not points:
            return []
        order = list(range(len(points)))
        if locality_order:
            numeric_points = [
                {
                    write.key: float(write.value)
                    for write in point
                    if isinstance(write.value, (int, float)) and not isinstance(write.value, bool)
                }
                for point in points
            ]
            if numeric_points and all(
                item.keys() == numeric_points[0].keys() for item in numeric_points
            ):
                order = nearest_neighbor_order(numeric_points)
        results: list[dict[str, Any] | None] = [None] * len(points)

        def submit(original_index: int, ordinal: int) -> tuple[int, dict[str, Any]]:
            worker_index = ordinal % len(self._clients)
            payload = {
                "writes": [write.model_dump(mode="json") for write in points[original_index]],
                "reads": [read.model_dump(mode="json") for read in outputs],
                "reinitialize": reinitialize,
            }
            with self._client_locks[worker_index]:
                client = self._clients[worker_index]
                try:
                    result = client.call("evaluate", payload)
                except WorkerError:
                    if not client.alive:
                        self._recover_worker_locked(worker_index)
                    raise
            if not isinstance(result, dict):
                raise TypeError("Worker evaluation result must be a mapping")
            return original_index, result

        with ThreadPoolExecutor(max_workers=len(self._clients)) as executor:
            futures = [
                executor.submit(submit, original_index, ordinal)
                for ordinal, original_index in enumerate(order)
            ]
            for future in as_completed(futures):
                original_index, result = future.result()
                results[original_index] = result
        return [result for result in results if result is not None]

    def _open_client(self, staged: Path) -> WorkerClient:
        client = WorkerClient(
            self.backend,
            timeout_s=self.timeout_s,
            backend_options=self.backend_options,
        )
        client.start()
        try:
            client.call("open", {"path": str(staged), "visible": False, "read_only": False})
        except Exception:
            client.shutdown()
            raise
        return client

    def _recover_worker_locked(self, index: int) -> None:
        old_client = self._clients[index]
        old_client.shutdown()
        replacement = self._open_client(self._staged_paths[index])
        self._clients[index] = replacement

    def __enter__(self) -> CasePool:
        self.start()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback_obj: object) -> None:
        del exc_type, exc, traceback_obj
        self.close()


def decode_worker_evaluation(payload: dict[str, Any]) -> tuple[RunReport, list[ValueResult]]:
    run = RunReport.model_validate(payload["run"])
    values = [ValueResult.model_validate(item) for item in payload.get("values", [])]
    return run, values
