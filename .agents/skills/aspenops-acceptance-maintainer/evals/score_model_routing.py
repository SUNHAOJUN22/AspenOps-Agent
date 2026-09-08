#!/usr/bin/env python3
"""Score externally captured model-routing decisions against this skill's evals.

This script never invokes a model. Capture model events separately (for example
with an authenticated ``codex exec --json`` run), normalize each decision to
``{"id": "...", "selected_skills": ["..."]}``, and pass the JSON or JSONL
file here. A PASS requires one decision for every case and exact activation
agreement. Static fixtures are not model-routing evidence.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


class ContractError(ValueError):
    pass


def pairs(items):
    out = {}
    for k, v in items:
        if k in out:
            raise ContractError(f"duplicate JSON key: {k}")
        out[k] = v
    return out


def load_json_text(text: str) -> Any:
    return json.loads(
        text,
        object_pairs_hook=pairs,
        parse_constant=lambda x: (_ for _ in ()).throw(
            ContractError(f"non-standard JSON constant: {x}")
        ),
    )


def load_decisions(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    stripped = text.lstrip()
    if stripped.startswith("["):
        value = load_json_text(text)
        if not isinstance(value, list):
            raise ContractError("decision input must be a list or JSONL")
        return value
    rows = []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        value = load_json_text(line)
        if not isinstance(value, dict):
            raise ContractError(f"line {number} must be an object")
        rows.append(value)
    return rows


def score(eval_path: Path, decision_path: Path) -> dict[str, Any]:
    spec = load_json_text(eval_path.read_text(encoding="utf-8"))
    rows = load_decisions(decision_path)
    cases = {c["id"]: c for c in spec["cases"]}
    seen = {}
    errors = []
    for row in rows:
        if not isinstance(row, dict):
            errors.append("decision must be an object")
            continue
        cid = row.get("id")
        if not isinstance(cid, str) or cid not in cases:
            errors.append(f"unknown decision id: {cid!r}")
            continue
        if cid in seen:
            errors.append(f"duplicate decision id: {cid}")
            continue
        selected = row.get("selected_skills")
        if not isinstance(selected, list) or any(not isinstance(x, str) for x in selected):
            errors.append(f"{cid}: selected_skills must be a string list")
            continue
        seen[cid] = row
    missing = sorted(set(cases) - set(seen))
    unexpected = sorted(set(seen) - set(cases))
    results = []
    for cid, case in cases.items():
        row = seen.get(cid)
        if row is None:
            continue
        selected = set(row["selected_skills"])
        actual = "ACTIVATE" if spec["skill_name"] in selected else "DO_NOT_ACTIVATE"
        passed = actual == case["expected_activation"]
        results.append(
            {
                "id": cid,
                "split": case["split"],
                "expected": case["expected_activation"],
                "actual": actual,
                "passed": passed,
            }
        )
    by_split = {}
    for split in ("train", "validation"):
        subset = [r for r in results if r["split"] == split]
        by_split[split] = {
            "scored": len(subset),
            "passed": sum(1 for r in subset if r["passed"]),
            "accuracy": (sum(1 for r in subset if r["passed"]) / len(subset) if subset else None),
        }
    complete = not missing and not unexpected and len(seen) == len(cases)
    all_pass = complete and not errors and all(r["passed"] for r in results)
    return {
        "schema_version": "agent-skill-model-routing-score.v11",
        "skill_name": spec["skill_name"],
        "evidence_scope": "EXTERNALLY_CAPTURED_MODEL_DECISIONS",
        "decision_file": str(decision_path),
        "complete": complete,
        "case_count": len(cases),
        "scored": len(results),
        "missing": missing,
        "unexpected": unexpected,
        "errors": errors,
        "by_split": by_split,
        "results": results,
        "status": "PASS" if all_pass else "FAIL",
    }


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("decisions", type=Path)
    p.add_argument("--evals", type=Path, default=Path(__file__).with_name("evals.json"))
    p.add_argument("--report", type=Path)
    ns = p.parse_args(argv)
    try:
        receipt = score(ns.evals, ns.decisions)
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ContractError,
        KeyError,
        TypeError,
    ) as exc:
        receipt = {
            "schema_version": "agent-skill-model-routing-score.v11",
            "status": "FAIL",
            "errors": [str(exc)],
        }
    text = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if ns.report:
        ns.report.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0 if receipt.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
