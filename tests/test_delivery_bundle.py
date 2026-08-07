from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import zipfile
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_delivery_bundle.py"
SOURCE_SHA = "a" * 40


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_delivery_bundle", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _repository(root: Path) -> Path:
    (root / "docs").mkdir(parents=True)
    (root / "src").mkdir()
    (root / "scripts").mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "aspenops-nexus"\nversion = "2.0.0"\n',
        encoding="utf-8",
    )
    (root / "uv.lock").write_text(
        """version = 1

[[package]]
name = "aspenops-nexus"
version = "2.0.0"

[[package]]
name = "pytest"
version = "9.1.1"
""",
        encoding="utf-8",
    )
    (root / "README.md").write_text("# delivery fixture\n", encoding="utf-8")
    (root / "LICENSE").write_text("Apache-2.0\n", encoding="utf-8")
    (root / "src" / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    evidence = {
        "schema": "aspenops.acceptance-hardening-qualification/v2",
        "status": "PASS",
        "passed": 1224,
        "branch_coverage_percent": 95.03,
        "validated_source_parent": SOURCE_SHA,
        "real_aspen_status": "PENDING_REAL_ASPEN_CERTIFICATION",
    }
    (root / "docs" / "ACCEPTANCE_HARDENING_QUALIFICATION.json").write_text(
        json.dumps(evidence, sort_keys=True),
        encoding="utf-8",
    )
    return root


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_delivery_bundle_is_deterministic_and_self_verifying(tmp_path: Path) -> None:
    module = _load_module()
    root = _repository(tmp_path / "repo")
    first = tmp_path / "first"
    second = tmp_path / "second"

    first_report = module.build_delivery_bundle(
        root=root,
        output_dir=first,
        source_sha=SOURCE_SHA,
        source_date_epoch=0,
    )
    second_report = module.build_delivery_bundle(
        root=root,
        output_dir=second,
        source_sha=SOURCE_SHA,
        source_date_epoch=0,
    )

    assert first_report["status"] == "PASS"
    assert first_report["real_aspen_status"] == "PENDING_REAL_ASPEN_CERTIFICATION"
    assert first_report["source_file_count"] == 6
    assert {item.name for item in first.iterdir()} == {
        item.name for item in second.iterdir()
    }
    for first_path in first.iterdir():
        assert first_path.read_bytes() == (second / first_path.name).read_bytes()

    checksum_lines = (first / "SHA256SUMS").read_text(encoding="ascii").splitlines()
    for line in checksum_lines:
        digest, name = line.split("  ", 1)
        assert digest == _sha256(first / name)

    handover = next(first.glob("aspenops-handover-*.zip"))
    digest_file = first / f"{handover.name}.sha256"
    assert digest_file.read_text(encoding="ascii") == (
        f"{_sha256(handover)}  {handover.name}\n"
    )


def test_source_archive_is_sorted_normalized_and_excludes_transient_files(
    tmp_path: Path,
) -> None:
    module = _load_module()
    root = _repository(tmp_path / "repo")
    (root / "var").mkdir()
    (root / "var" / "secret.json").write_text("{}", encoding="utf-8")
    (root / ".venv").mkdir()
    (root / ".venv" / "private.txt").write_text("private", encoding="utf-8")
    (root / "src" / "__pycache__").mkdir()
    (root / "src" / "__pycache__" / "module.pyc").write_bytes(b"bytecode")
    (root / ".coverage").write_text("coverage-db", encoding="utf-8")

    output = tmp_path / "delivery"
    module.build_delivery_bundle(root=root, output_dir=output, source_sha=SOURCE_SHA)
    source_archive = next(output.glob("aspenops-source-*.zip"))
    with zipfile.ZipFile(source_archive) as archive:
        names = archive.namelist()
        assert names == sorted(names)
        assert all("/var/" not in name for name in names)
        assert all("/.venv/" not in name for name in names)
        assert all("/__pycache__/" not in name for name in names)
        assert all(not name.endswith("/.coverage") for name in names)
        for item in archive.infolist():
            assert item.date_time == (1980, 1, 1, 0, 0, 0)
            assert item.external_attr >> 16 == 0o100644


def test_include_dist_copies_only_wheel_and_source_distribution(tmp_path: Path) -> None:
    module = _load_module()
    root = _repository(tmp_path / "repo")
    (root / "dist").mkdir()
    (root / "dist" / "aspenops_nexus-2.0.0-py3-none-any.whl").write_bytes(b"wheel")
    (root / "dist" / "aspenops_nexus-2.0.0.tar.gz").write_bytes(b"sdist")
    (root / "dist" / "unrelated.gz").write_bytes(b"not-a-source-distribution")
    (root / "dist" / "ignore.txt").write_text("ignore", encoding="utf-8")

    output = tmp_path / "delivery"
    report = module.build_delivery_bundle(
        root=root,
        output_dir=output,
        source_sha=SOURCE_SHA,
        include_dist=True,
    )
    artifact_names = {item["path"] for item in report["artifacts"]}
    assert "aspenops_nexus-2.0.0-py3-none-any.whl" in artifact_names
    assert "aspenops_nexus-2.0.0.tar.gz" in artifact_names
    assert "unrelated.gz" not in artifact_names
    assert "ignore.txt" not in artifact_names


@pytest.mark.parametrize("source_sha", ["main", "G" * 40, "A" * 40])
def test_invalid_sha_fails_closed(tmp_path: Path, source_sha: str) -> None:
    module = _load_module()
    root = _repository(tmp_path / "repo")
    with pytest.raises(module.DeliveryBundleError, match="lowercase hexadecimal"):
        module.build_delivery_bundle(
            root=root,
            output_dir=tmp_path / "bad-sha",
            source_sha=source_sha,
        )


@pytest.mark.parametrize("source_date_epoch", [True, 1.5, -1])
def test_invalid_source_date_epoch_fails_closed(
    tmp_path: Path,
    source_date_epoch: object,
) -> None:
    module = _load_module()
    root = _repository(tmp_path / "repo")
    with pytest.raises(module.DeliveryBundleError, match="non-negative integer"):
        module.build_delivery_bundle(
            root=root,
            output_dir=tmp_path / "bad-epoch",
            source_sha=SOURCE_SHA,
            source_date_epoch=source_date_epoch,
        )


def test_nonempty_or_file_output_path_fails_closed(tmp_path: Path) -> None:
    module = _load_module()
    root = _repository(tmp_path / "repo")

    nonempty = tmp_path / "nonempty"
    nonempty.mkdir()
    (nonempty / "existing.txt").write_text("do not overwrite", encoding="utf-8")
    with pytest.raises(module.DeliveryBundleError, match="must be empty"):
        module.build_delivery_bundle(
            root=root,
            output_dir=nonempty,
            source_sha=SOURCE_SHA,
        )

    output_file = tmp_path / "output-file"
    output_file.write_text("not a directory", encoding="utf-8")
    with pytest.raises(module.DeliveryBundleError, match="must be a directory"):
        module.build_delivery_bundle(
            root=root,
            output_dir=output_file,
            source_sha=SOURCE_SHA,
        )


def test_evidence_cannot_self_promote_real_aspen_certification(tmp_path: Path) -> None:
    module = _load_module()
    root = _repository(tmp_path / "repo")
    evidence_path = root / "docs" / "ACCEPTANCE_HARDENING_QUALIFICATION.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["real_aspen_status"] = "REAL_ASPEN_CERTIFIED"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    with pytest.raises(module.DeliveryBundleError, match="PENDING_REAL_ASPEN_CERTIFICATION"):
        module.build_delivery_bundle(
            root=root,
            output_dir=tmp_path / "delivery",
            source_sha=SOURCE_SHA,
        )


def test_git_checkout_identity_and_dirty_source_are_enforced(tmp_path: Path) -> None:
    module = _load_module()
    root = _repository(tmp_path / "repo")
    (root / ".gitignore").write_text("ignored-secret.txt\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], check=True, shell=False)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "test@example.invalid"],
        check=True,
        shell=False,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "AspenOps Test"],
        check=True,
        shell=False,
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True, shell=False)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-qm", "fixture"],
        check=True,
        shell=False,
    )
    source_sha = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        shell=False,
    ).stdout.strip()
    (root / "ignored-secret.txt").write_text("must-not-ship", encoding="utf-8")

    report = module.build_delivery_bundle(
        root=root,
        output_dir=tmp_path / "clean-delivery",
        source_sha=source_sha,
    )
    manifest = json.loads(
        next(
            (tmp_path / "clean-delivery").glob("aspenops-delivery-manifest-*.json")
        ).read_text(encoding="utf-8")
    )
    assert manifest["git_identity_verified"] is True
    assert report["status"] == "PASS"
    source_archive = next((tmp_path / "clean-delivery").glob("aspenops-source-*.zip"))
    with zipfile.ZipFile(source_archive) as archive:
        assert all(not name.endswith("ignored-secret.txt") for name in archive.namelist())

    (root / "src" / "module.py").write_text("VALUE = 2\n", encoding="utf-8")
    with pytest.raises(module.DeliveryBundleError, match="uncommitted"):
        module.build_delivery_bundle(
            root=root,
            output_dir=tmp_path / "dirty-delivery",
            source_sha=source_sha,
        )


def test_generated_current_qualification_is_evidence_not_source(tmp_path: Path) -> None:
    module = _load_module()
    root = _repository(tmp_path / "repo")
    current = {
        "schema": "aspenops.delivery-qualification/v2",
        "status": "PASS",
        "passed": 1204,
        "branch_coverage_percent": 95.2,
        "validated_source_parent": SOURCE_SHA,
        "real_aspen_status": "PENDING_REAL_ASPEN_CERTIFICATION",
    }
    path = root / "docs" / "DELIVERY_QUALIFICATION.json"
    path.write_text(json.dumps(current), encoding="utf-8")
    output = tmp_path / "delivery-current"
    module.build_delivery_bundle(root=root, output_dir=output, source_sha=SOURCE_SHA)

    source_archive = next(output.glob("aspenops-source-*.zip"))
    with zipfile.ZipFile(source_archive) as archive:
        assert all(
            not name.endswith("docs/DELIVERY_QUALIFICATION.json")
            for name in archive.namelist()
        )
    evidence = json.loads(next(output.glob("aspenops-evidence-index-*.json")).read_text())
    assert any(
        record["path"] == "docs/DELIVERY_QUALIFICATION.json"
        for record in evidence["records"]
    )


def test_git_current_qualification_must_match_head_tree(tmp_path: Path) -> None:
    module = _load_module()
    root = _repository(tmp_path / "repo")
    subprocess.run(["git", "init", "-q", str(root)], check=True, shell=False)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "test@example.invalid"],
        check=True,
        shell=False,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "AspenOps Test"],
        check=True,
        shell=False,
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True, shell=False)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-qm", "fixture"],
        check=True,
        shell=False,
    )
    source_sha = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        shell=False,
    ).stdout.strip()
    tree_sha = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD^{tree}"],
        check=True,
        capture_output=True,
        text=True,
        shell=False,
    ).stdout.strip()
    current = {
        "schema": "aspenops.delivery-qualification/v2",
        "status": "PASS",
        "passed": 1204,
        "branch_coverage_percent": 95.2,
        "validated_source_parent": source_sha,
        "qualified_content_tree_sha": tree_sha,
        "real_aspen_status": "PENDING_REAL_ASPEN_CERTIFICATION",
    }
    path = root / "docs" / "DELIVERY_QUALIFICATION.json"
    path.write_text(json.dumps(current), encoding="utf-8")

    report = module.build_delivery_bundle(
        root=root,
        output_dir=tmp_path / "matched-delivery",
        source_sha=source_sha,
    )
    manifest = json.loads(
        next(
            (tmp_path / "matched-delivery").glob("aspenops-delivery-manifest-*.json")
        ).read_text(encoding="utf-8")
    )
    assert manifest["git_tree_sha"] == tree_sha
    assert report["status"] == "PASS"

    current["qualified_content_tree_sha"] = "c" * 40
    path.write_text(json.dumps(current), encoding="utf-8")
    with pytest.raises(module.DeliveryBundleError, match="Git tree"):
        module.build_delivery_bundle(
            root=root,
            output_dir=tmp_path / "mismatched-delivery",
            source_sha=source_sha,
        )


def test_cli_writes_machine_readable_report(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_module()
    root = _repository(tmp_path / "repo")
    output = tmp_path / "delivery"
    assert (
        module.main(
            [
                "--root",
                str(root),
                "--output-dir",
                str(output),
                "--source-sha",
                SOURCE_SHA,
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["schema"] == "aspenops.delivery-build-report/v1"
    assert report["status"] == "PASS"
