from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "final_acceptance_preflight.py"


def _load() -> Any:
    spec = importlib.util.spec_from_file_location("final_acceptance_preflight", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_final_acceptance_preflight_contract() -> None:
    module = _load()
    assert module.platform_family("win32") == "windows"
    assert module.platform_family("linux") == "linux"
    assert module.platform_family("darwin") == "unsupported"
    report = module.build_report(ROOT, platform_name="linux")
    assert report["status"] == "PASS", report["issues"]
    assert report["solver_or_experiment_executed"] is False
    assert report["automatic_scientific_approval"] is False
    assert report["external_boundary_marker"] == "PENDING_REAL_ASPEN_CERTIFICATION"
    assert set(report["delivery_platforms"]) == {"windows", "linux"}


def test_preflight_rejects_unsupported_platform() -> None:
    module = _load()
    report = module.build_report(ROOT, platform_name="darwin")
    assert report["status"] == "BLOCK"
    assert any(issue["code"] == "platform_unsupported" for issue in report["issues"])
