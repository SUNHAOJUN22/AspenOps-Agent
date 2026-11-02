from __future__ import annotations

from pathlib import Path

import pytest

from aspenops_nexus.batch import dry_run_document, run_batch_document
from aspenops_nexus.config import Settings
from aspenops_nexus.json_input import load_request_object

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("purity_limit,expected_ok", [(0.85, True), (0.99999, False)])
def test_readme_guarded_example_executes_and_enforces_declared_checks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    purity_limit: float,
    expected_ok: bool,
) -> None:
    monkeypatch.chdir(ROOT)
    settings = Settings(state_dir=tmp_path, license_slots=2, max_workers=2)
    request = load_request_object(
        ROOT / "examples/guarded-mock-batch.example.json",
        max_bytes=settings.max_request_bytes,
    )
    request["constraints"][0]["value"] = purity_limit
    validation = dry_run_document(request, settings)
    assert validation["evaluations"] == 3
    assert validation["effective_workers"] == 2

    results = run_batch_document(request, settings)
    assert len(results) == 3
    for result in results:
        assert result["ok"] is expected_ok
        assert result["communication_ok"] and result["engine_ok"] and result["converged"]
        assert result["balance_residuals"]["declared_feed_setpoint"]["passed"] is True
        assert result["balance_residuals"]["declared_feed_setpoint"]["residual"] == 0.0
        assert result["diagnostics"]["constraints"][0]["passed"] is expected_ok
        assert result["units"]["stream.output.purity:stream=PRODUCT"] == "fraction"
        assert ("constraint_failed:minimum_product_purity" in result["violations"]) is (
            not expected_ok
        )
