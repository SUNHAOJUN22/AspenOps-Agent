from __future__ import annotations

import json
import math
import sqlite3
import subprocess
import sys
from collections.abc import Callable
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus import batch, cli, provenance, runtime_qualification
from aspenops_nexus.cache import ResultCache
from aspenops_nexus.config import Settings
from aspenops_nexus.design_validation import load_strict_json_object
from aspenops_nexus.licensed_certification import load_licensed_plan
from aspenops_nexus.registry import NodeRegistry, RegistryError
from aspenops_nexus.research import ResearchStudyDocument, ResearchValidationError

ROOT = Path(__file__).resolve().parents[1]


def readers(path: Path) -> dict[str, Callable[[], Any]]:
    return {
        "request": lambda: cli._load(path),
        "design": lambda: load_strict_json_object(path),
        "bundle": lambda: provenance._strict_json(path.read_bytes()),
        "qualification": lambda: runtime_qualification._strict_json(path.read_bytes()),
    }


@pytest.mark.parametrize("reader", ["request", "design", "bundle", "qualification"])
@pytest.mark.parametrize("token", ["1e-400", "-1e-400", "1e999", "-1e999"])
def test_external_json_rejects_unrepresentable_nonzero_numbers(
    tmp_path: Path, reader: str, token: str
) -> None:
    path = tmp_path / "number.json"
    path.write_text('{"nested":[{"measurement":' + token + "}]}", encoding="utf-8")
    with pytest.raises(ValueError, match="underflow|finite range"):
        readers(path)[reader]()


@pytest.mark.parametrize("reader", ["request", "design", "bundle", "qualification"])
@pytest.mark.parametrize("token", ["0e-9999", "-0.000E-9999", "5e-324", "-5e-324", "1e-300"])
def test_external_json_preserves_true_zero_subnormal_and_integer_values(
    tmp_path: Path, reader: str, token: str
) -> None:
    path = tmp_path / "number.json"
    path.write_text('{"measurement":' + token + ',"count":9007199254740993}', encoding="utf-8")
    value = readers(path)[reader]()
    assert value["measurement"] == float(token)
    assert math.copysign(1, value["measurement"]) == math.copysign(1, float(token))
    assert value["count"] == 9007199254740993
    assert isinstance(value["count"], int)


@pytest.mark.parametrize(
    "payload",
    [
        '{"backend":"aspen_plus","backend":"mock"}',
        '{"nested":{"value":1,"\\u0076alue":2}}',
        '{"value":NaN}',
        '{"value":Infinity}',
        '{"value":1e999}',
        '{"value":1e-400}',
    ],
)
def test_batch_file_rejects_invalid_json_before_backend_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, payload: str
) -> None:
    path = tmp_path / "batch.json"
    path.write_text(payload, encoding="utf-8")
    called: list[dict[str, Any]] = []

    def record(data: dict[str, Any], settings: Settings) -> list[dict[str, Any]]:
        called.append(data)
        return []

    monkeypatch.setattr(batch, "run_batch_document", record)
    with pytest.raises(ValueError, match="Duplicate|non-finite|finite range|underflow"):
        batch.run_batch_file(path, Settings(state_dir=tmp_path / "state"))
    assert not called


@pytest.mark.parametrize("token", ["1e-400", "-1e-400"])
def test_real_dry_run_cli_rejects_underflow_in_a_valid_request(tmp_path: Path, token: str) -> None:
    payload = (ROOT / "examples/batch-request.example.json").read_text(encoding="utf-8")
    payload = payload.replace('"metadata": {', '"metadata": {"measurement":' + token + ",")
    path = tmp_path / "request.json"
    path.write_text(payload, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "aspenops_nexus.cli", "dry-run", str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 1, result.stdout
    response = json.loads(result.stdout)
    assert response["ok"] is False
    assert "underflow" in response["error"]


@pytest.mark.parametrize("token", ["1e-400", "-1e-400"])
def test_corrupt_underflow_cache_rows_cannot_become_successful_hits(
    tmp_path: Path, token: str
) -> None:
    path = tmp_path / "cache.sqlite3"
    cache = ResultCache(path)
    try:
        cache.put("good", {"ok": True, "value": 5e-324})
        with closing(sqlite3.connect(path)) as connection, connection:
            connection.execute(
                "INSERT INTO result_cache(cache_key,payload) VALUES (?,?)",
                ("corrupt", '{"ok":true,"value":' + token + "}"),
            )
        assert cache.get_many(["corrupt", "good"]) == {"good": {"ok": True, "value": 5e-324}}
        assert cache.get("corrupt") is None
        assert "corrupt" not in cache._memory
    finally:
        cache.close()


@pytest.mark.parametrize("token", ["1e-400", "-1e-400"])
def test_registry_bounds_cannot_silently_underflow(tmp_path: Path, token: str) -> None:
    path = tmp_path / "registry.json"
    path.write_text(
        '{"nodes":{"value":{"backend":"mock","access":"read",'
        '"unit":"1","identifiers":[],"paths":["value"],"lower":' + token + "}}}",
        encoding="utf-8",
    )
    with pytest.raises(RegistryError, match="underflow"):
        NodeRegistry(path)


def test_research_file_cannot_override_a_duplicate_schema(tmp_path: Path) -> None:
    payload = (ROOT / "examples/research-study.example.json").read_text(encoding="utf-8")
    path = tmp_path / "study.json"
    path.write_text('{"schema":"invalid",' + payload.lstrip()[1:], encoding="utf-8")
    with pytest.raises(ResearchValidationError, match="Duplicate"):
        ResearchStudyDocument.load(path)


def test_licensed_plan_cannot_override_a_duplicate_case_id(tmp_path: Path) -> None:
    payload = (ROOT / "examples/licensed-certification-plan.example.json").read_text(
        encoding="utf-8"
    )
    path = tmp_path / "plan.json"
    path.write_text('{"case_id":"other-case",' + payload.lstrip()[1:], encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate"):
        load_licensed_plan(path)


def test_process_ir_cli_rejects_underflow_before_canonicalization(tmp_path: Path) -> None:
    payload = (ROOT / "examples/process-intent.example.json").read_text(encoding="utf-8")
    payload = payload.replace(
        '"name": "temperature", "value": 25.0', '"name": "temperature", "value": 1e-400'
    )
    assert "1e-400" in payload
    path = tmp_path / "intent.json"
    path.write_text(payload, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "scripts/validate_process_ir.py", str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode != 0
    assert "underflow" in result.stdout + result.stderr
