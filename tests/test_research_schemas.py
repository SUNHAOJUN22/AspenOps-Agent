from __future__ import annotations

import json
from pathlib import Path

from aspenops_nexus.research import RESEARCH_SCHEMA, ResearchStudyDocument

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src" / "aspenops_nexus" / "data"
EXAMPLE = ROOT / "examples" / "research-study.example.json"

EXPECTED = {
    "research-common.schema.json",
    "research-study.schema.json",
    "research-dataset.schema.json",
    "research-target.schema.json",
    "research-parameter.schema.json",
    "research-assumption.schema.json",
    "research-calibration.schema.json",
    "research-validation.schema.json",
    "research-claim.schema.json",
}


def test_research_schema_inventory_is_complete_and_strict() -> None:
    paths = sorted(DATA.glob("research-*.schema.json"))

    assert {path.name for path in paths} == EXPECTED
    ids = set()
    for path in paths:
        schema = json.loads(path.read_text(encoding="utf-8"))
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["$id"].startswith("https://schemas.aspenops.dev/research/v1/")
        assert schema["$id"] not in ids
        ids.add(schema["$id"])
        assert schema["type"] == "object"
        if path.name != "research-common.schema.json":
            assert schema["additionalProperties"] is False
            assert schema["required"]
            assert schema["properties"]


def test_common_schema_defines_immutable_refs_and_claim_maturity() -> None:
    schema = json.loads(
        (DATA / "research-common.schema.json").read_text(encoding="utf-8")
    )
    definitions = schema["$defs"]

    assert {
        "safeId",
        "sha256",
        "maturity",
        "objectRef",
        "artifactRef",
        "semanticBinding",
        "sourceRef",
    } <= set(definitions)
    assert definitions["artifactRef"]["required"] == ["uri", "sha256"]
    assert "LICENSED_ENGINEERING_REVIEWED" in definitions["maturity"]["enum"]
    assert definitions["semanticBinding"]["properties"]["access"]["enum"] == [
        "read",
        "write",
    ]


def test_synthetic_research_fixture_is_current_and_valid() -> None:
    value = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    document = ResearchStudyDocument.from_dict(value)
    report = document.validate()

    assert value["schema"] == RESEARCH_SCHEMA
    assert report.ok
    assert report.computed_claim_ceiling == "VALIDATED_HELD_OUT"
    assert document.claims[0].claim_sha256 == document.claims[0].computed_sha256()
