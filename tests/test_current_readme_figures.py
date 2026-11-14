from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/update_readme_gallery.py"


def _load() -> Any:
    spec = importlib.util.spec_from_file_location("current_readme_figures", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fixture(root: Path, module: Any) -> None:
    for relative, images in module.DOCUMENT_FIGURES.items():
        document = root / relative
        document.parent.mkdir(parents=True, exist_ok=True)
        document.write_text(
            "# Figure contract\n\n"
            + "\n".join(f"![Current figure]({target})" for target in images)
            + "\n[Historical figure](old.svg)\n",
            encoding="utf-8",
        )
        for target in images:
            asset = document.parent / target
            asset.parent.mkdir(parents=True, exist_ok=True)
            asset.write_bytes(module.PNG_MAGIC)


def test_legacy_gallery_entry_point_preserves_documentation_and_qualification(
    tmp_path: Path,
) -> None:
    module = _load()
    _fixture(tmp_path, module)
    evidence = tmp_path / "qualification.json"
    evidence.write_text('{"status":"historical-only"}\n', encoding="utf-8")
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    assert module.check_current_figures(tmp_path) == []
    assert {path: path.read_bytes() for path in before} == before


@pytest.mark.parametrize(
    "document",
    ["README.md", "README.en.md", "README_ACCEPTANCE.md", "docs/assets/README.md"],
)
@pytest.mark.parametrize("mutation", ["missing", "duplicate", "historical", "html"])
def test_current_figure_contract_rejects_removed_or_substituted_images(
    tmp_path: Path, document: str, mutation: str
) -> None:
    module = _load()
    _fixture(tmp_path, module)
    path = tmp_path / document
    text = path.read_text(encoding="utf-8")
    image = f"![Current figure]({module.DOCUMENT_FIGURES[document][0]})"
    if mutation == "missing":
        text = text.replace(image, "")
    elif mutation == "duplicate":
        text += "\n" + image
    elif mutation == "historical":
        text = text.replace(image, "![Deterministic archive](old.svg)")
    else:
        text += '\n<img src="old.svg">'
    path.write_text(text, encoding="utf-8")
    issues = module.check_current_figures(tmp_path)
    assert issues
    assert all(issue.startswith(document + ":") for issue in issues)


@pytest.mark.parametrize("mutation", ["missing", "symlink", "wrong_format"])
def test_current_figure_contract_rejects_invalid_asset_files(tmp_path: Path, mutation: str) -> None:
    module = _load()
    _fixture(tmp_path, module)
    asset = tmp_path / "docs/assets/ai-generated/algorithm.png"
    if mutation == "missing":
        asset.unlink()
    elif mutation == "symlink":
        asset.unlink()
        asset.symlink_to("architecture.png")
    else:
        asset.write_text("<svg/>", encoding="utf-8")
    assert module.check_current_figures(tmp_path)
