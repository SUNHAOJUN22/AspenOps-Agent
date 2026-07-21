from __future__ import annotations

import pytest

from aspenops_nexus.config import Settings, _env_float


def test_settings_load_resource_budgets_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASPENOPS_MAX_REQUEST_BYTES", "1234")
    monkeypatch.setenv("ASPENOPS_MAX_BATCH_POINTS", "234")
    monkeypatch.setenv("ASPENOPS_MAX_SEMANTIC_OPERATIONS", "3456")
    monkeypatch.setenv("ASPENOPS_MAX_OPTIMIZATION_EVALUATIONS", "456")
    monkeypatch.setenv("ASPENOPS_MAX_OPTIMIZATION_VARIABLES", "12")
    monkeypatch.setenv("ASPENOPS_MAX_OPTIMIZATION_OBJECTIVES", "7")

    settings = Settings.from_env()

    assert settings.max_request_bytes == 1234
    assert settings.max_batch_points == 234
    assert settings.max_semantic_operations == 3456
    assert settings.max_optimization_evaluations == 456
    assert settings.max_optimization_variables == 12
    assert settings.max_optimization_objectives == 7


@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_float_environment_values_must_be_finite(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv("FINITE_FLOAT", value)
    with pytest.raises(ValueError, match="FINITE_FLOAT must be finite"):
        _env_float("FINITE_FLOAT", 1.0)


@pytest.mark.parametrize(
    "name",
    [
        "ASPENOPS_MAX_REQUEST_BYTES",
        "ASPENOPS_MAX_BATCH_POINTS",
        "ASPENOPS_MAX_SEMANTIC_OPERATIONS",
        "ASPENOPS_MAX_OPTIMIZATION_EVALUATIONS",
        "ASPENOPS_MAX_OPTIMIZATION_VARIABLES",
        "ASPENOPS_MAX_OPTIMIZATION_OBJECTIVES",
    ],
)
def test_resource_budget_environment_values_must_be_positive(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
) -> None:
    monkeypatch.setenv(name, "0")
    with pytest.raises(ValueError, match=f"{name} must be >= 1"):
        Settings.from_env()
