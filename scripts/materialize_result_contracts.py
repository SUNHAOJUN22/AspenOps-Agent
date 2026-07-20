from __future__ import annotations

from pathlib import Path


def main() -> None:
    script = Path(__file__)
    path = Path("src/aspenops_nexus/models.py")
    text = path.read_text(encoding="utf-8")
    old_bounds = '''def _nonnegative_number(value: Any, label: str) -> float:
    number = _finite_number(value, label)
    if number < 0:
        raise ValueError(f"{label} must be a finite non-negative number")
    return number
'''
    new_bounds = '''def _nonnegative_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{label} must be a finite non-negative number")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{label} must be a finite non-negative number")
    return number


def _positive_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{label} must be a finite positive number")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{label} must be a finite positive number")
    return number
'''
    if old_bounds not in text:
        raise RuntimeError("numeric bound helper anchor not found")
    text = text.replace(old_bounds, new_bounds, 1)
    old_timeout = (
        '        timeout_s = _finite_number(mapping.get("timeout_s", 1200.0), '
        '"timeout_s")\n'
        "        if timeout_s <= 0:\n"
        '            raise ValueError("timeout_s must be a finite positive number")\n'
    )
    new_timeout = (
        '        timeout_s = _positive_number(mapping.get("timeout_s", 1200.0), '
        '"timeout_s")\n'
    )
    if old_timeout not in text:
        raise RuntimeError("timeout validation anchor not found")
    text = text.replace(old_timeout, new_timeout, 1)

    marker = "@dataclass(slots=True)\nclass EvaluationResult:"
    start = text.index(marker)
    replacement = '''@dataclass(slots=True)
class EvaluationResult:
    ok: bool
    communication_ok: bool
    engine_ok: bool
    converged: bool
    feasible: bool
    values: dict[str, Any]
    units: dict[str, str | None]
    violations: list[str]
    diagnostics: dict[str, Any]
    elapsed_s: float
    balance_residuals: dict[str, dict[str, float]] = field(default_factory=dict)
    cache_source: CacheSource = "computed"
    cache_hit: bool = False
    request_hash: str = ""
    worker_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvaluationResult:
        mapping = _object(data, "evaluation result")

        def required_bool(name: str, default: bool | None = None) -> bool:
            if name not in mapping:
                if default is None:
                    raise ValueError(f"evaluation result is missing {name}")
                return default
            value = mapping[name]
            if not isinstance(value, bool):
                raise ValueError(f"result {name} must be a boolean")
            return value

        communication_ok = required_bool("communication_ok")
        engine_ok = required_bool("engine_ok", communication_ok)
        values = _object(mapping.get("values"), "result values")
        raw_units = _object(mapping.get("units"), "result units")
        units: dict[str, str | None] = {}
        for key, value in raw_units.items():
            if value is not None and not isinstance(value, str):
                raise ValueError("result unit values must be strings or null")
            units[str(key)] = value

        raw_violations = _array(mapping.get("violations"), "result violations")
        if not all(isinstance(item, str) for item in raw_violations):
            raise ValueError("result violations must contain only strings")
        violations = [str(item) for item in raw_violations]
        diagnostics = _object(mapping.get("diagnostics"), "result diagnostics")

        raw_balances = _object(
            mapping.get("balance_residuals", {}),
            "result balance_residuals",
        )
        balances: dict[str, dict[str, float]] = {}
        for name, raw_detail in raw_balances.items():
            detail = _object(raw_detail, f"result balance_residuals[{name}]")
            normalized_detail: dict[str, float] = {}
            for key, value in detail.items():
                normalized_detail[str(key)] = _finite_number(
                    value,
                    f"result balance_residuals[{name}].{key}",
                )
            balances[str(name)] = normalized_detail

        cache_source = mapping.get("cache_source", "computed")
        if cache_source not in {
            "computed",
            "persistent_cache",
            "same_batch_dedup",
            "inflight_singleflight",
        }:
            raise ValueError(f"Unsupported result cache_source: {cache_source}")
        cache_hit = mapping.get("cache_hit", cache_source != "computed")
        if not isinstance(cache_hit, bool):
            raise ValueError("result cache_hit must be a boolean")
        request_hash = mapping.get("request_hash", "")
        if not isinstance(request_hash, str):
            raise ValueError("result request_hash must be a string")
        worker_id = mapping.get("worker_id")
        if worker_id is not None and (
            isinstance(worker_id, bool) or not isinstance(worker_id, int)
        ):
            raise ValueError("result worker_id must be an integer or null")

        known = {
            "ok",
            "communication_ok",
            "engine_ok",
            "converged",
            "feasible",
            "values",
            "units",
            "violations",
            "diagnostics",
            "elapsed_s",
            "balance_residuals",
            "cache_source",
            "cache_hit",
            "request_hash",
            "worker_id",
        }
        unknown = sorted(set(mapping) - known)
        if unknown:
            raise ValueError(f"Unsupported evaluation result fields: {', '.join(unknown)}")

        return cls(
            ok=required_bool("ok"),
            communication_ok=communication_ok,
            engine_ok=engine_ok,
            converged=required_bool("converged"),
            feasible=required_bool("feasible"),
            values=values,
            units=units,
            violations=violations,
            diagnostics=diagnostics,
            elapsed_s=_nonnegative_number(mapping.get("elapsed_s"), "elapsed_s"),
            balance_residuals=balances,
            cache_source=cast(CacheSource, cache_source),
            cache_hit=cache_hit,
            request_hash=request_hash,
            worker_id=worker_id,
        )
'''
    path.write_text(text[:start] + replacement, encoding="utf-8")
    script.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
