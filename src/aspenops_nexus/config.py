from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid Boolean environment variable {name}={raw!r}")


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    value = int(os.getenv(name, str(default)))
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    value = float(os.getenv(name, str(default)))
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _inside(path: Path, roots: tuple[Path, ...]) -> bool:
    return any(path == root or root in path.parents for root in roots)


@dataclass(frozen=True, slots=True)
class Settings:
    backend: str = "mock"
    mode: str = "default"
    allowed_roots: tuple[Path, ...] = ()
    license_slots: int = 1
    max_workers: int = 1
    timeout_s: float = 1200.0
    startup_timeout_s: float = 90.0
    worker_max_points: int = 200
    worker_max_age_s: float = 14_400.0
    visible: bool = False
    state_dir: Path = Path("var")
    cache_failures: bool = False
    scheduler_poll_s: float = 0.25
    max_resident_cases: int = 2
    pool_idle_timeout_s: float = 1800.0
    job_lease_s: float = 30.0
    cancellation_grace_s: float = 2.0
    job_max_attempts: int = 3
    max_request_bytes: int = 10_000_000
    max_batch_points: int = 10_000
    max_semantic_operations: int = 1_000_000
    max_optimization_evaluations: int = 10_000
    max_optimization_variables: int = 64
    max_optimization_objectives: int = 16

    @classmethod
    def from_env(cls) -> Settings:
        backend = os.getenv("ASPENOPS_BACKEND", "mock").strip().lower()
        if backend not in {"mock", "aspen_plus", "hysys"}:
            raise ValueError(f"Unsupported ASPENOPS_BACKEND={backend!r}")

        root_values = tuple(
            value.strip()
            for value in os.getenv("ASPENOPS_ALLOWED_ROOTS", "").split(";")
            if value.strip()
        )
        if backend != "mock":
            relative_roots = [
                value
                for value in root_values
                if not Path(value).expanduser().is_absolute()
            ]
            if relative_roots:
                raise ValueError("Every ASPENOPS_ALLOWED_ROOTS entry must be absolute")
        roots = tuple(Path(value).expanduser().resolve() for value in root_values)

        state_value = os.getenv("ASPENOPS_STATE_DIR", "var").strip()
        if not state_value:
            raise ValueError("ASPENOPS_STATE_DIR must be non-empty")
        state_path = Path(state_value).expanduser()
        if backend != "mock" and roots and not state_path.is_absolute():
            raise ValueError("ASPENOPS_STATE_DIR must be absolute for a real backend")
        state_dir = state_path.resolve()
        if backend != "mock" and roots and not _inside(state_dir, roots):
            raise ValueError("ASPENOPS_STATE_DIR must be inside ASPENOPS_ALLOWED_ROOTS")

        slots = _env_int("ASPENOPS_LICENSE_SLOTS", 1)
        max_workers = _env_int("ASPENOPS_MAX_WORKERS", slots)
        mode = os.getenv("ASPENOPS_MODE", "default").strip().lower()
        if mode not in {"readonly", "default", "enhanced"}:
            raise ValueError(f"Unsupported ASPENOPS_MODE={mode!r}")
        return cls(
            backend=backend,
            mode=mode,
            allowed_roots=roots,
            license_slots=slots,
            max_workers=max_workers,
            timeout_s=_env_float("ASPENOPS_TIMEOUT_S", 1200.0, 0.001),
            startup_timeout_s=_env_float("ASPENOPS_STARTUP_TIMEOUT_S", 90.0, 0.001),
            worker_max_points=_env_int("ASPENOPS_WORKER_MAX_POINTS", 200),
            worker_max_age_s=_env_float("ASPENOPS_WORKER_MAX_AGE_S", 14_400.0, 1.0),
            visible=_env_bool("ASPENOPS_VISIBLE", False),
            state_dir=state_dir,
            cache_failures=_env_bool("ASPENOPS_CACHE_FAILURES", False),
            scheduler_poll_s=_env_float("ASPENOPS_SCHEDULER_POLL_S", 0.25, 0.01),
            max_resident_cases=_env_int("ASPENOPS_MAX_RESIDENT_CASES", 2),
            pool_idle_timeout_s=_env_float("ASPENOPS_POOL_IDLE_TIMEOUT_S", 1800.0, 1.0),
            job_lease_s=_env_float("ASPENOPS_JOB_LEASE_S", 30.0, 1.0),
            cancellation_grace_s=_env_float("ASPENOPS_CANCELLATION_GRACE_S", 2.0, 0.0),
            job_max_attempts=_env_int("ASPENOPS_JOB_MAX_ATTEMPTS", 3),
            max_request_bytes=_env_int("ASPENOPS_MAX_REQUEST_BYTES", 10_000_000),
            max_batch_points=_env_int("ASPENOPS_MAX_BATCH_POINTS", 10_000),
            max_semantic_operations=_env_int(
                "ASPENOPS_MAX_SEMANTIC_OPERATIONS",
                1_000_000,
            ),
            max_optimization_evaluations=_env_int(
                "ASPENOPS_MAX_OPTIMIZATION_EVALUATIONS",
                10_000,
            ),
            max_optimization_variables=_env_int(
                "ASPENOPS_MAX_OPTIMIZATION_VARIABLES",
                64,
            ),
            max_optimization_objectives=_env_int(
                "ASPENOPS_MAX_OPTIMIZATION_OBJECTIVES",
                16,
            ),
        )

    @property
    def effective_workers(self) -> int:
        return max(1, min(self.max_workers, self.license_slots))
