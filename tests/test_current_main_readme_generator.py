from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "refresh_current_main_readme.py"


def test_current_main_readme_generator_is_at_fixed_point() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["acceptance"] == "PASS"
    assert report["failures"] == []
    assert report["code_anchors"] == [
        "src/aspenops_nexus/process_ir.py",
        "src/aspenops_nexus/models.py",
        "src/aspenops_nexus/pool.py",
    ]
    assert set(report["generated_files"]) == {
        "README.en.md",
        "README.md",
        "docs/CURRENT_MAIN_ACCEPTANCE.md",
        "docs/current-main/aspenops-current-main-en.svg",
        "docs/current-main/aspenops-current-main-zh.svg",
    }
