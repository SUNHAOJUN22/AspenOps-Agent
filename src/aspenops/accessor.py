"""Validated semantic access to simulator tree nodes."""

from __future__ import annotations

from typing import Any

from aspenops.backends.base import SimulatorBackend
from aspenops.errors import AccessViolation, SimulationError, UnitError, ValidationError
from aspenops.models import AccessMode, ValueRead, ValueResult, ValueWrite
from aspenops.registry import NodeRegistry
from aspenops.units import convert, dimension_of


class SemanticAccessor:
    def __init__(self, backend: SimulatorBackend, registry: NodeRegistry) -> None:
        self.backend = backend
        self.registry = registry
        self._path_cache: dict[tuple[str, tuple[tuple[str, str], ...]], str] = {}

    @property
    def cache_size(self) -> int:
        return len(self._path_cache)

    def clear_cache(self) -> None:
        self._path_cache.clear()

    def get_many(self, requests: list[ValueRead]) -> list[ValueResult]:
        results: list[ValueResult] = []
        for request in requests:
            spec = self.registry.get(request.key)
            if spec.access == AccessMode.WRITE_ONLY:
                raise AccessViolation(f"Node {request.key} is write-only")
            path = self.registry.resolve(
                request.key, request.identifiers, self.backend.exists, self._path_cache
            )
            raw = self.backend.get_raw(path)
            value = raw.value
            result_unit = raw.unit or spec.default_unit
            requested_unit = request.unit
            if requested_unit is not None:
                if result_unit is None:
                    raise UnitError(f"Node {request.key} has no unit metadata")
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    raise UnitError(f"Node {request.key} is not numeric")
                value = convert(float(value), result_unit, requested_unit)
                result_unit = requested_unit
            results.append(
                ValueResult(
                    key=request.key,
                    value=value,
                    unit=result_unit,
                    resolved_path=path,
                )
            )
        return results

    def set_many(self, writes: list[ValueWrite], *, atomic: bool = True) -> list[ValueResult]:
        prepared: list[tuple[ValueWrite, str, Any, str | None]] = []
        for write in writes:
            spec = self.registry.get(write.key)
            if spec.access == AccessMode.READ_ONLY:
                raise AccessViolation(f"Node {write.key} is read-only")
            path = self.registry.resolve(
                write.key, write.identifiers, self.backend.exists, self._path_cache
            )
            value, unit = self._validate_write(write)
            prepared.append((write, path, value, unit))

        originals: list[tuple[str, Any, str | None]] = []
        if atomic:
            originals = [
                (path, raw.value, raw.unit)
                for _, path, _, _ in prepared
                for raw in [self.backend.get_raw(path)]
            ]
        applied = 0
        try:
            for _, path, value, unit in prepared:
                self.backend.set_raw(path, value, unit)
                applied += 1
        except Exception as exc:
            rollback_errors: list[str] = []
            if atomic:
                for path, value, unit in reversed(originals[:applied]):
                    try:
                        self.backend.set_raw(path, value, unit)
                    except Exception as rollback_exc:  # pragma: no cover - rare double failure
                        rollback_errors.append(f"{path}: {rollback_exc}")
            suffix = f"; rollback errors: {rollback_errors}" if rollback_errors else ""
            raise SimulationError(f"Batch write failed after {applied} writes{suffix}") from exc

        return [
            ValueResult(key=write.key, value=value, unit=unit, resolved_path=path)
            for write, path, value, unit in prepared
        ]

    def _validate_write(self, write: ValueWrite) -> tuple[Any, str | None]:
        spec = self.registry.get(write.key)
        value = write.value
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            if spec.quantity not in {"dimensionless", "string", "boolean"}:
                raise ValidationError(f"Node {write.key} requires a numeric value")
            return value, write.unit or spec.default_unit

        numeric = float(value)
        source_unit = write.unit or spec.default_unit
        target_unit = spec.default_unit
        if source_unit is not None:
            if dimension_of(source_unit) != spec.quantity:
                raise UnitError(f"Node {write.key} expects {spec.quantity}, got {source_unit}")
            if target_unit is not None:
                numeric = convert(numeric, source_unit, target_unit)
        if spec.minimum is not None and numeric < spec.minimum:
            raise ValidationError(
                f"Node {write.key} value {numeric} is below minimum {spec.minimum} {target_unit or ''}"
            )
        if spec.maximum is not None and numeric > spec.maximum:
            raise ValidationError(
                f"Node {write.key} value {numeric} is above maximum {spec.maximum} {target_unit or ''}"
            )
        if spec.integer and not numeric.is_integer():
            raise ValidationError(f"Node {write.key} requires an integer value")
        return (int(numeric) if spec.integer else numeric), target_unit
