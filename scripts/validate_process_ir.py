from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from aspenops_nexus.process_ir import ProcessIntent, validate_process_intent
from aspenops_nexus.simulation_agents import agent_pipeline, capability_matrix


def _load(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Process intent root must be a JSON object")
    return value


def _write(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and normalize simulator-neutral AspenOps process intent IR"
    )
    parser.add_argument("intent", nargs="?", help="Process intent JSON document")
    parser.add_argument("--disallow-recycles", action="store_true")
    parser.add_argument("--canonical-output")
    parser.add_argument("--report-output")
    parser.add_argument("--capabilities-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.capabilities_only:
        print(
            json.dumps(
                {
                    "backends": capability_matrix(),
                    "agent_pipeline": [item.to_dict() for item in agent_pipeline()],
                },
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    if not args.intent:
        raise ValueError("intent is required unless --capabilities-only is used")
    intent = ProcessIntent.from_dict(_load(args.intent))
    report = validate_process_intent(
        intent,
        allow_recycles=not args.disallow_recycles,
    )
    payload = {
        "schema": intent.schema,
        "name": intent.name,
        "report": report.to_dict(),
        "backends": capability_matrix(),
        "agent_pipeline": [item.to_dict() for item in agent_pipeline()],
    }
    if args.canonical_output:
        _write(args.canonical_output, intent.canonical_dict())
        payload["canonical_output"] = str(Path(args.canonical_output))
    if args.report_output:
        _write(args.report_output, payload)
        payload["report_output"] = str(Path(args.report_output))
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0 if report.valid else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            json.dumps(
                {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        raise SystemExit(1) from exc
