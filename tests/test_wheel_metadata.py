from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts.check_wheel_metadata import inspect_wheel


def _wheel(
    dist_dir: Path,
    requirement: str,
    *,
    name: str = "aspenops_nexus-2.0.0-py3-none-any.whl",
    padding_bytes: int = 0,
) -> Path:
    dist_dir.mkdir(parents=True, exist_ok=True)
    wheel = dist_dir / name
    metadata = "\n".join(
        [
            "Metadata-Version: 2.4",
            "Name: aspenops-nexus",
            "Version: 2.0.0",
            f"Requires-Dist: {requirement}",
            "X-Padding: " + ("x" * padding_bytes),
            "",
        ]
    )
    with ZipFile(wheel, "w") as archive:
        archive.writestr("aspenops_nexus-2.0.0.dist-info/METADATA", metadata)
    return wheel


def test_wheel_metadata_accepts_supported_agent_constraint(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    wheel = _wheel(dist, "mcp<2,>=1.9; extra == 'agent'")

    report = inspect_wheel(dist)

    assert report == {
        "ok": True,
        "wheel": wheel.name,
        "metadata_member": "aspenops_nexus-2.0.0.dist-info/METADATA",
        "mcp_requirement": "mcp<2,>=1.9; extra == 'agent'",
    }


@pytest.mark.parametrize(
    "requirement",
    [
        "mcp>=1.9; extra == 'agent'",
        "mcp<20,>=1.9; extra == 'agent'",
        "mcp<2,>=1.9; extra == 'wrong'",
    ],
)
def test_wheel_metadata_rejects_unsafe_constraints(
    requirement: str,
    tmp_path: Path,
) -> None:
    dist = tmp_path / "dist"
    _wheel(dist, requirement)

    with pytest.raises(RuntimeError):
        inspect_wheel(dist)


def test_wheel_metadata_rejects_ambiguous_artifacts(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    _wheel(dist, "mcp<2,>=1.9; extra == 'agent'")
    _wheel(
        dist,
        "mcp<2,>=1.9; extra == 'agent'",
        name="aspenops_nexus-2.0.1-py3-none-any.whl",
    )

    with pytest.raises(RuntimeError, match="exactly one AspenOps Wheel"):
        inspect_wheel(dist)


def test_wheel_metadata_rejects_oversized_metadata(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    _wheel(
        dist,
        "mcp<2,>=1.9; extra == 'agent'",
        padding_bytes=256_000,
    )

    with pytest.raises(RuntimeError, match="METADATA exceeds"):
        inspect_wheel(dist)
