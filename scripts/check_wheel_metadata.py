from __future__ import annotations

import argparse
import json
import re
from email.parser import BytesParser
from email.policy import default
from pathlib import Path
from typing import Any
from zipfile import ZipFile

_MCP_REQUIREMENT = re.compile(r"^\s*mcp(?:\s|\[|[<>=!~;]|$)", re.IGNORECASE)


def inspect_wheel(dist_dir: Path) -> dict[str, Any]:
    """Verify the built Wheel carries the supported MCP 1.x extra constraint."""

    wheels = sorted(dist_dir.glob("aspenops_nexus-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(
            f"Expected exactly one AspenOps Wheel in {dist_dir}, found {len(wheels)}"
        )
    wheel = wheels[0]
    with ZipFile(wheel) as archive:
        metadata_names = [
            name
            for name in archive.namelist()
            if name.endswith(".dist-info/METADATA")
        ]
        if len(metadata_names) != 1:
            raise RuntimeError(
                f"Expected exactly one METADATA member in {wheel.name}, "
                f"found {len(metadata_names)}"
            )
        metadata_name = metadata_names[0]
        message = BytesParser(policy=default).parsebytes(archive.read(metadata_name))

    requirements = [str(value) for value in message.get_all("Requires-Dist", [])]
    mcp_requirements = [value for value in requirements if _MCP_REQUIREMENT.match(value)]
    if len(mcp_requirements) != 1:
        raise RuntimeError(
            f"Expected exactly one MCP Requires-Dist entry, found {len(mcp_requirements)}"
        )
    mcp_requirement = mcp_requirements[0]
    compact = mcp_requirement.replace(" ", "").casefold()
    if ">=1.9" not in compact or "<2" not in compact:
        raise RuntimeError(
            "Built Wheel must constrain the MCP Python SDK to mcp>=1.9,<2"
        )
    if "extra=='agent'" not in compact and 'extra=="agent"' not in compact:
        raise RuntimeError("MCP requirement must remain scoped to the agent extra")

    return {
        "ok": True,
        "wheel": wheel.name,
        "metadata_member": metadata_name,
        "mcp_requirement": mcp_requirement,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify AspenOps Wheel dependency metadata",
    )
    parser.add_argument("--dist-dir", type=Path, default=Path("dist"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    report = inspect_wheel(args.dist_dir)
    payload = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
