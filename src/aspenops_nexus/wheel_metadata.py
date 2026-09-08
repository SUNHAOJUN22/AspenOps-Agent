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
_MAX_METADATA_BYTES = 256_000
_REQUIRED_SPECIFIERS = {">=1.9", "<2"}


def _validate_mcp_requirement(requirement: str) -> None:
    requirement_part, separator, marker = requirement.partition(";")
    compact_requirement = requirement_part.replace(" ", "").casefold()
    if not compact_requirement.startswith("mcp"):
        raise RuntimeError("MCP Requires-Dist entry has an unexpected package name")

    specifiers = {item for item in compact_requirement.removeprefix("mcp").split(",") if item}
    if not _REQUIRED_SPECIFIERS.issubset(specifiers):
        raise RuntimeError("Built Wheel must constrain the MCP Python SDK to mcp>=1.9,<2")

    compact_marker = marker.replace(" ", "").casefold()
    if not separator or compact_marker not in {"extra=='agent'", 'extra=="agent"'}:
        raise RuntimeError("MCP requirement must remain scoped to the agent extra")


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
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        ]
        if len(metadata_names) != 1:
            raise RuntimeError(
                f"Expected exactly one METADATA member in {wheel.name}, found {len(metadata_names)}"
            )
        metadata_name = metadata_names[0]
        metadata_info = archive.getinfo(metadata_name)
        if metadata_info.file_size > _MAX_METADATA_BYTES:
            raise RuntimeError(
                f"Wheel METADATA exceeds {_MAX_METADATA_BYTES} bytes: {metadata_info.file_size}"
            )
        message = BytesParser(policy=default).parsebytes(archive.read(metadata_name))

    requirements = [str(value) for value in message.get_all("Requires-Dist", [])]
    mcp_requirements = [value for value in requirements if _MCP_REQUIREMENT.match(value)]
    if len(mcp_requirements) != 1:
        raise RuntimeError(
            f"Expected exactly one MCP Requires-Dist entry, found {len(mcp_requirements)}"
        )
    mcp_requirement = mcp_requirements[0]
    _validate_mcp_requirement(mcp_requirement)

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
