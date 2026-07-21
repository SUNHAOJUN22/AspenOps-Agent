from __future__ import annotations

from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"Expected runtime-scope marker missing: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    module = Path("src/aspenops_nexus/licensed_certification.py")
    test = Path("tests/test_licensed_certification.py")

    replace_once(
        module,
        '''def _unique_texts(value: Any, label: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    items = tuple(_text(item, f"{label} item") for item in _array(value, label))
    if not items and not allow_empty:
        raise ValueError(f"{label} must contain at least one item")
    normalized = [item.casefold() for item in items]
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{label} must contain unique values")
    return items
''',
        '''def _unique_texts(value: Any, label: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    items = tuple(_text(item, f"{label} item") for item in _array(value, label))
    if not items and not allow_empty:
        raise ValueError(f"{label} must contain at least one item")
    normalized = [item.casefold() for item in items]
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{label} must contain unique values")
    return items


def _scoped_texts(value: Any, label: str) -> tuple[str, ...]:
    items = _unique_texts(value, label)
    if any("*" in item or "?" in item for item in items):
        raise ValueError(f"{label} cannot contain wildcard characters")
    return items


def _version_patterns(value: Any) -> tuple[str, ...]:
    patterns = _unique_texts(
        value,
        "runtime_expectation.version_patterns",
        allow_empty=True,
    )
    for pattern in patterns:
        if not pattern.startswith("^") or ".*" in pattern:
            raise ValueError(
                "runtime_expectation.version_patterns must be anchored and cannot contain .*"
            )
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError(
                f"Invalid runtime version pattern {pattern!r}: {exc}"
            ) from exc
    return patterns
''',
    )
    replace_once(
        module,
        '''        return cls(
            case_id=_text(mapping.get("case_id"), "case_id"),
''',
        '''        repeatability = RepeatabilityPlan.from_document(mapping.get("repeatability"))
        license_slots = _positive_integer(
            license_expectation.get("slots"),
            "license_expectation.slots",
            maximum=64,
        )
        if max(repeatability.workers) > license_slots:
            raise ValueError(
                "repeatability.workers cannot exceed approved license_expectation.slots"
            )

        return cls(
            case_id=_text(mapping.get("case_id"), "case_id"),
''',
    )
    replace_once(
        module,
        '            repeatability=RepeatabilityPlan.from_document(mapping.get("repeatability")),\n',
        '            repeatability=repeatability,\n',
    )
    replace_once(
        module,
        '''            progids=_unique_texts(runtime.get("progids"), "runtime_expectation.progids"),
            version_patterns=_unique_texts(
                runtime.get("version_patterns", []),
                "runtime_expectation.version_patterns",
                allow_empty=True,
            ),
            license_slots=_positive_integer(
                license_expectation.get("slots"), "license_expectation.slots", maximum=64
            ),
''',
        '''            progids=_scoped_texts(
                runtime.get("progids"), "runtime_expectation.progids"
            ),
            version_patterns=_version_patterns(runtime.get("version_patterns", [])),
            license_slots=license_slots,
''',
    )
    replace_once(
        module,
        '''            feature_names=_unique_texts(
                license_expectation.get("feature_names"),
                "license_expectation.feature_names",
            ),
            runner_names=_unique_texts(runner.get("names"), "runner_expectation.names"),
''',
        '''            feature_names=_scoped_texts(
                license_expectation.get("feature_names"),
                "license_expectation.feature_names",
            ),
            runner_names=_scoped_texts(
                runner.get("names"), "runner_expectation.names"
            ),
''',
    )
    replace_once(
        module,
        '''def execute_licensed_certification(
    plan: LicensedCertificationPlan,
''',
        '''def _runtime_scope_evidence(
    plan: LicensedCertificationPlan,
    reports: list[dict[str, Any]],
) -> dict[str, Any]:
    approved_progids = {item.casefold() for item in plan.progids}
    compiled_patterns = [re.compile(pattern) for pattern in plan.version_patterns]
    identities: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []
    for report_index, report in enumerate(reports):
        runs = report.get("runs", [])
        if not isinstance(runs, list):
            violations.append(
                {"report": report_index, "code": "runtime_runs_missing"}
            )
            continue
        for repeat_index, run in enumerate(runs):
            if not isinstance(run, list):
                violations.append(
                    {
                        "report": report_index,
                        "repeat": repeat_index,
                        "code": "runtime_run_malformed",
                    }
                )
                continue
            for point_index, result in enumerate(run):
                if not isinstance(result, dict):
                    violations.append(
                        {
                            "report": report_index,
                            "repeat": repeat_index,
                            "point": point_index,
                            "code": "runtime_result_malformed",
                        }
                    )
                    continue
                diagnostics = result.get("diagnostics", {})
                runtime = diagnostics.get("runtime") if isinstance(diagnostics, dict) else None
                if not isinstance(runtime, dict):
                    violations.append(
                        {
                            "report": report_index,
                            "repeat": repeat_index,
                            "point": point_index,
                            "code": "runtime_identity_missing",
                        }
                    )
                    continue
                progid = str(runtime.get("progid") or "")
                exposed = runtime.get("exposed", {})
                exposed_values = (
                    [str(value) for value in exposed.values()]
                    if isinstance(exposed, dict)
                    else []
                )
                identity = {
                    "report": report_index,
                    "repeat": repeat_index,
                    "point": point_index,
                    "progid": progid,
                    "exposed": exposed_values,
                }
                identities.append(identity)
                if progid.casefold() not in approved_progids:
                    violations.append({**identity, "code": "runtime_progid_out_of_scope"})
                if compiled_patterns and not any(
                    pattern.search(value)
                    for pattern in compiled_patterns
                    for value in exposed_values
                ):
                    violations.append({**identity, "code": "runtime_version_out_of_scope"})
    if not identities:
        violations.append({"code": "no_runtime_identity_evidence"})
    return {
        "passed": not violations,
        "identities": identities,
        "violations": violations,
        "approved_progids": list(plan.progids),
        "approved_version_patterns": list(plan.version_patterns),
    }


def execute_licensed_certification(
    plan: LicensedCertificationPlan,
''',
    )
    replace_once(
        module,
        '''    runtime_gate_passed = all(bool(item.get("repeatability_gate_passed")) for item in reports)
    report = {
''',
        '''    repeatability_gate_passed = all(
        bool(item.get("repeatability_gate_passed")) for item in reports
    )
    runtime_scope = _runtime_scope_evidence(plan, reports)
    runtime_gate_passed = repeatability_gate_passed and bool(runtime_scope["passed"])
    report = {
''',
    )
    replace_once(
        module,
        '        "runtime_gate_passed": runtime_gate_passed,\n',
        '        "repeatability_gate_passed": repeatability_gate_passed,\n        "runtime_scope": runtime_scope,\n        "runtime_gate_passed": runtime_gate_passed,\n',
    )
    replace_once(
        test,
        '''        "runs": [[{"ok": True}]],
''',
        '''        "runs": [
            [
                {
                    "ok": True,
                    "diagnostics": {
                        "runtime": {
                            "progid": "Apwn.Document.40.0",
                            "exposed": {"Version": "40.1"},
                        }
                    },
                }
            ]
        ],
''',
    )
    replace_once(
        test,
        '''def test_output_directory_must_remain_in_approved_roots(
''',
        '''def test_plan_rejects_worker_counts_above_approved_license_slots(
    tmp_path: Path,
) -> None:
    _, _, key_id = key_material(tmp_path)
    document = plan_document(tmp_path, key_id)
    document["repeatability"]["workers"] = [1, 3]
    document["license_expectation"]["slots"] = 2

    with pytest.raises(ValueError, match="cannot exceed approved license"):
        LicensedCertificationPlan.from_document(document)


@pytest.mark.parametrize(
    ("section", "field"),
    [
        ("runtime_expectation", "progids"),
        ("license_expectation", "feature_names"),
        ("runner_expectation", "names"),
    ],
)
def test_plan_rejects_wildcard_approval_scopes(
    tmp_path: Path,
    section: str,
    field: str,
) -> None:
    _, _, key_id = key_material(tmp_path)
    document = plan_document(tmp_path, key_id)
    document[section][field] = ["*"]

    with pytest.raises(ValueError, match="wildcard"):
        LicensedCertificationPlan.from_document(document)


@pytest.mark.parametrize("pattern", ["40\\..*", ".*", "[invalid"])
def test_plan_rejects_broad_or_invalid_version_patterns(
    tmp_path: Path,
    pattern: str,
) -> None:
    _, _, key_id = key_material(tmp_path)
    document = plan_document(tmp_path, key_id)
    document["runtime_expectation"]["version_patterns"] = [pattern]

    with pytest.raises(ValueError, match="pattern|anchored"):
        LicensedCertificationPlan.from_document(document)


def test_out_of_scope_runtime_identity_fails_runtime_gate_but_stays_pending(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, configured, env, _ = valid_preflight(tmp_path, monkeypatch)

    def mismatched_runtime(
        request: dict[str, Any],
        active_settings: Settings,
        **kwargs: Any,
    ) -> dict[str, Any]:
        report = execution_report(kwargs["workers"])
        runtime = report["runs"][0][0]["diagnostics"]["runtime"]
        runtime["progid"] = "Apwn.Document.999.0"
        return report

    monkeypatch.setattr(licensed, "certify_batch_document", mismatched_runtime)
    report = execute_licensed_certification(
        plan,
        configured,
        output_dir=configured.state_dir / "out-of-scope",
        environment=env,
    )

    assert report["repeatability_gate_passed"] is True
    assert report["runtime_gate_passed"] is False
    assert report["certification_status"] == PENDING_REAL_ASPEN_CERTIFICATION
    assert "runtime_progid_out_of_scope" in {
        item["code"] for item in report["runtime_scope"]["violations"]
    }


def test_output_directory_must_remain_in_approved_roots(
''',
    )


if __name__ == "__main__":
    main()
