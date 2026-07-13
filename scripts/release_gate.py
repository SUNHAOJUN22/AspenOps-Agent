from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def run(name: str, command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    record = {
        "name": name,
        "command": command,
        "returncode": completed.returncode,
        "passed": completed.returncode == 0,
        "output": completed.stdout,
    }
    if completed.returncode != 0:
        raise RuntimeError(json.dumps(record, indent=2))
    return record


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_last_json(text: str) -> Any:
    positions = [match.start() for match in re.finditer(r"(?m)^\{", text)]
    for position in reversed(positions):
        try:
            return json.loads(text[position:])
        except json.JSONDecodeError:
            continue
    return None


def main() -> None:
    records = [
        run("ruff", ["uv", "run", "ruff", "check", "."]),
        run("mypy", ["uv", "run", "mypy", "src"]),
        run(
            "pytest",
            [
                "uv",
                "run",
                "pytest",
                "-W",
                "error::ResourceWarning",
                "--cov=aspenops_nexus",
                "--cov-report=term",
                "--cov-fail-under=60",
            ],
        ),
        run("build", ["uv", "build", "--clear"]),
        run("demo", ["uv", "run", "aspenops", "demo"]),
        run(
            "benchmark",
            ["uv", "run", "aspenops", "benchmark", "--points", "24", "--workers", "1,2,4"],
        ),
        run("mcp_surface", ["uv", "run", "python", "scripts/check_mcp.py"]),
        run(
            "mock_certification",
            [
                "uv",
                "run",
                "aspenops",
                "certify",
                "examples/batch-request.example.json",
                "--output",
                "var/mock-certification-report.json",
                "--repeats",
                "2",
            ],
        ),
    ]
    artifacts = []
    for path in sorted((ROOT / "dist").glob("*")):
        if path.is_file() and path.suffix in {".whl", ".gz"}:
            artifacts.append(
                {
                    "path": str(path.relative_to(ROOT)),
                    "size": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )
    report = {
        "project": "AspenOps",
        "version": "1.0.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "portable_release_gate_passed": all(record["passed"] for record in records),
        "commands": records,
        "benchmark": parse_last_json(
            next(x["output"] for x in records if x["name"] == "benchmark")
        ),
        "mcp": parse_last_json(next(x["output"] for x in records if x["name"] == "mcp_surface")),
        "artifacts": artifacts,
        "real_aspen_certification": (
            "NOT EXECUTED: this environment is Linux and has no licensed Aspen installation or "
            "operator-approved qualification model."
        ),
    }
    output = ROOT / "var" / "release-report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"passed": True, "report": str(output)}, indent=2))


if __name__ == "__main__":
    main()
