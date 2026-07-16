from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path

_VALID_BACKENDS = {"mock", "aspen_plus", "hysys"}
_VALID_MODES = {"readonly", "default", "enhanced"}


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
    if not math.isfinite(value) or value < minimum:
        raise ValueError(f"{name} must be finite and >= {minimum}")
    return value


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
    max_batch_points: int = 10_000
    max_operations_per_request: int = 10_000
    max_request_bytes: int = 10 * 1024 * 1024

    def __post_init__(self) -> None:
        if self.backend not in _VALID_BACKENDS:
            raise ValueError(f"Unsupported backend={self.backend!r}")
        if self.mode not in _VALID_MODES:
            raise ValueError(f"Unsupported mode={self.mode!r}")
        for integer_name, integer_value in (
            ("license_slots", self.license_slots),
            ("max_workers", self.max_workers),
            ("worker_max_points", self.worker_max_points),
            ("max_batch_points", self.max_batch_points),
            ("max_operations_per_request", self.max_operations_per_request),
            ("max_request_bytes", self.max_request_bytes),
        ):
            if (
                isinstance(integer_value, bool)
                or not isinstance(integer_value, int)
                or integer_value < 1
            ):
                raise ValueError(f"{integer_name} must be an integer >= 1")
        for float_name, float_value, minimum in (
            ("timeout_s", self.timeout_s, 0.001),
            ("startup_timeout_s", self.startup_timeout_s, 0.001),
            ("worker_max_age_s", self.worker_max_age_s, 1.0),
            ("scheduler_poll_s", self.scheduler_poll_s, 0.01),
        ):
            if (
                isinstance(float_value, bool)
                or not math.isfinite(float_value)
                or float_value < minimum
            ):
                raise ValueError(f"{float_name} must be finite and >= {minimum}")

    @classmethod
    def from_env(cls) -> Settings:
        roots = tuple(
            Path(x).expanduser().resolve()
            for x in os.getenv("ASPENOPS_ALLOWED_ROOTS", "").split(";")
            if x.strip()
        )
        slots = _env_int("ASPENOPS_LICENSE_SLOTS", 1)
        max_workers = _env_int("ASPENOPS_MAX_WORKERS", slots)
        backend = os.getenv("ASPENOPS_BACKEND", "mock").strip().lower()
        if backend not in _VALID_BACKENDS:
            raise ValueError(f"Unsupported ASPENOPS_BACKEND={backend!r}")
        mode = os.getenv("ASPENOPS_MODE", "default").strip().lower()
        if mode not in _VALID_MODES:
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
            state_dir=Path(os.getenv("ASPENOPS_STATE_DIR", "var")).expanduser().resolve(),
            cache_failures=_env_bool("ASPENOPS_CACHE_FAILURES", False),
            scheduler_poll_s=_env_float("ASPENOPS_SCHEDULER_POLL_S", 0.25, 0.01),
            max_batch_points=_env_int("ASPENOPS_MAX_BATCH_POINTS", 10_000),
            max_operations_per_request=_env_int("ASPENOPS_MAX_OPERATIONS_PER_REQUEST", 10_000),
            max_request_bytes=_env_int("ASPENOPS_MAX_REQUEST_BYTES", 10 * 1024 * 1024),
        )

    @property
    def effective_workers(self) -> int:
        return min(self.max_workers, self.license_slots)
