from __future__ import annotations

import argparse
import json
from pathlib import Path

from aspenops_nexus.design_validation import validate_design_files


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a ProcessRequirementDocument and ProcessDesignIR v2 without opening a "
            "simulator."
        )
    )
    parser.add_argument("requirement")
    parser.add_argument("design")
    parser.add_argument("--report-output")
    parser.add_argument("--graph-output")
    parser.add_argument("--svg-output")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = validate_design_files(args.requirement, args.design)
    if args.report_output:
        path = Path(args.report_output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    preview = report.get("preview")
    if isinstance(preview, dict):
        if args.graph_output:
            path = Path(args.graph_output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(preview["graph"], indent=2, ensure_ascii=False, allow_nan=False)
                + "\n",
                encoding="utf-8",
            )
        if args.svg_output:
            path = Path(args.svg_output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(str(preview["svg"]), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))
    return 0 if report["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
