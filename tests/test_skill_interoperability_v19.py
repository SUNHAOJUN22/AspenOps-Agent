from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents/skills/aspenops-acceptance-maintainer"


def load(path: Path) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate key: {key}")
            result[key] = value
        return result

    def constant(value: str) -> Any:
        raise ValueError(f"non-finite JSON constant: {value}")

    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=pairs,
        parse_constant=constant,
    )


def test_interoperability_contract_is_fail_closed() -> None:
    contract = load(SKILL / "references/interoperability-v1.json")
    assert contract["schema_version"] == "tsao-scientific-interoperability/v1"
    assert contract["scientific_quantity"]["boolean_is_numeric"] is False
    assert contract["scientific_quantity"]["unknown_is_zero"] is False
    assert contract["status_lattice"]["software_pass_implies_external_acceptance"] is False
    order = contract["status_lattice"]["severity_order"]
    assert order.index("FAIL") < order.index("HOLD") < order.index("PASS")


def test_existing_model_routing_status_remains_truthful() -> None:
    status = load(SKILL / "evals/MODEL_EVAL_STATUS.json")
    assert status["status"] == "NOT_RUN"


def test_boolean_nan_and_infinity_are_not_scientific_values() -> None:
    for value in (True, False, float("nan"), float("inf"), -float("inf")):
        valid = (
            not isinstance(value, bool)
            and isinstance(value, int | float)
            and math.isfinite(float(value))
        )
        assert valid is False
