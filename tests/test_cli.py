from __future__ import annotations

import json
import runpy
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from aspenops_nexus import cli


def settings_for(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        state_dir=tmp_path / "state",
        license_slots=2,
        max_resident_cases=3,
        pool_idle_timeout_s=4.0,
        worker_max_points=5,
        worker_max_age_s=6.0,
        startup_timeout_s=7.0,
        cache_failures=True,
    )


def patch_settings(
    monkeypatch: pytest.MonkeyPatch,
    settings: SimpleNamespace,
) -> None:
    monkeypatch.setattr(
        cli.Settings,
        "from_env",
        classmethod(lambda cls: settings),
    )


def test_json_helpers_and_request_loader(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cli._json_print({"path": Path("demo"), "ok": True})
    rendered = json.loads(capsys.readouterr().out)
    assert rendered == {"path": "demo", "ok": True}

    request_path = tmp_path / "request.json"
    request_path.write_text('{"backend": "mock"}', encoding="utf-8")
    assert cli._load(request_path) == {"backend": "mock"}

    request_path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        cli._load(request_path)


def test_demo_command_reports_success_and_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = settings_for(tmp_path)
    patch_settings(monkeypatch, settings)
    printed: list[Any] = []
    monkeypatch.setattr(cli, "_json_print", printed.append)

    captured: dict[str, Any] = {}

    def run_success(request: dict[str, Any], active_settings: Any) -> list[dict[str, Any]]:
        captured["request"] = request
        captured["settings"] = active_settings
        return [{"ok": True}]

    monkeypatch.setattr(cli, "run_batch_document", run_success)
    assert cli.command_demo(Namespace()) == 0
    assert captured["request"]["backend"] == "mock"
    assert captured["settings"] is settings
    assert printed[-1]["results"] == [{"ok": True}]

    monkeypatch.setattr(cli, "run_batch_document", lambda request, active: [{"ok": False}])
    assert cli.command_demo(Namespace()) == 2


def test_doctor_and_dry_run_commands(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = settings_for(tmp_path)
    patch_settings(monkeypatch, settings)
    printed: list[Any] = []
    monkeypatch.setattr(cli, "_json_print", printed.append)

    monkeypatch.setattr(cli, "diagnose", lambda active, probe: {"ready": probe})
    assert cli.command_doctor(Namespace(probe=True)) == 0
    assert cli.command_doctor(Namespace(probe=False)) == 2

    request_path = tmp_path / "dry-run.json"
    request_path.write_text('{"backend": "mock"}', encoding="utf-8")
    monkeypatch.setattr(
        cli,
        "dry_run_document",
        lambda document, active: {"document": document, "same_settings": active is settings},
    )
    assert cli.command_dry_run(Namespace(request=str(request_path))) == 0
    assert printed[-1] == {
        "document": {"backend": "mock"},
        "same_settings": True,
    }


def test_run_batch_writes_default_outputs_and_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = settings_for(tmp_path)
    patch_settings(monkeypatch, settings)
    request_path = tmp_path / "batch.json"
    request = {"backend": "mock", "points": []}
    request_path.write_text(json.dumps(request), encoding="utf-8")
    results = [{"ok": True, "value": 1.0}]
    monkeypatch.setattr(cli, "run_batch_file", lambda path, active: results)

    bundles: list[dict[str, Any]] = []
    monkeypatch.setattr(cli, "write_run_bundle", lambda **kwargs: bundles.append(kwargs))
    printed: list[Any] = []
    monkeypatch.setattr(cli, "_json_print", printed.append)

    assert cli.command_run_batch(
        Namespace(request=str(request_path), output=None, bundle=None)
    ) == 0
    output = settings.state_dir / "latest-results.json"
    bundle = settings.state_dir / "latest-run-bundle.zip"
    assert json.loads(output.read_text(encoding="utf-8")) == results
    assert bundles == [{"request": request, "results": results, "output_path": bundle}]
    assert printed[-1]["results_path"] == str(output)
    assert printed[-1]["bundle_path"] == str(bundle)


def test_run_batch_uses_explicit_paths_and_propagates_failure_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = settings_for(tmp_path)
    patch_settings(monkeypatch, settings)
    request_path = tmp_path / "batch.json"
    request_path.write_text('{"backend": "mock"}', encoding="utf-8")
    results = [{"ok": False}]
    monkeypatch.setattr(cli, "run_batch_file", lambda path, active: results)
    bundles: list[dict[str, Any]] = []
    monkeypatch.setattr(cli, "write_run_bundle", lambda **kwargs: bundles.append(kwargs))
    monkeypatch.setattr(cli, "_json_print", lambda value: None)

    output = tmp_path / "nested" / "results.json"
    bundle = tmp_path / "bundles" / "evidence.zip"
    assert cli.command_run_batch(
        Namespace(request=str(request_path), output=str(output), bundle=str(bundle))
    ) == 2
    assert json.loads(output.read_text(encoding="utf-8")) == results
    assert bundles[0]["output_path"] == bundle


def test_submit_and_job_commands(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = settings_for(tmp_path)
    patch_settings(monkeypatch, settings)
    request_path = tmp_path / "submit.json"
    request_path.write_text('{"backend": "mock"}', encoding="utf-8")
    printed: list[Any] = []
    monkeypatch.setattr(cli, "_json_print", printed.append)

    class SubmitScheduler:
        def __init__(self, active_settings: Any) -> None:
            assert active_settings is settings
            self.store = SimpleNamespace(path=tmp_path / "jobs.sqlite3")

        def submit(self, request: dict[str, Any]) -> str:
            assert request == {"backend": "mock"}
            return "job-123"

    monkeypatch.setattr(cli, "BackgroundScheduler", SubmitScheduler)
    assert cli.command_submit(Namespace(request=str(request_path))) == 0
    assert printed[-1] == {
        "job_id": "job-123",
        "state_db": str(tmp_path / "jobs.sqlite3"),
    }

    class JobScheduler:
        def __init__(self, active_settings: Any) -> None:
            assert active_settings is settings
            self.store = SimpleNamespace(
                get=lambda job_id: {"id": job_id} if job_id == "present" else None
            )

    monkeypatch.setattr(cli, "BackgroundScheduler", JobScheduler)
    assert cli.command_job(Namespace(job_id="present")) == 0
    assert printed[-1]["found"] is True
    assert cli.command_job(Namespace(job_id="missing")) == 2
    assert printed[-1] == {"found": False, "job": None}


def test_benchmark_command_normalizes_paths_and_worker_candidates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = settings_for(tmp_path)
    patch_settings(monkeypatch, settings)
    model = tmp_path / "case.json"
    registry = tmp_path / "registry.json"
    model.write_text("{}", encoding="utf-8")
    registry.write_text("{}", encoding="utf-8")
    captured: dict[str, Any] = {}

    def benchmark(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"recommended_workers": 3}

    monkeypatch.setattr(cli, "benchmark_worker_matrix", benchmark)
    printed: list[Any] = []
    monkeypatch.setattr(cli, "_json_print", printed.append)

    assert cli.command_benchmark(
        Namespace(points=12, workers="1,3", model=str(model), registry=str(registry))
    ) == 0
    assert captured == {
        "model_path": model.resolve(),
        "registry_path": registry.resolve(),
        "points": 12,
        "worker_candidates": [1, 3],
        "state_dir": settings.state_dir,
    }
    assert printed[-1] == {"recommended_workers": 3}


def test_optimize_command_closes_pool_and_writes_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = settings_for(tmp_path)
    patch_settings(monkeypatch, settings)
    request_path = tmp_path / "optimization.json"
    request_path.write_text('{"optimization": {}}', encoding="utf-8")
    output = tmp_path / "out" / "optimization-result.json"
    events: list[Any] = []

    class FakePoolManager:
        def __init__(self, **kwargs: Any) -> None:
            events.append(("init", kwargs))

        def __enter__(self) -> FakePoolManager:
            events.append("enter")
            return self

        def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
            events.append("exit")

    monkeypatch.setattr(cli, "PoolManager", FakePoolManager)

    def optimize(document: dict[str, Any], active: Any, *, pool_manager: Any) -> dict[str, Any]:
        assert document == {"optimization": {}}
        assert active is settings
        assert isinstance(pool_manager, FakePoolManager)
        return {"status": "completed", "best": 4.2}

    monkeypatch.setattr(cli, "run_optimization_document", optimize)
    printed: list[Any] = []
    monkeypatch.setattr(cli, "_json_print", printed.append)

    assert cli.command_optimize(
        Namespace(request=str(request_path), output=str(output))
    ) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["best"] == 4.2
    assert events[-1] == "exit"
    assert printed[-1]["result_path"] == str(output.resolve())


def test_optimize_command_returns_failure_for_noncompleted_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = settings_for(tmp_path)
    patch_settings(monkeypatch, settings)
    request_path = tmp_path / "optimization.json"
    request_path.write_text('{"optimization": {}}', encoding="utf-8")

    class FakePoolManager:
        def __init__(self, **kwargs: Any) -> None:
            pass

        def __enter__(self) -> FakePoolManager:
            return self

        def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
            pass

    monkeypatch.setattr(cli, "PoolManager", FakePoolManager)
    monkeypatch.setattr(
        cli,
        "run_optimization_document",
        lambda document, active, pool_manager: {"status": "cancelled"},
    )
    monkeypatch.setattr(cli, "_json_print", lambda value: None)
    assert cli.command_optimize(
        Namespace(request=str(request_path), output=str(tmp_path / "cancelled.json"))
    ) == 2


def test_certify_and_verify_bundle_commands(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = settings_for(tmp_path)
    patch_settings(monkeypatch, settings)
    request_path = tmp_path / "certify.json"
    request_path.write_text('{"backend": "mock"}', encoding="utf-8")
    output = tmp_path / "reports" / "certification.json"
    printed: list[Any] = []
    monkeypatch.setattr(cli, "_json_print", printed.append)

    captured: dict[str, Any] = {}

    def certify(document: dict[str, Any], active: Any, **kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        assert document == {"backend": "mock"}
        assert active is settings
        return {"passed": True}

    monkeypatch.setattr(cli, "certify_batch_document", certify)
    assert cli.command_certify(
        Namespace(
            request=str(request_path),
            output=str(output),
            repeats=4,
            abs_tol=1e-7,
            rel_tol=1e-5,
        )
    ) == 0
    assert captured == {"repeats": 4, "abs_tol": 1e-7, "rel_tol": 1e-5}
    assert json.loads(output.read_text(encoding="utf-8")) == {"passed": True}

    monkeypatch.setattr(cli, "verify_run_bundle", lambda path: {"ok": True, "path": path})
    assert cli.command_verify_bundle(Namespace(bundle="bundle.zip")) == 0
    monkeypatch.setattr(cli, "verify_run_bundle", lambda path: {"ok": False})
    assert cli.command_verify_bundle(Namespace(bundle="bundle.zip")) == 2


def test_certify_command_returns_failure_when_report_does_not_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = settings_for(tmp_path)
    patch_settings(monkeypatch, settings)
    request_path = tmp_path / "certify.json"
    request_path.write_text('{"backend": "mock"}', encoding="utf-8")
    monkeypatch.setattr(
        cli,
        "certify_batch_document",
        lambda document, active, **kwargs: {"passed": False},
    )
    monkeypatch.setattr(cli, "_json_print", lambda value: None)
    assert cli.command_certify(
        Namespace(
            request=str(request_path),
            output=str(tmp_path / "failed.json"),
            repeats=2,
            abs_tol=1e-8,
            rel_tol=1e-6,
        )
    ) == 2


def test_mcp_command_delegates_to_server(monkeypatch: pytest.MonkeyPatch) -> None:
    from aspenops_nexus import mcp_server

    calls: list[str] = []
    monkeypatch.setattr(mcp_server, "main", lambda: calls.append("started"))
    assert cli.command_mcp(Namespace()) == 0
    assert calls == ["started"]


def test_parser_exposes_every_supported_command() -> None:
    parser = cli.build_parser()
    commands = [
        ["demo"],
        ["doctor", "--probe"],
        ["dry-run", "request.json"],
        ["run-batch", "request.json"],
        ["submit", "request.json"],
        ["job", "job-1"],
        ["benchmark"],
        ["optimize", "request.json"],
        ["certify", "request.json"],
        ["verify-bundle", "bundle.zip"],
        ["mcp"],
    ]
    parsed = [parser.parse_args(argv) for argv in commands]
    assert [item.command for item in parsed] == [item[0] for item in commands]
    benchmark = parsed[6]
    assert benchmark.points == 24
    assert benchmark.workers == "1,2,4"


def test_main_maps_success_interrupt_and_exception_to_exit_codes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeParser:
        def __init__(self, func: Any) -> None:
            self.func = func

        def parse_args(self, argv: list[str] | None) -> Namespace:
            return Namespace(func=self.func)

    monkeypatch.setattr(cli, "build_parser", lambda: FakeParser(lambda args: 7))
    with pytest.raises(SystemExit) as success:
        cli.main([])
    assert success.value.code == 7

    def interrupt(args: Namespace) -> int:
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "build_parser", lambda: FakeParser(interrupt))
    with pytest.raises(SystemExit) as interrupted:
        cli.main([])
    assert interrupted.value.code == 130

    printed: list[Any] = []

    def fail(args: Namespace) -> int:
        raise ValueError("boom")

    monkeypatch.setattr(cli, "_json_print", printed.append)
    monkeypatch.setattr(cli, "build_parser", lambda: FakeParser(fail))
    with pytest.raises(SystemExit) as failed:
        cli.main([])
    assert failed.value.code == 1
    assert printed == [{"ok": False, "error": "ValueError: boom"}]


def test_package_main_module_delegates_to_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(cli, "main", lambda argv=None: calls.append("called"))
    runpy.run_module("aspenops_nexus.__main__", run_name="__main__")
    assert calls == ["called"]
