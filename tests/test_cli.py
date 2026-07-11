import json

from typer.testing import CliRunner

from aspenops.cli import app

runner = CliRunner()


def test_version_and_doctor() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "1.0.0"
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["aspenops_version"] == "1.0.0"
    assert payload["registry_nodes"] >= 10


def test_demo() -> None:
    result = runner.invoke(app, ["demo"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["run"]["state"] == "converged"
    assert len(payload["values"]) == 2


def test_registry_and_run_case(tmp_path) -> None:
    result = runner.invoke(app, ["registry"])
    assert result.exit_code == 0
    rows = json.loads(result.stdout)
    assert any(row["key"] == "stream.input.temperature" for row in rows)

    case = tmp_path / "case.json"
    case.write_text("{}", encoding="utf-8")
    result = runner.invoke(app, ["run-case", str(case), "--backend", "mock", "--timeout-s", "10"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["run"]["state"] == "converged"
