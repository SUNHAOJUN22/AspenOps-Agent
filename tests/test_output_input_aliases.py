from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from test_licensed_certification import key_material, plan_document

from aspenops_nexus import cli
from aspenops_nexus import licensed_certification as licensed
from aspenops_nexus.config import Settings
from aspenops_nexus.policy import PolicyError
from aspenops_nexus.provenance import verify_run_bundle, write_run_bundle


def _request(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    model = tmp_path / "model.json"
    registry = tmp_path / "registry.json"
    model.write_text('{"original_model":true}', encoding="utf-8")
    registry.write_text('{"original_registry":true}', encoding="utf-8")
    document = {"backend": "mock", "model_path": str(model), "registry_path": str(registry)}
    source = tmp_path / "request.json"
    source.write_text(json.dumps(document), encoding="utf-8")
    return source, document


def _alias(source: Path, kind: str, tmp_path: Path) -> Path:
    if kind == "direct":
        return source
    if kind == "dotdot":
        nested = tmp_path / "nested"
        nested.mkdir()
        return nested / ".." / source.name
    alias = tmp_path / "alias-output"
    try:
        if kind == "symlink":
            alias.symlink_to(source)
        else:
            alias.hardlink_to(source)
    except OSError as error:
        pytest.skip(f"{kind} is unavailable: {error}")
    return alias


def _install_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Settings:
    active = Settings(allowed_roots=(tmp_path,), state_dir=tmp_path / "state")
    monkeypatch.setattr(cli.Settings, "from_env", classmethod(lambda cls: active))
    return active


def _unexpected_execution(*args: Any, **kwargs: Any) -> Any:
    pytest.fail("output aliases must be rejected before execution or preflight")


@pytest.mark.parametrize("output_kind", ["output", "bundle"])
@pytest.mark.parametrize("source_kind", ["request", "model_path", "registry_path"])
@pytest.mark.parametrize("alias_kind", ["direct", "dotdot", "symlink", "hardlink"])
def test_batch_rejects_input_aliases_before_execution_or_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output_kind: str,
    source_kind: str,
    alias_kind: str,
) -> None:
    source, document = _request(tmp_path)
    protected = source if source_kind == "request" else Path(document[source_kind])
    target = _alias(protected, alias_kind, tmp_path)
    output = tmp_path / "results.json"
    bundle = tmp_path / "run.zip"
    output.write_bytes(b"existing results")
    bundle.write_bytes(b"existing bundle")
    before = {path: path.read_bytes() for path in (source, protected, output, bundle)}
    _install_settings(monkeypatch, tmp_path)
    monkeypatch.setattr(cli, "run_batch_file", _unexpected_execution)
    arguments = {"request": str(source), "output": str(output), "bundle": str(bundle)}
    arguments[output_kind] = str(target)

    with pytest.raises(PolicyError, match="alias"):
        cli.command_run_batch(Namespace(**arguments))

    assert all(path.read_bytes() == payload for path, payload in before.items())


@pytest.mark.parametrize("alias_kind", ["direct", "dotdot", "symlink", "hardlink"])
def test_batch_rejects_colliding_outputs_before_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, alias_kind: str
) -> None:
    source, _ = _request(tmp_path)
    output = tmp_path / "results.json"
    output.write_bytes(b"existing results")
    bundle = _alias(output, alias_kind, tmp_path)
    _install_settings(monkeypatch, tmp_path)
    monkeypatch.setattr(cli, "run_batch_file", _unexpected_execution)

    with pytest.raises(PolicyError, match="alias"):
        cli.command_run_batch(
            Namespace(request=str(source), output=str(output), bundle=str(bundle))
        )
    assert output.read_bytes() == b"existing results"


@pytest.mark.parametrize("command", ["optimize", "certify", "certification_preflight"])
@pytest.mark.parametrize("source_kind", ["request", "model_path", "registry_path"])
def test_report_commands_reject_input_aliases_before_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str, source_kind: str
) -> None:
    source, document = _request(tmp_path)
    target = source if source_kind == "request" else Path(document[source_kind])
    before = target.read_bytes()
    _install_settings(monkeypatch, tmp_path)
    monkeypatch.setattr(cli, "PoolManager", _unexpected_execution)
    monkeypatch.setattr(cli, "certify_batch_document", _unexpected_execution)
    monkeypatch.setattr(cli, "certification_preflight", _unexpected_execution)
    monkeypatch.setattr(cli, "load_licensed_plan", lambda path: SimpleNamespace(request=document))
    arguments = Namespace(
        request=str(source), plan=str(source), output=str(target), repeats=2, abs_tol=0, rel_tol=0
    )

    with pytest.raises(PolicyError, match="alias"):
        getattr(cli, f"command_{command}")(arguments)
    assert target.read_bytes() == before


@pytest.mark.parametrize("writer", ["run", "licensed"])
@pytest.mark.parametrize("source_kind", ["model_path", "registry_path", "signing_key"])
@pytest.mark.parametrize("alias_kind", ["direct", "dotdot", "symlink", "hardlink"])
def test_bundle_writers_preserve_inputs_and_file_signing_key(
    tmp_path: Path, writer: str, source_kind: str, alias_kind: str
) -> None:
    private_key, _, key_id = key_material(tmp_path)
    plan = licensed.LicensedCertificationPlan.from_document(plan_document(tmp_path, key_id))
    source = private_key if source_kind == "signing_key" else Path(plan.request[source_kind])
    target = _alias(source, alias_kind, tmp_path)
    before = source.read_bytes()

    with pytest.raises(PolicyError, match="alias"):
        if writer == "run":
            write_run_bundle(
                request=plan.request,
                results=[{"ok": True}],
                output_path=target,
                signing_private_key=private_key,
            )
        else:
            licensed.write_licensed_certification_bundle(
                plan=plan,
                preflight={"ready": False},
                report={"executed": False},
                environment={},
                output_path=target,
                signing_private_key=private_key,
            )
    assert source.read_bytes() == before
    assert not list(tmp_path.glob(".*.tmp"))


@pytest.mark.parametrize(
    "output_name",
    ["preflight.json", "licensed-certification-report.json", "licensed-certification-bundle.zip"],
)
def test_licensed_execution_rejects_output_aliases_before_preflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, output_name: str
) -> None:
    private_key, _, key_id = key_material(tmp_path)
    plan = licensed.LicensedCertificationPlan.from_document(plan_document(tmp_path, key_id))
    output = tmp_path / "outputs"
    output.mkdir()
    model = Path(plan.request["model_path"])
    (output / output_name).hardlink_to(model)
    before = model.read_bytes()
    monkeypatch.setattr(licensed, "certification_preflight", _unexpected_execution)

    with pytest.raises(PolicyError, match="alias"):
        licensed.execute_licensed_certification(
            plan,
            Settings(allowed_roots=(tmp_path,), state_dir=tmp_path / "state"),
            output_dir=output,
            environment={"ASPENOPS_CERT_SIGNING_KEY": str(private_key)},
        )
    assert model.read_bytes() == before
    assert sorted(path.name for path in output.iterdir()) == [output_name]


def test_licensed_cli_protects_the_plan_file_before_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_key, _, key_id = key_material(tmp_path)
    document = plan_document(tmp_path, key_id)
    source = tmp_path / "preflight.json"
    source.write_text(json.dumps(document), encoding="utf-8")
    before = source.read_bytes()
    _install_settings(monkeypatch, tmp_path)
    monkeypatch.setattr(cli, "execute_licensed_certification", _unexpected_execution)

    with pytest.raises(PolicyError, match="alias"):
        cli.command_certify_licensed(Namespace(plan=str(source), output_dir=str(tmp_path)))
    assert source.read_bytes() == before


def test_batch_separate_outputs_preserve_relative_source_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, document = _request(tmp_path)
    document["model_path"] = "model.json"
    document["registry_path"] = "registry.json"
    source.write_text(json.dumps(document), encoding="utf-8")
    before = {path: path.read_bytes() for path in (source, tmp_path / "model.json")}
    monkeypatch.chdir(tmp_path)
    _install_settings(monkeypatch, tmp_path)
    monkeypatch.setattr(cli, "run_batch_file", lambda *args: [{"ok": True}])
    output = tmp_path / "results.json"
    bundle = tmp_path / "run.zip"

    assert cli.command_run_batch(Namespace(request=str(source), output=output, bundle=bundle)) == 0
    assert json.loads(output.read_text(encoding="utf-8")) == [{"ok": True}]
    assert verify_run_bundle(bundle)["ok"] is True
    assert all(path.read_bytes() == payload for path, payload in before.items())
