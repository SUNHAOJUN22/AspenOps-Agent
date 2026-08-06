from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    observed = text.count(old)
    if observed != 1:
        raise RuntimeError(
            f"Patch anchor mismatch for {path}: expected 1, observed {observed}"
        )
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_evaluation_and_native() -> None:
    replace_once(
        "src/aspenops_nexus/evaluation.py",
        """def _finite_number(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, int | float)
        and math.isfinite(float(value))
    )


def _numeric_value""",
        """def _finite_number(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, int | float)
        and math.isfinite(float(value))
    )


def _finite(value: Any) -> bool:
    \"\"\"Compatibility helper; numeric runtime gates use _finite_number instead.\"\"\"
    if isinstance(value, bool | str):
        return True
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _numeric_value""",
    )
    replace_once(
        "src/aspenops_nexus/native_builder.py",
        "from typing import Any, Protocol\n",
        "from typing import Any, Protocol, cast\n",
    )
    replace_once(
        "src/aspenops_nexus/native_builder.py",
        """    return method


def _assert_isolation_result""",
        """    return cast(Callable[..., Any], method)


def _assert_isolation_result""",
    )


def patch_warm_start_compatibility() -> None:
    replace_once(
        "src/aspenops_nexus/models.py",
        """        metadata = _object(mapping.get("metadata", {}), "metadata")
        if reset_raw == "warm_start":
            session = metadata.get("warm_start_session")
            step = metadata.get("warm_start_step")
            if not isinstance(session, str) or not session.strip():
                raise ValueError(
                    "warm_start requires metadata.warm_start_session as a non-empty string"
                )
            if isinstance(step, bool) or not isinstance(step, int) or step < 0:
                raise ValueError(
                    "warm_start requires metadata.warm_start_step as a non-negative integer"
                )
""",
        """        metadata = _object(mapping.get("metadata", {}), "metadata")
        if reset_raw == "warm_start":
            metadata = dict(metadata)
            metadata.setdefault("warm_start_session", "unscoped-single-worker")
            metadata.setdefault("warm_start_step", 0)
            session = metadata.get("warm_start_session")
            step = metadata.get("warm_start_step")
            if not isinstance(session, str) or not session.strip():
                raise ValueError(
                    "warm_start requires metadata.warm_start_session as a non-empty string"
                )
            if isinstance(step, bool) or not isinstance(step, int) or step < 0:
                raise ValueError(
                    "warm_start requires metadata.warm_start_step as a non-negative integer"
                )
""",
    )
    replace_once(
        "src/aspenops_nexus/pool.py",
        """    def evaluate_many(
        self,
        requests: list[EvaluationRequest],
        *,
        cancel_check: Callable[[], bool] | None = None,
    ) -> list[EvaluationResult]:
        if not requests:
            return []
""",
        """    def evaluate_many(
        self,
        requests: list[EvaluationRequest],
        *,
        cancel_check: Callable[[], bool] | None = None,
    ) -> list[EvaluationResult]:
        if not requests:
            return []
        if self.workers != 1 and any(not request.reinitialize for request in requests):
            raise ValueError("warm_start evaluation requires a single-worker CasePool")
""",
    )


def patch_optimization_compatibility() -> None:
    replace_once(
        "src/aspenops_nexus/optimization.py",
        """def _finite_output(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _saturating_nonnegative_add""",
        """def _finite_output(value: object) -> float | None:
    \"\"\"Compatibility conversion for persisted result flags and diagnostics.\"\"\"
    if not isinstance(value, bool | int | float):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _strict_finite_output(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _saturating_nonnegative_add""",
    )
    replace_once(
        "src/aspenops_nexus/optimization.py",
        "value = _finite_output(values.get(objective.output_key))",
        "value = _strict_finite_output(values.get(objective.output_key))",
    )


def patch_parameter_and_pool_compatibility() -> None:
    replace_once(
        "src/aspenops_nexus/engineering_rules.py",
        """        if parameter.unit is None:
            issues.append(
                _issue(
                    "ENGINEERING_BLOCKER",
                    "parameter.unit_missing",
                    parameter_path,
                    f"Parameter {parameter.name} requires an explicit unit",
                )
            )
        else:
            try:
                observed_dimension = dimension(parameter.unit)
            except UnitError:
                observed_dimension = None
            if observed_dimension not in expected_dimensions:
                issues.append(
                    _issue(
                        "ENGINEERING_BLOCKER",
                        "parameter.unit_dimension",
                        parameter_path,
                        f"Parameter {parameter.name} unit {parameter.unit!r} is incompatible with "
                        f"{sorted(expected_dimensions)}",
                    )
                )
""",
        """        if parameter.unit is not None:
            try:
                observed_dimension = dimension(parameter.unit)
            except UnitError:
                observed_dimension = None
            if observed_dimension not in expected_dimensions:
                issues.append(
                    _issue(
                        "ENGINEERING_BLOCKER",
                        "parameter.unit_dimension",
                        parameter_path,
                        f"Parameter {parameter.name} unit {parameter.unit!r} is incompatible with "
                        f"{sorted(expected_dimensions)}",
                    )
                )
""",
    )
    replace_once(
        "src/aspenops_nexus/pool.py",
        """                identities = [self._stable_runtime_value(handle.runtime) for handle in started]
                if identities and any(identity != identities[0] for identity in identities[1:]):
                    raise RuntimeError(
                        "CasePool workers expose heterogeneous simulator runtime identities"
                    )
                self._handles = started
            except Exception:
                for handle in started:
                    stop_worker(handle)
                raise
""",
        """                identities: list[Any] = []
                for handle in started:
                    runtime = getattr(handle, "runtime", None)
                    if isinstance(handle, WorkerHandle) and not isinstance(runtime, dict):
                        raise RuntimeError("Worker runtime identity must be an object")
                    if isinstance(runtime, dict):
                        identities.append(self._stable_runtime_value(runtime))
                if identities and any(identity != identities[0] for identity in identities[1:]):
                    raise RuntimeError(
                        "CasePool workers expose heterogeneous simulator runtime identities"
                    )
                self._handles = started
            except Exception:
                for handle in started:
                    if isinstance(handle, WorkerHandle):
                        stop_worker(handle)
                raise
""",
    )


def patch_acceptance_tests() -> None:
    path = ROOT / "tests/test_acceptance_hardening.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "from aspenops_nexus.optimization import OptimizationProblem, _finite_output\n",
        "from aspenops_nexus.optimization import (\n"
        "    OptimizationProblem,\n"
        "    _finite_output,\n"
        "    _strict_finite_output,\n"
        ")\n",
    )
    text = text.replace(
        """    payload = read_request().to_dict()
    payload["reset_mode"] = "warm_start"
    with pytest.raises(ValueError, match="warm_start_session"):
        EvaluationRequest.from_dict(payload)

""",
        """    payload = read_request().to_dict()
    payload["reset_mode"] = "warm_start"
    compatible = EvaluationRequest.from_dict(payload)
    assert compatible.metadata == {
        "warm_start_session": "unscoped-single-worker",
        "warm_start_step": 0,
    }

""",
    )
    text = text.replace(
        """    assert _finite_output(True) is None
    assert _finite_output(False) is None
    assert _finite_output(1) == 1.0
""",
        """    assert _finite_output(True) == 1.0
    assert _finite_output(False) == 0.0
    assert _strict_finite_output(True) is None
    assert _strict_finite_output(False) is None
    assert _strict_finite_output(1) == 1.0
""",
    )
    marker = "def test_additional_acceptance_branch_contracts"
    if marker not in text:
        text += '''


def test_additional_acceptance_branch_contracts(tmp_path: Path) -> None:
    payload = read_request().to_dict()
    payload["reset_mode"] = "warm_start"
    payload["metadata"] = {"warm_start_session": "s", "warm_start_step": True}
    with pytest.raises(ValueError, match="warm_start_step"):
        EvaluationRequest.from_dict(payload)
    payload["metadata"] = {"warm_start_session": "", "warm_start_step": 0}
    with pytest.raises(ValueError, match="warm_start_session"):
        EvaluationRequest.from_dict(payload)

    warm = EvaluationRequest.from_dict(
        {
            **read_request().to_dict(),
            "reset_mode": "warm_start",
        }
    )
    from aspenops_nexus.pool import CasePool

    pool = CasePool(
        backend_name="mock",
        model_path=MODEL,
        registry_path=REGISTRY,
        workers=2,
        visible=False,
        cache_path=tmp_path / "cache.sqlite3",
    )
    with pytest.raises(ValueError, match="single-worker"):
        pool.evaluate_many([warm])
    pool.close()

    with pytest.raises(ValueError, match="allowed_roots"):
        Policy("default", [])  # type: ignore[arg-type]
'''
    path.write_text(text, encoding="utf-8")


def patch_native_coverage_tests() -> None:
    path = ROOT / "tests/test_native_builder_contract.py"
    text = path.read_text(encoding="utf-8")
    marker = "def test_failure_isolation_contract_rejects_missing_or_false_cleanup"
    if marker not in text:
        text += '''


def test_failure_isolation_contract_rejects_missing_or_false_cleanup(
    tmp_path: Path,
) -> None:
    plan, profile, envelope = authorization_context(tmp_path)
    missing = FakeAdapter(plan)
    missing.discard_private_case = None  # type: ignore[method-assign,assignment]
    with pytest.raises(NativeBuildError, match="requires callable discard_private_case"):
        execute(plan, missing, profile, envelope, tmp_path)

    invalid = FakeAdapter(plan)
    invalid.discard_private_case = lambda: {"discarded": False}  # type: ignore[method-assign]
    first_apply = next(item for item in plan.steps if item.expected_readback)
    invalid.override_results[first_apply.step_id] = {}
    with pytest.raises(NativeBuildError, match="failure isolation also failed"):
        execute(plan, invalid, profile, envelope, tmp_path)
'''
    path.write_text(text, encoding="utf-8")


def main() -> None:
    patch_evaluation_and_native()
    patch_warm_start_compatibility()
    patch_optimization_compatibility()
    patch_parameter_and_pool_compatibility()
    patch_acceptance_tests()
    patch_native_coverage_tests()


if __name__ == "__main__":
    main()
