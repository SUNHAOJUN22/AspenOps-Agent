from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "tests/test_balance_dimension_contract_v19.py"
MARKER = "def test_precompiled_balance_contract_failures_are_structured_v19"


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    if MARKER in text:
        print({"status": "ALREADY_APPLIED", "target": TARGET.relative_to(ROOT).as_posix()})
        return 0

    if "from dataclasses import replace\n" not in text:
        text = text.replace(
            "import math\n",
            "import math\nimport sys\nfrom dataclasses import replace\n",
            1,
        )

    addition = r'''


def _compiled_mass_plan(tmp_path: Path, *, base_unit: str = "kg/h"):
    registry = _registry(tmp_path)
    return registry, EvaluationPlanCompiler.compile(
        registry,
        _request(tmp_path, base_unit=base_unit),
    )


def test_precompiled_balance_contract_failures_are_structured_v19(
    tmp_path: Path,
) -> None:
    registry, plan = _compiled_mass_plan(tmp_path)
    model = tmp_path / "static.json"
    model.write_text("{}", encoding="utf-8")

    empty_balance = replace(plan.balances[0], terms=())
    backend = StaticBackend({"mass_hour": 1.0, "mass_second": 1.0})
    backend.open(model)
    empty_result = evaluate(backend, registry, _request(tmp_path), plan=replace(plan, balances=(empty_balance,)))
    backend.close()
    assert not empty_result.ok
    assert "execution_error:ValueError" in empty_result.violations
    assert "no terms" in empty_result.diagnostics["exception"]

    first = plan.balances[0].terms[0]
    no_unit_first = replace(first, node=replace(first.node, native_unit=None))
    no_unit_balance = replace(plan.balances[0], base_unit=None, terms=(no_unit_first,))
    backend = StaticBackend({"mass_hour": 1.0, "mass_second": 1.0})
    backend.open(model)
    no_unit_result = evaluate(
        backend,
        registry,
        _request(tmp_path),
        plan=replace(plan, balances=(no_unit_balance,)),
    )
    backend.close()
    assert not no_unit_result.ok
    assert "execution_error:ValueError" in no_unit_result.violations
    assert "canonical base unit" in no_unit_result.diagnostics["exception"]


def test_balance_non_numeric_and_signed_overflow_are_invalid_v19(tmp_path: Path) -> None:
    registry, plan = _compiled_mass_plan(tmp_path)
    model = tmp_path / "static.json"
    model.write_text("{}", encoding="utf-8")

    backend = StaticBackend({"mass_hour": "not-a-number", "mass_second": 0.0})
    backend.open(model)
    non_numeric = evaluate(backend, registry, _request(tmp_path, base_unit="kg/h"), plan=plan)
    backend.close()
    assert not non_numeric.ok
    assert non_numeric.balance_residuals["mass"]["status"] == "invalid"
    assert non_numeric.diagnostics["invalid_balances"]["mass"][0]["value"] == "non_numeric:str"

    first = plan.balances[0].terms[0]
    overflowing_first = replace(first, spec=replace(first.spec, coefficient=2.0))
    overflow_balance = replace(
        plan.balances[0],
        terms=(overflowing_first, plan.balances[0].terms[1]),
    )
    backend = StaticBackend({"mass_hour": sys.float_info.max, "mass_second": 0.0})
    backend.open(model)
    overflow = evaluate(
        backend,
        registry,
        _request(tmp_path, base_unit="kg/h"),
        plan=replace(plan, balances=(overflow_balance,)),
    )
    backend.close()
    assert not overflow.ok
    assert overflow.diagnostics["invalid_balances"]["mass"][0]["value"] == "derived_overflow"
    assert "balance_non_finite:mass" in overflow.violations


def test_balance_aggregate_overflow_is_invalid_not_zero_v19(tmp_path: Path) -> None:
    registry, plan = _compiled_mass_plan(tmp_path)
    model = tmp_path / "static.json"
    model.write_text("{}", encoding="utf-8")
    second = plan.balances[0].terms[1]
    positive_second = replace(second, spec=replace(second.spec, coefficient=1.0))
    aggregate_balance = replace(
        plan.balances[0],
        terms=(plan.balances[0].terms[0], positive_second),
    )
    backend = StaticBackend(
        {"mass_hour": sys.float_info.max, "mass_second": sys.float_info.max / 3600.0}
    )
    backend.open(model)
    result = evaluate(
        backend,
        registry,
        _request(tmp_path, base_unit="kg/h"),
        plan=replace(plan, balances=(aggregate_balance,)),
    )
    backend.close()
    detail = result.balance_residuals["mass"]
    assert not result.ok
    assert detail["status"] == "invalid"
    assert detail["residual"] is None
    assert result.diagnostics["invalid_balances"]["mass"] == [
        {"identity": "derived_balance", "value": "derived_overflow"}
    ]
'''
    TARGET.write_text(text + addition, encoding="utf-8", newline="\n")
    print({"status": "APPLIED", "target": TARGET.relative_to(ROOT).as_posix()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
