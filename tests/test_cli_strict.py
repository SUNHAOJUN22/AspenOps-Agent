import json
from importlib.resources import as_file, files
from pathlib import Path

import pytest

from aspenops_nexus.cli import build_parser, main
from aspenops_nexus.scheduler import JobStore


def resource(name: str) -> Path:
    with as_file(files("aspenops_nexus.data").joinpath(name)) as path:
        return Path(path)


def request() -> dict:
    return {
        "backend": "mock",
        "model_path": str(resource("mock-case.json")),
        "registry_path": str(resource("node-registry.json")),
        "points": [{}],
        "reads": [
            {
                "key": "stream.output.purity",
                "identifiers": {"stream": "PRODUCT"},
                "unit": "fraction",
            }
        ],
        "timeout_s": 5,
    }


def invoke(argv: list[str]) -> int:
    with pytest.raises(SystemExit) as captured:
        main(argv)
    return int(captured.value.code)


def configure_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    state = tmp_path / "state"
    monkeypatch.setenv("ASPENOPS_STATE_DIR", str(state))
    monkeypatch.setenv("ASPENOPS_LICENSE_SLOTS", "1")
    monkeypatch.setenv("ASPENOPS_MAX_WORKERS", "1")
    monkeypatch.delenv("ASPENOPS_ALLOWED_ROOTS", raising=False)
    return state


def write_request(tmp_path: Path, value: dict | None = None) -> Path:
    path = tmp_path / "request.json"
    path.write_text(json.dumps(request() if value is None else value), encoding="utf-8")
    return path


def test_parser_exposes_persistent_submit_and_scheduler_service() -> None:
    parser = build_parser()
    assert parser.parse_args(["submit", "request.json"]).command == "submit"
    assert parser.parse_args(["scheduler"]).command == "scheduler"


def test_cli_reports_stable_validation_errors_for_invalid_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_state(monkeypatch, tmp_path)
    path = tmp_path / "invalid.json"
    path.write_text('{"x": 1, "x": 2}', encoding="utf-8")
    assert invoke(["dry-run", str(path)]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert payload["error"]["retryable"] is False


def test_submit_persists_pending_job_without_ephemeral_scheduler_thread(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    state = configure_state(monkeypatch, tmp_path)
    request_path = write_request(tmp_path)
    assert invoke(["submit", str(request_path), "--idempotency-key", "case-1"]) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["status"] == "pending"
    assert first["scheduler_required"] is True

    store = JobStore(state / "jobs.sqlite3")
    record = store.get(first["job_id"])
    assert record is not None
    assert record["status"] == "pending"

    assert invoke(["submit", str(request_path), "--idempotency-key", "case-1"]) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["job_id"] == first["job_id"]


def test_job_command_reads_store_without_starting_scheduler(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    state = configure_state(monkeypatch, tmp_path)
    store = JobStore(state / "jobs.sqlite3")
    job_id = store.create(request())
    assert invoke(["job", job_id]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["found"] is True
    assert payload["job"]["status"] == "pending"


def test_run_batch_publishes_atomic_results_and_immutable_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_state(monkeypatch, tmp_path)
    request_path = write_request(tmp_path)
    results = tmp_path / "results.json"
    bundle = tmp_path / "evidence.zip"
    assert (
        invoke(
            [
                "run-batch",
                str(request_path),
                "--output",
                str(results),
                "--bundle",
                str(bundle),
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["results_path"] == str(results.resolve())
    assert payload["bundle_path"] == str(bundle.resolve())
    assert json.loads(results.read_text(encoding="utf-8"))[0]["ok"] is True
    assert bundle.is_file()
    assert bundle.with_suffix(".zip.sha256").is_file()
    assert not list(tmp_path.glob("*.tmp"))


def test_benchmark_rejects_duplicate_or_over_capacity_workers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_state(monkeypatch, tmp_path)
    assert invoke(["benchmark", "--workers", "1,1"]) == 1
    duplicate = json.loads(capsys.readouterr().out)
    assert duplicate["error"]["code"] == "VALIDATION_ERROR"

    assert invoke(["benchmark", "--workers", "2"]) == 1
    capacity = json.loads(capsys.readouterr().out)
    assert capacity["error"]["code"] == "VALIDATION_ERROR"
