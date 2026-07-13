"""Persistent worker pool for efficient multi-point evaluation."""

from __future__ import annotations

import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from aspenops.design import nearest_neighbor_order
from aspenops.errors import WorkerError
from aspenops.models import RunReport, ValueRead, ValueResult, ValueWrite
from aspenops.worker import WorkerClient


class CasePool:
    """Keep one open case per worker and reuse it across many evaluations."""

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
        self.backend = backend
        self.case_path = case_path
        self.worker_count = workers
        self.timeout_s = timeout_s
        self.backend_options = backend_options or {}
        self._clients: list[WorkerClient] = []
        self._temp_dir: tempfile.TemporaryDirectory[str] | None = None
        self._broken = False

    def start(self) -> None:
        if self._broken:
            raise WorkerError("CasePool is broken after a worker failure; create a new pool")
        if self._clients:
            return
        self._temp_dir = tempfile.TemporaryDirectory(prefix="aspenops-pool-")
        staging_root = Path(self._temp_dir.name)
        clients: list[WorkerClient] = []
        try:
            for index in range(self.worker_count):
                staged = staging_root / f"worker-{index}" / self.case_path.name
                staged.parent.mkdir(parents=True, exist_ok=True)
                if self.case_path.exists():
                    shutil.copy2(self.case_path, staged)
                client = WorkerClient(
                    self.backend,
                    timeout_s=self.timeout_s,
                    backend_options=self.backend_options,
                )
                client.start()
                client.call("open", {"path": str(staged), "visible": False, "read_only": False})
                clients.append(client)
        except Exception:
            for client in clients:
                client.shutdown()
            self._cleanup_temp_dir()
            raise
        self._clients = clients

    def close(self) -> None:
        for client in self._clients:
            client.shutdown()
        self._clients.clear()
        self._cleanup_temp_dir()

    def evaluate_many(
        self,
        points: list[list[ValueWrite]],
        outputs: list[ValueRead],
        *,
        locality_order: bool = True,
        reinitialize: bool = True,
    ) -> list[dict[str, Any]]:
        if self._broken:
            raise WorkerError("CasePool is broken after a worker failure; create a new pool")
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
            client = self._clients[ordinal % len(self._clients)]
            payload = {
                "writes": [write.model_dump(mode="json") for write in points[original_index]],
                "reads": [read.model_dump(mode="json") for read in outputs],
                "reinitialize": reinitialize,
            }
            result = client.call("evaluate", payload)
            if not isinstance(result, dict):
                raise TypeError("Worker evaluation result must be a mapping")
            return original_index, result

        try:
            with ThreadPoolExecutor(max_workers=len(self._clients)) as executor:
                futures = [
                    executor.submit(submit, original_index, ordinal)
                    for ordinal, original_index in enumerate(order)
                ]
                for future in as_completed(futures):
                    original_index, result = future.result()
                    results[original_index] = result
        except Exception:
            self._broken = True
            for client in self._clients:
                client.terminate()
            self._clients.clear()
            self._cleanup_temp_dir()
            raise
        return [result for result in results if result is not None]

    def _cleanup_temp_dir(self) -> None:
        if self._temp_dir is not None:
            self._temp_dir.cleanup()
            self._temp_dir = None

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
