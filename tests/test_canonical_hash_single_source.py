from __future__ import annotations

import ast
from pathlib import Path

from aspenops_nexus.hashing import canonical_hash
from aspenops_nexus.process_requirement import ProcessRequirementDocument

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "aspenops_nexus"


def test_canonical_hash_has_one_production_definition() -> None:
    definitions: list[str] = []
    for path in SOURCE.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in {
                "canonical_hash",
                "_canonical_hash",
            }:
                definitions.append(f"{path.name}:{node.name}")
    assert definitions == ["hashing.py:canonical_hash"]


def test_requirement_digest_uses_shared_canonical_contract() -> None:
    import json

    example = ROOT / "examples" / "process-requirement-v1.example.json"
    payload = json.loads(example.read_text(encoding="utf-8"))
    requirement = ProcessRequirementDocument.from_dict(payload)
    assert requirement.digest() == canonical_hash(requirement.to_dict())
