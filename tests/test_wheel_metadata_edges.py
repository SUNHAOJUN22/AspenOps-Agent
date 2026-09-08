from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from aspenops_nexus import wheel_metadata


def _write_wheel(
    dist_dir: Path,
    *,
    filename: str = "aspenops_nexus-2.0.0-py3-none-any.whl",
    metadata_members: list[tuple[str, str]] | None = None,
) -> Path:
    dist_dir.mkdir(parents=True, exist_ok=True)
    wheel = dist_dir / filename
    members = metadata_members
    if members is None:
        members = [
            (
                "aspenops_nexus-2.0.0.dist-info/METADATA",
                "Metadata-Version: 2.4\n"
                "Name: aspenops-nexus\n"
                "Version: 2.0.0\n"
                "Requires-Dist: mcp<2,>=1.9; extra == 'agent'\n\n",
            )
        ]
    with ZipFile(wheel, "w") as archive:
        for name, content in members:
            archive.writestr(name, content)
    return wheel


@pytest.mark.parametrize(
    ("requirement", "message"),
    [
        ("other>=1.9,<2; extra == 'agent'", "unexpected package name"),
        ("mcp>=1.9; extra == 'agent'", "must constrain"),
        ("mcp>=1.9,<2", "scoped to the agent extra"),
        ("mcp>=1.9,<2; extra == 'other'", "scoped to the agent extra"),
    ],
)
def test_mcp_requirement_contract_rejects_every_boundary(
    requirement: str,
    message: str,
) -> None:
    with pytest.raises(RuntimeError, match=message):
        wheel_metadata._validate_mcp_requirement(requirement)


def test_inspect_wheel_requires_exactly_one_distribution(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="found 0"):
        wheel_metadata.inspect_wheel(tmp_path)

    _write_wheel(tmp_path)
    _write_wheel(
        tmp_path,
        filename="aspenops_nexus-2.0.1-py3-none-any.whl",
    )
    with pytest.raises(RuntimeError, match="found 2"):
        wheel_metadata.inspect_wheel(tmp_path)


@pytest.mark.parametrize("member_count", [0, 2])
def test_inspect_wheel_requires_one_metadata_member(
    tmp_path: Path,
    member_count: int,
) -> None:
    members = [
        (f"package_{index}.dist-info/METADATA", "Metadata-Version: 2.4\n\n")
        for index in range(member_count)
    ]
    _write_wheel(tmp_path, metadata_members=members)

    with pytest.raises(RuntimeError, match=f"found {member_count}"):
        wheel_metadata.inspect_wheel(tmp_path)


def test_inspect_wheel_rejects_oversized_metadata(tmp_path: Path) -> None:
    oversized = "X-Metadata: " + ("x" * wheel_metadata._MAX_METADATA_BYTES)
    _write_wheel(
        tmp_path,
        metadata_members=[("aspenops_nexus-2.0.0.dist-info/METADATA", oversized)],
    )

    with pytest.raises(RuntimeError, match="METADATA exceeds"):
        wheel_metadata.inspect_wheel(tmp_path)


@pytest.mark.parametrize("mcp_entries", [0, 2])
def test_inspect_wheel_requires_one_mcp_requirement(
    tmp_path: Path,
    mcp_entries: int,
) -> None:
    requirements = "".join(
        "Requires-Dist: mcp<2,>=1.9; extra == 'agent'\n" for _ in range(mcp_entries)
    )
    metadata = f"Metadata-Version: 2.4\nName: aspenops-nexus\nVersion: 2.0.0\n{requirements}\n"
    _write_wheel(
        tmp_path,
        metadata_members=[("aspenops_nexus-2.0.0.dist-info/METADATA", metadata)],
    )

    with pytest.raises(RuntimeError, match=f"found {mcp_entries}"):
        wheel_metadata.inspect_wheel(tmp_path)


def test_wheel_metadata_cli_writes_the_same_json_it_prints(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    dist_dir = tmp_path / "dist"
    wheel = _write_wheel(dist_dir)
    output = tmp_path / "reports" / "wheel.json"

    assert wheel_metadata.main(["--dist-dir", str(dist_dir), "--output", str(output)]) == 0
    printed = json.loads(capsys.readouterr().out)
    stored = json.loads(output.read_text(encoding="utf-8"))

    assert printed == stored
    assert stored["ok"] is True
    assert stored["wheel"] == wheel.name
