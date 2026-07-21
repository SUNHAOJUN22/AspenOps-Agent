from __future__ import annotations

from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"Expected runtime identity marker missing: {old[:140]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    module = Path("src/aspenops_nexus/licensed_certification.py")
    test = Path("tests/test_licensed_certification.py")

    replace_once(
        module,
        '''                diagnostics = result.get("diagnostics", {})
                runtime = diagnostics.get("runtime") if isinstance(diagnostics, dict) else None
                if not isinstance(runtime, dict):
''',
        '''                diagnostics = result.get("diagnostics", {})
                worker = (
                    diagnostics.get("worker")
                    if isinstance(diagnostics, dict)
                    else None
                )
                runtime = worker.get("runtime") if isinstance(worker, dict) else None
                if not isinstance(runtime, dict):
''',
    )
    replace_once(
        test,
        '''                    "diagnostics": {
                        "runtime": {
                            "progid": "Apwn.Document.40.0",
                            "exposed": {"Version": "40.1"},
                        }
                    },
''',
        '''                    "diagnostics": {
                        "worker": {
                            "runtime": {
                                "progid": "Apwn.Document.40.0",
                                "exposed": {"Version": "40.1"},
                            }
                        }
                    },
''',
    )
    replace_once(
        test,
        '''        runtime = report["runs"][0][0]["diagnostics"]["runtime"]
        runtime["progid"] = "Apwn.Document.999.0"
''',
        '''        runtime = report["runs"][0][0]["diagnostics"]["worker"]["runtime"]
        runtime["progid"] = "Apwn.Document.999.0"
''',
    )
    replace_once(
        test,
        '''def test_output_directory_must_remain_in_approved_roots(
''',
        '''def test_direct_runtime_field_cannot_forge_worker_protocol_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, configured, env, _ = valid_preflight(tmp_path, monkeypatch)

    def forged_runtime(
        request: dict[str, Any],
        active_settings: Settings,
        **kwargs: Any,
    ) -> dict[str, Any]:
        report = execution_report(kwargs["workers"])
        worker_runtime = report["runs"][0][0]["diagnostics"].pop("worker")
        report["runs"][0][0]["diagnostics"]["runtime"] = worker_runtime["runtime"]
        return report

    monkeypatch.setattr(licensed, "certify_batch_document", forged_runtime)
    report = execute_licensed_certification(
        plan,
        configured,
        output_dir=configured.state_dir / "forged-runtime",
        environment=env,
    )

    assert report["runtime_gate_passed"] is False
    assert "runtime_identity_missing" in {
        item["code"] for item in report["runtime_scope"]["violations"]
    }


def test_output_directory_must_remain_in_approved_roots(
''',
    )


if __name__ == "__main__":
    main()
