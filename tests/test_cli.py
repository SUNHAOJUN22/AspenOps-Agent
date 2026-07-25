from __future__ import annotations

import json
import runpy
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from aspenops_nexus import cli


def make_settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        state_dir=tmp_path / "state",
        license_slots=2,
        max_resident_cases=3,
        pool_idle_timeout_s=4.0,
        worker_max_points=5,
        worker_max_age_s=6.0,
        startup_timeout_s=7.0,
        cache_failures=True,
        job_max_attempts=3,
    )


def use_settings(
    monkeypatch: pytest.MonkeyPatch,
    settings: SimpleNamespace,
) -> None:
    monkeypatch.setattr(
        cli.Settings,
        "from_env",
        classmethod(lambda cls: settings),
    )


def test_json_helpers_and_request_loader(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli._json_print({"path": Path("demo"), "ok": True})
    assert json.loads(capsys.readouterr().out) == {"path": "demo", "ok": True}

    path = tmp_path / "request.json"
    path.write_text('{"backend": "mock"}', encoding="utf-8")
    assert cli._load(path) == {"backend": "mock"}
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        cli._load(path)


def test_demo_doctor_and_dry_run_commands(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings(tmp_path)
    use_settings(monkeypatch, settings)
    printed: list[Any] = []
    monkeypatch.setattr(cli, "_json_print", printed.append)

    captured: dict[str, Any] = {}

    def run_demo(request: dict[str, Any], active: Any) -> list[dict[str, Any]]:
        captured.update(request=request, settings=active)
        return [{"ok": True}]

    monkeypatch.setattr(cli, "run_batch_document", run_demo)
    assert cli.command_demo(Namespace()) == 0
    assert captured["request"]["backend"] == "mock"
    assert captured["settings"] is settings
    monkeypatch.setattr(cli, "run_batch_document", lambda request, active: [{"ok": False}])
    assert cli.command_demo(Namespace()) == 2

    monkeypatch.setattr(cli, "diagnose", lambda active, probe: {"ready": probe})
    assert cli.command_doctor(Namespace(probe=True)) == 0
    assert cli.command_doctor(Namespace(probe=False)) == 2

    request_path = tmp_path / "dry-run.json"
    request_path.write_text('{"backend": "mock"}', encoding="utf-8")
    monkeypatch.setattr(
        cli,
        "dry_run_document",
        lambda document, active: {
            "document": document,
            "same_settings": active is settings,
        },
    )
    assert cli.command_dry_run(Namespace(request=str(request_path))) == 0
    assert printed[-1]["same_settings"] is True


def test_run_batch_writes_default_and_explicit_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings(tmp_path)
    use_settings(monkeypatch, settings)
    request_path = tmp_path / "batch.json"
    request = {"backend": "mock", "points": []}
    request_path.write_text(json.dumps(request), encoding="utf-8")
    bundles: list[dict[str, Any]] = []
    printed: list[Any] = []
    monkeypatch.setattr(cli, "write_run_bundle", lambda **kwargs: bundles.append(kwargs))
    monkeypatch.setattr(cli, "_json_print", printed.append)

    results = [{"ok": True, "value": 1.0}]
    monkeypatch.setattr(cli, "run_batch_file", lambda path, active: results)
    args = Namespace(request=str(request_path), output=None, bundle=None)
    assert cli.command_run_batch(args) == 0
    default_output = settings.state_dir / "latest-results.json"
    default_bundle = settings.state_dir / "latest-run-bundle.zip"
    assert json.loads(default_output.read_text(encoding="utf-8")) == results
    assert bundles[-1] == {
        "request": request,
        "results": results,
        "output_path": default_bundle,
    }
    assert printed[-1]["results_path"] == str(default_output)

    failed = [{"ok": False}]
    monkeypatch.setattr(cli, "run_batch_file", lambda path, active: failed)
    explicit_output = tmp_path / "nested" / "results.json"
    explicit_bundle = tmp_path / "bundle.zip"
    args = Namespace(
        request=str(request_path),
        output=str(explicit_output),
        bundle=str(explicit_bundle),
    )
    assert cli.command_run_batch(args) == 2
    assert json.loads(explicit_output.read_text(encoding="utf-8")) == failed
    assert bundles[-1]["output_path"] == explicit_bundle


def test_submit_job_scheduler_and_benchmark_commands(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings(tmp_path)
    use_settings(monkeypatch, settings)
    request_path = tmp_path / "submit.json"
    request_path.write_text('{"backend": "mock"}', encoding="utf-8")
    printed: list[Any] = []
    monkeypatch.setattr(cli, "_json_print", printed.append)

    validated: list[tuple[dict[str, Any], Any]] = []
    monkeypatch.setattr(
        cli,
        "_validate_scheduled_request",
        lambda request, active: validated.append((request, active)),
    )

    records: dict[str, dict[str, Any]] = {}

    class FakeJobStore:
        def __init__(self, path: Path) -> None:
            self.path = path

        def create(self, request: dict[str, Any], max_attempts: int) -> str:
            assert request == {"backend": "mock"}
            assert max_attempts == 3
            records["job-123"] = {"job_id": "job-123", "status": "pending"}
            return "job-123"

        def get(self, job_id: str) -> dict[str, Any] | None:
            return records.get(job_id)

    monkeypatch.setattr(cli, "JobStore", FakeJobStore)
    assert cli.command_submit(Namespace(request=str(request_path))) == 0
    assert validated == [({"backend": "mock"}, settings)]
    assert printed[-1]["job_id"] == "job-123"
    assert printed[-1]["scheduler_required"] is True
    assert printed[-1]["scheduler_command"] == "uv run aspenops scheduler"

    assert cli.command_job(Namespace(job_id="job-123")) == 0
    assert cli.command_job(Namespace(job_id="missing")) == 2

    service_events: list[str] = []

    class FakeScheduler:
        def __init__(self, active: Any) -> None:
            assert active is settings
            self.owner = "scheduler-test"
            self.store = SimpleNamespace(path=tmp_path / "state" / "jobs.sqlite3")

        def start(self) -> None:
            service_events.append("start")

        def stop(self) -> None:
            service_events.append("stop")

    monkeypatch.setattr(cli, "BackgroundScheduler", FakeScheduler)

    def interrupt_sleep(seconds: float) -> None:
        assert seconds == 0.05
        raise KeyboardInterrupt

    monkeypatch.setattr(cli.time, "sleep", interrupt_sleep)
    with pytest.raises(KeyboardInterrupt):
        cli.command_scheduler(Namespace(idle_wait_s=0.01))
    assert service_events == ["start", "stop"]
    assert printed[-1]["service"] == "scheduler"

    model = tmp_path / "case.json"
    registry = tmp_path / "registry.json"
    model.write_text("{}", encoding="utf-8")
    registry.write_text("{}", encoding="utf-8")
    captured: dict[str, Any] = {}

    def benchmark(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"recommended_workers": 3}

    monkeypatch.setattr(cli, "benchmark_worker_matrix", benchmark)
    args = Namespace(
        points=12,
        workers="1,3",
        model=str(model),
        registry=str(registry),
    )
    assert cli.command_benchmark(args) == 0
    assert captured["worker_candidates"] == [1, 3]
    assert captured["model_path"] == model.resolve()
    assert captured["registry_path"] == registry.resolve()


@pytest.mark.parametrize(
    ("status", "expected"),
    [("completed", 0), ("cancelled", 2)],
)
def test_optimize_command_closes_pool_and_writes_result(
    status: str,
    expected: int,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings(tmp_path)
    use_settings(monkeypatch, settings)
    request_path = tmp_path / "optimization.json"
    request_path.write_text('{"optimization": {}}', encoding="utf-8")
    output = tmp_path / status / "result.json"
    events: list[str] = []

    class FakePoolManager:
        def __init__(self, **kwargs: Any) -> None:
            assert kwargs["license_slots"] == 2

        def __enter__(self) -> FakePoolManager:
            events.append("enter")
            return self

        def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
            events.append("exit")

    def optimize(
        document: dict[str, Any],
        active: Any,
        *,
        pool_manager: Any,
    ) -> dict[str, Any]:
        assert document == {"optimization": {}}
        assert active is settings
        assert isinstance(pool_manager, FakePoolManager)
        return {"status": status, "best": 4.2}

    monkeypatch.setattr(cli, "PoolManager", FakePoolManager)
    monkeypatch.setattr(cli, "run_optimization_document", optimize)
    monkeypatch.setattr(cli, "_json_print", lambda value: None)
    args = Namespace(request=str(request_path), output=str(output))
    assert cli.command_optimize(args) == expected
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == status
    assert events == ["enter", "exit"]


@pytest.mark.parametrize(("passed", "expected"), [(True, 0), (False, 2)])
def test_certify_and_verify_bundle_commands(
    passed: bool,
    expected: int,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings(tmp_path)
    use_settings(monkeypatch, settings)
    request_path = tmp_path / "certify.json"
    request_path.write_text('{"backend": "mock"}', encoding="utf-8")
    output = tmp_path / "reports" / f"{passed}.json"
    captured: dict[str, Any] = {}

    def certify(document: dict[str, Any], active: Any, **kwargs: Any) -> dict[str, Any]:
        assert document == {"backend": "mock"}
        assert active is settings
        captured.update(kwargs)
        return {"passed": passed}

    monkeypatch.setattr(cli, "certify_batch_document", certify)
    monkeypatch.setattr(cli, "_json_print", lambda value: None)
    args = Namespace(
        request=str(request_path),
        output=str(output),
        repeats=4,
        abs_tol=1e-7,
        rel_tol=1e-5,
    )
    assert cli.command_certify(args) == expected
    assert captured == {"repeats": 4, "abs_tol": 1e-7, "rel_tol": 1e-5}
    assert json.loads(output.read_text(encoding="utf-8")) == {"passed": passed}

    monkeypatch.setattr(cli, "verify_run_bundle", lambda path: {"ok": passed})
    assert cli.command_verify_bundle(Namespace(bundle="bundle.zip")) == expected


def test_mcp_parser_and_main_exit_semantics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aspenops_nexus import mcp_server

    calls: list[str] = []
    monkeypatch.setattr(mcp_server, "main", lambda: calls.append("mcp"))
    assert cli.command_mcp(Namespace()) == 0
    assert calls == ["mcp"]

    parser = cli.build_parser()
    commands = [
        ["demo"],
        ["doctor", "--probe"],
        ["dry-run", "request.json"],
        ["run-batch", "request.json"],
        ["submit", "request.json"],
        ["job", "job-1"],
        ["scheduler"],
        ["benchmark"],
        ["optimize", "request.json"],
        ["certify", "request.json"],
        ["verify-bundle", "bundle.zip"],
        ["mcp"],
    ]
    parsed = [parser.parse_args(argv) for argv in commands]
    assert [item.command for item in parsed] == [argv[0] for argv in commands]
    assert parsed[7].workers == "1,2,4"

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
