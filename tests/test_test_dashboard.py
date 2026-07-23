from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


SCRIPT = Path("scripts/render_test_dashboard.py")


def load_module():
    spec = importlib.util.spec_from_file_location("render_test_dashboard", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_dashboard_parses_junit_and_coverage(tmp_path: Path) -> None:
    module = load_module()
    junit = tmp_path / "junit.xml"
    junit.write_text(
        '<testsuite tests="12" failures="1" errors="1" skipped="2" time="3.5"/>',
        encoding="utf-8",
    )
    coverage = tmp_path / "coverage.json"
    coverage.write_text('{"totals":{"percent_covered":94.5}}', encoding="utf-8")

    summary = module.parse_junit([junit])
    totals = module.parse_coverage([coverage])

    assert summary.tests == 12
    assert summary.passed == 8
    assert summary.failures == 1
    assert summary.errors == 1
    assert summary.skipped == 2
    assert summary.seconds == 3.5
    assert totals.percent == 94.5


def test_dashboard_outputs_are_self_contained(tmp_path: Path) -> None:
    module = load_module()
    summary = module.TestSummary(tests=10, failures=0, errors=0, skipped=0, seconds=2.0)
    coverage = module.CoverageSummary(percent=95.0)

    page = module.render_html(
        title="AspenOps test dashboard",
        scope="Python 3.12",
        note="Current supplied evidence only.",
        summary=summary,
        coverage=coverage,
        files=[tmp_path / "junit.xml"],
    )
    svg = module.render_svg(
        title="AspenOps test dashboard",
        scope="Python 3.12",
        summary=summary,
        coverage=coverage,
    )

    assert "<!doctype html>" in page
    assert "data-target=\"summary\"" in page
    assert "Evidence boundary" in page
    assert "fetch(" not in page
    assert "http://" not in page
    assert "https://" not in page
    assert "<svg" in svg
    assert "Current supplied evidence only" in svg


def test_dashboard_marks_missing_evidence_incomplete() -> None:
    module = load_module()
    summary = module.TestSummary()
    coverage = module.CoverageSummary()

    page = module.render_html(
        title="Dashboard",
        scope="No evidence",
        note="Early failure.",
        summary=summary,
        coverage=coverage,
        files=[],
    )
    svg = module.render_svg(
        title="Dashboard",
        scope="No evidence",
        summary=summary,
        coverage=coverage,
    )

    assert summary.pass_rate == 0.0
    assert "INCOMPLETE" in page
    assert "INCOMPLETE" in svg
    assert "100.00%" not in page


def test_dashboard_is_integrated_and_documented() -> None:
    workflows = (
        Path(".github/workflows/ci.yml"),
        Path(".github/workflows/windows-control-plane.yml"),
        Path(".github/workflows/licensed-aspen-certification.yml"),
    )
    for workflow in workflows:
        text = workflow.read_text(encoding="utf-8")
        assert "scripts/render_test_dashboard.py" in text
        assert "test-dashboard-" in text

    for readme in (Path("README.md"), Path("README.en.md")):
        text = readme.read_text(encoding="utf-8")
        assert "scripts/render_test_dashboard.py" in text
        assert "test-dashboard-quality.html" in text
        assert "test-dashboard-windows.html" in text
        assert "test-dashboard-licensed.html" in text


def test_dashboard_cli_writes_html_and_svg(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    junit = tmp_path / "junit.xml"
    junit.write_text(
        '<testsuite tests="5" failures="0" errors="0" skipped="0" time="1.0"/>',
        encoding="utf-8",
    )
    html_output = tmp_path / "dashboard.html"
    svg_output = tmp_path / "dashboard.svg"
    monkeypatch.setattr(
        "sys.argv",
        [
            str(SCRIPT),
            "--input-dir",
            str(tmp_path),
            "--output-html",
            str(html_output),
            "--output-svg",
            str(svg_output),
            "--title",
            "Dashboard",
        ],
    )

    assert module.main() == 0
    assert html_output.is_file()
    assert svg_output.is_file()
    assert "Dashboard" in html_output.read_text(encoding="utf-8")
    assert "5" in svg_output.read_text(encoding="utf-8")
