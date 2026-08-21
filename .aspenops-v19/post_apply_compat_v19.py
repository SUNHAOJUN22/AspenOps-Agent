from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count == 0 and new in text:
        return
    if count != 1:
        raise RuntimeError(f"expected one pattern in {path}, found {count}: {old!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


def repair_model_serialization() -> None:
    path = ROOT / "src/aspenops_nexus/models.py"
    old = '''    if item.dimension is not None:\n        payload["dimension"] = item.dimension\n    if item.base_unit is not None:\n        payload["base_unit"] = item.base_unit\n    return payload\n'''
    new = '''    payload["dimension"] = item.dimension\n    payload["base_unit"] = item.base_unit\n    return payload\n'''
    replace_once(path, old, new)


def repair_compiled_balance_compatibility() -> None:
    path = ROOT / "src/aspenops_nexus/evaluation_plan.py"
    old = '''class CompiledBalance:\n    spec: BalanceSpec\n    terms: tuple[CompiledBalanceTerm, ...]\n    dimension: str\n    base_unit: str\n'''
    new = '''class CompiledBalance:\n    spec: BalanceSpec\n    terms: tuple[CompiledBalanceTerm, ...]\n    dimension: str | None = None\n    base_unit: str | None = None\n'''
    replace_once(path, old, new)


def repair_runtime_compatibility() -> None:
    path = ROOT / "src/aspenops_nexus/evaluation.py"
    text = path.read_text(encoding="utf-8")
    old_import = "from .units import convert\n"
    new_import = "from .units import convert, dimension as unit_dimension\n"
    if old_import in text:
        text = text.replace(old_import, new_import, 1)
    elif new_import not in text:
        raise RuntimeError("evaluation unit import was not found")

    loop = '''        for compiled_balance in active_plan.balances:\n            name = compiled_balance.spec.name\n            signed_terms: list[float] = []\n'''
    replacement = '''        for compiled_balance in active_plan.balances:\n            name = compiled_balance.spec.name\n            if not compiled_balance.terms:\n                raise ValueError(f"Compiled balance {name} has no terms")\n            first_term = compiled_balance.terms[0]\n            balance_base_unit = (\n                compiled_balance.base_unit\n                or first_term.spec.unit\n                or first_term.node.native_unit\n            )\n            if balance_base_unit is None:\n                raise ValueError(f"Compiled balance {name} has no canonical base unit")\n            balance_dimension = compiled_balance.dimension or unit_dimension(balance_base_unit)\n            if balance_dimension is None:\n                raise ValueError(f"Compiled balance {name} has no physical dimension")\n            signed_terms: list[float] = []\n'''
    if loop in text:
        text = text.replace(loop, replacement, 1)
    elif replacement not in text:
        raise RuntimeError("compiled balance loop was not found")

    text = text.replace("compiled_balance.base_unit", "balance_base_unit")
    text = text.replace("compiled_balance.dimension", "balance_dimension")

    old_violation = '''                violations.append(f"balance_invalid:{name}")\n                violations.append(f"balance_failed:{name}")\n'''
    new_violation = '''                violations.append(f"balance_non_finite:{name}")\n                violations.append(f"balance_invalid:{name}")\n                violations.append(f"balance_failed:{name}")\n'''
    count = text.count(old_violation)
    if count == 2:
        text = text.replace(old_violation, new_violation)
    elif count == 0 and text.count('violations.append(f"balance_non_finite:{name}")') >= 2:
        pass
    else:
        raise RuntimeError(f"expected two invalid-balance violation blocks, found {count}")

    compile(text, path.as_posix(), "exec")
    path.write_text(text, encoding="utf-8", newline="\n")


def extend_contract_tests() -> None:
    path = ROOT / "tests/test_balance_dimension_contract_v19.py"
    text = path.read_text(encoding="utf-8")
    marker = "def test_declared_balance_contracts_fail_closed_v19"
    if marker in text:
        return
    addition = r'''


def test_declared_balance_contracts_fail_closed_v19(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    common = {
        "model_path": str(tmp_path / "static.json"),
        "registry_path": str(tmp_path / "registry.json"),
        "backend": "mock",
        "writes": [],
        "reads": [],
    }
    wrong_dimension = EvaluationRequest.from_dict(
        {
            **common,
            "balances": [
                {
                    "name": "wrong-dimension",
                    "dimension": "power",
                    "terms": [
                        {"key": "mass.hour", "identifiers": {}, "coefficient": 1},
                        {"key": "mass.second", "identifiers": {}, "coefficient": -1},
                    ],
                }
            ],
        }
    )
    with pytest.raises(ValueError, match="declares dimension"):
        EvaluationPlanCompiler.compile(registry, wrong_dimension)

    wrong_base = EvaluationRequest.from_dict(
        {
            **common,
            "balances": [
                {
                    "name": "wrong-base",
                    "dimension": "mass_flow",
                    "base_unit": "kW",
                    "terms": [
                        {"key": "mass.hour", "identifiers": {}, "coefficient": 1},
                        {"key": "mass.second", "identifiers": {}, "coefficient": -1},
                    ],
                }
            ],
        }
    )
    with pytest.raises(ValueError, match="base unit"):
        EvaluationPlanCompiler.compile(registry, wrong_base)

    wrong_term_unit = EvaluationRequest.from_dict(
        {
            **common,
            "balances": [
                {
                    "name": "wrong-term-unit",
                    "terms": [
                        {
                            "key": "mass.hour",
                            "identifiers": {},
                            "coefficient": 1,
                            "unit": "kW",
                        }
                    ],
                }
            ],
        }
    )
    with pytest.raises(ValueError, match="requests incompatible unit"):
        EvaluationPlanCompiler.compile(registry, wrong_term_unit)


def test_optional_balance_contract_fields_remain_explicit_in_documents_v19(
    tmp_path: Path,
) -> None:
    request = EvaluationRequest.from_dict(
        {
            "model_path": str(tmp_path / "static.json"),
            "registry_path": str(tmp_path / "registry.json"),
            "backend": "mock",
            "writes": [],
            "reads": [],
            "balances": [
                {
                    "name": "legacy",
                    "terms": [
                        {"key": "mass.hour", "identifiers": {}, "coefficient": 1}
                    ],
                }
            ],
        }
    )
    balance = request.to_dict()["balances"][0]
    assert balance["dimension"] is None
    assert balance["base_unit"] is None
    assert request.physical_identity()["balances"][0]["dimension"] is None
'''
    path.write_text(text + addition, encoding="utf-8", newline="\n")


def main() -> int:
    repair_model_serialization()
    repair_compiled_balance_compatibility()
    repair_runtime_compatibility()
    extend_contract_tests()
    print(
        {
            "status": "APPLIED",
            "contract": "balance-v19 backward-compatible scientific closure",
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
