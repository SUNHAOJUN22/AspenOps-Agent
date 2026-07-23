from __future__ import annotations

import argparse
import html
import json
import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class TestSummary:
    tests: int = 0
    failures: int = 0
    errors: int = 0
    skipped: int = 0
    seconds: float = 0.0

    @property
    def passed(self) -> int:
        return max(0, self.tests - self.failures - self.errors - self.skipped)

    @property
    def pass_rate(self) -> float:
        return 100.0 if self.tests == 0 else 100.0 * self.passed / self.tests


@dataclass(frozen=True)
class CoverageSummary:
    percent: float | None = None


def _as_int(value: object) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return 0


def _as_float(value: object) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0.0


def _suite_totals(element: ET.Element) -> TestSummary:
    return TestSummary(
        tests=_as_int(element.attrib.get("tests")),
        failures=_as_int(element.attrib.get("failures")),
        errors=_as_int(element.attrib.get("errors")),
        skipped=_as_int(element.attrib.get("skipped")),
        seconds=_as_float(element.attrib.get("time")),
    )


def parse_junit(paths: Iterable[Path]) -> TestSummary:
    total = TestSummary()
    for path in paths:
        root = ET.parse(path).getroot()
        summary = _suite_totals(root)
        if summary.tests == 0 and root.tag == "testsuites":
            children = [_suite_totals(child) for child in root.findall("testsuite")]
            summary = TestSummary(
                tests=sum(item.tests for item in children),
                failures=sum(item.failures for item in children),
                errors=sum(item.errors for item in children),
                skipped=sum(item.skipped for item in children),
                seconds=sum(item.seconds for item in children),
            )
        total = TestSummary(
            tests=total.tests + summary.tests,
            failures=total.failures + summary.failures,
            errors=total.errors + summary.errors,
            skipped=total.skipped + summary.skipped,
            seconds=total.seconds + summary.seconds,
        )
    return total


def _percentage(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return max(0.0, min(100.0, number))


def parse_coverage(paths: Iterable[Path]) -> CoverageSummary:
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        totals = data.get("totals")
        if isinstance(totals, dict):
            return CoverageSummary(_percentage(totals.get("percent_covered")))
    return CoverageSummary()


def discover_files(input_dir: Path) -> tuple[list[Path], list[Path]]:
    return sorted(input_dir.glob("*.xml")), sorted(input_dir.glob("coverage*.json"))


def _fmt_percent(value: float | None) -> str:
    return "Not available" if value is None else f"{value:.2f}%"


def _metric(label: str, value: str, note: str) -> str:
    return "".join(
        [
            '<section class="metric">',
            f'<div class="metric-label">{html.escape(label)}</div>',
            f'<div class="metric-value">{html.escape(value)}</div>',
            f'<div class="metric-note">{html.escape(note)}</div>',
            "</section>",
        ]
    )


def _bar(label: str, value: float) -> str:
    safe = max(0.0, min(100.0, value))
    return "".join(
        [
            '<div class="bar-row">',
            f'<div class="bar-label">{html.escape(label)}</div>',
            '<div class="bar-track">',
            f'<div class="bar-fill" style="width:{safe:.2f}%"></div>',
            "</div>",
            f'<div class="bar-value">{safe:.2f}%</div>',
            "</div>",
        ]
    )


def _html_styles(status_color: str) -> str:
    return "\n".join(
        [
            ":root { color-scheme: light dark; --accent:#2563eb; }",
            "* { box-sizing:border-box; }",
            "body { margin:0; font-family:system-ui,-apple-system,Segoe UI,sans-serif; }",
            "body { background:#f4f6f8; color:#17202a; }",
            "main { max-width:980px; margin:0 auto; padding:28px; }",
            "header { display:flex; justify-content:space-between; gap:20px; }",
            "header { align-items:flex-start; }",
            "h1 { margin:0 0 6px; font-size:28px; }",
            "p { line-height:1.55; }",
            ".badge { border-radius:999px; padding:8px 13px; font-weight:700; }",
            f".badge {{ background:{status_color}; color:white; }}",
            ".metrics { display:grid; gap:12px; margin:22px 0; }",
            ".metrics { grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); }",
            ".metric,.panel { background:white; border:1px solid #dbe2e8; }",
            ".metric,.panel { border-radius:14px; padding:16px; }",
            ".panel { margin:14px 0; padding:18px; }",
            ".metric-label,.metric-note { color:#5b6770; font-size:13px; }",
            ".metric-value { font-size:28px; font-weight:750; margin:4px 0; }",
            ".bar-row { display:grid; grid-template-columns:110px 1fr 82px; }",
            ".bar-row { gap:12px; align-items:center; margin:14px 0; }",
            ".bar-track { height:12px; background:#e5e9ee; border-radius:999px; }",
            ".bar-track { overflow:hidden; }",
            ".bar-fill { height:100%; background:var(--accent); }",
            ".bar-value { text-align:right; font-variant-numeric:tabular-nums; }",
            "button { border:1px solid #cbd5df; background:white; border-radius:10px; }",
            "button { padding:9px 12px; cursor:pointer; }",
            "button[aria-pressed='true'] { background:var(--accent); color:white; }",
            ".hidden { display:none; }",
            "code { font-size:13px; }",
            "small { color:#5b6770; }",
            "@media (prefers-color-scheme:dark) {",
            " body { background:#111827; color:#e5e7eb; }",
            " .metric,.panel,button { background:#18212f; border-color:#334155; }",
            " .metric,.panel,button { color:#e5e7eb; }",
            " .metric-label,.metric-note,small { color:#a8b3c0; }",
            " .bar-track { background:#334155; }",
            "}",
        ]
    )


def render_html(
    *,
    title: str,
    scope: str,
    note: str,
    summary: TestSummary,
    coverage: CoverageSummary,
    files: list[Path],
) -> str:
    metrics = "".join(
        [
            _metric("Tests", str(summary.tests), "Discovered JUnit cases"),
            _metric("Passed", str(summary.passed), "Failures and skips excluded"),
            _metric("Pass rate", f"{summary.pass_rate:.2f}%", "Current evidence"),
            _metric("Coverage", _fmt_percent(coverage.percent), "When available"),
        ]
    )
    bars = _bar("Pass rate", summary.pass_rate) + _bar(
        "Coverage", coverage.percent or 0.0
    )
    evidence = "".join(
        f"<li><code>{html.escape(path.name)}</code></li>" for path in files
    )
    evidence = evidence or "<li>No matching evidence files were supplied.</li>"
    status = "PASS" if summary.failures == 0 and summary.errors == 0 else "FAIL"
    status_color = "#15803d" if status == "PASS" else "#b91c1c"
    summary_detail = (
        f"<p><strong>Duration:</strong> {summary.seconds:.2f} s</p>"
        f"<p><strong>Failures:</strong> {summary.failures}; "
        f"<strong>Errors:</strong> {summary.errors}; "
        f"<strong>Skipped:</strong> {summary.skipped}</p>"
    )
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width,initial-scale=1">',
            f"<title>{html.escape(title)}</title>",
            "<style>",
            _html_styles(status_color),
            "</style>",
            "</head>",
            "<body>",
            "<main>",
            "<header>",
            f"<div><h1>{html.escape(title)}</h1><p>{html.escape(scope)}</p></div>",
            f'<div class="badge">{status}</div>',
            "</header>",
            f'<div class="metrics">{metrics}</div>',
            '<div role="group" aria-label="Dashboard sections">',
            '<button type="button" data-target="summary" aria-pressed="true">',
            "Summary</button>",
            '<button type="button" data-target="evidence" aria-pressed="false">',
            "Evidence</button>",
            "</div>",
            f'<section id="summary" class="panel">{bars}{summary_detail}</section>',
            '<section id="evidence" class="panel hidden">',
            f"<h2>Evidence files</h2><ul>{evidence}</ul></section>",
            '<section class="panel"><strong>Evidence boundary:</strong> ',
            f"{html.escape(note)}</section>",
            "<small>Generated by scripts/render_test_dashboard.py. ",
            "No network resources are required.</small>",
            "</main>",
            "<script>",
            "const buttons = document.querySelectorAll('button[data-target]');",
            "buttons.forEach((button) => button.addEventListener('click', () => {",
            " buttons.forEach((item) => item.setAttribute(",
            "  'aria-pressed', String(item === button)));",
            " document.querySelectorAll('main > section[id]').forEach((section) =>",
            "  section.classList.add('hidden'));",
            " document.getElementById(button.dataset.target).classList.remove('hidden');",
            "}));",
            "</script>",
            "</body>",
            "</html>",
        ]
    )


def render_svg(
    *,
    title: str,
    scope: str,
    summary: TestSummary,
    coverage: CoverageSummary,
) -> str:
    coverage_value = coverage.percent or 0.0
    status = "PASS" if summary.failures == 0 and summary.errors == 0 else "FAIL"
    status_color = "#15803d" if status == "PASS" else "#b91c1c"
    pass_width = 1072 * summary.pass_rate / 100
    coverage_width = 1072 * coverage_value / 100
    escaped_title = html.escape(title)
    escaped_scope = html.escape(scope)
    return "\n".join(
        [
            '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="675"',
            ' viewBox="0 0 1200 675" role="img"',
            f' aria-label="{escaped_title} test dashboard">',
            '<rect width="1200" height="675" fill="#f7f9fb"/>',
            '<text x="64" y="76" font-family="Arial, sans-serif" font-size="34"',
            f' font-weight="700" fill="#17202a">{escaped_title}</text>',
            '<text x="64" y="112" font-family="Arial, sans-serif" font-size="18"',
            f' fill="#5b6770">{escaped_scope}</text>',
            f'<rect x="1016" y="48" width="120" height="44" rx="22" fill="{status_color}"/>',
            '<text x="1076" y="77" text-anchor="middle"',
            ' font-family="Arial, sans-serif" font-size="20" font-weight="700"',
            f' fill="#ffffff">{status}</text>',
            '<g font-family="Arial, sans-serif">',
            '<rect x="64" y="156" width="248" height="136" rx="18"',
            ' fill="#ffffff" stroke="#dbe2e8"/>',
            '<text x="88" y="190" font-size="16" fill="#5b6770">Tests</text>',
            f'<text x="88" y="248" font-size="48" font-weight="700">{summary.tests}</text>',
            '<rect x="328" y="156" width="248" height="136" rx="18"',
            ' fill="#ffffff" stroke="#dbe2e8"/>',
            '<text x="352" y="190" font-size="16" fill="#5b6770">Passed</text>',
            f'<text x="352" y="248" font-size="48" font-weight="700">{summary.passed}</text>',
            '<rect x="592" y="156" width="248" height="136" rx="18"',
            ' fill="#ffffff" stroke="#dbe2e8"/>',
            '<text x="616" y="190" font-size="16" fill="#5b6770">Pass rate</text>',
            '<text x="616" y="248" font-size="48" font-weight="700">',
            f"{summary.pass_rate:.1f}%</text>",
            '<rect x="856" y="156" width="280" height="136" rx="18"',
            ' fill="#ffffff" stroke="#dbe2e8"/>',
            '<text x="880" y="190" font-size="16" fill="#5b6770">Coverage</text>',
            '<text x="880" y="248" font-size="48" font-weight="700">',
            f"{_fmt_percent(coverage.percent)}</text>",
            '<text x="64" y="358" font-size="18" font-weight="700">Pass rate</text>',
            '<rect x="64" y="378" width="1072" height="20" rx="10"',
            ' fill="#e5e9ee"/>',
            f'<rect x="64" y="378" width="{pass_width:.2f}" height="20"',
            ' rx="10" fill="#2563eb"/>',
            '<text x="64" y="452" font-size="18" font-weight="700">Coverage</text>',
            '<rect x="64" y="472" width="1072" height="20" rx="10"',
            ' fill="#e5e9ee"/>',
            f'<rect x="64" y="472" width="{coverage_width:.2f}" height="20"',
            ' rx="10" fill="#7c3aed"/>',
            '<text x="64" y="555" font-size="18">',
            f"Failures {summary.failures}   Errors {summary.errors}   ",
            f"Skipped {summary.skipped}   Duration {summary.seconds:.2f} s</text>",
            '<text x="64" y="620" font-size="15" fill="#5b6770">',
            "Current supplied evidence only. Archived repository baselines remain ",
            "explicitly labeled as archived.</text>",
            "</g>",
            "</svg>",
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render JUnit and coverage dashboards.")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-html", type=Path, required=True)
    parser.add_argument("--output-svg", type=Path, required=True)
    parser.add_argument("--title", default="AspenOps test dashboard")
    parser.add_argument("--scope", default="Automated test evidence")
    parser.add_argument(
        "--note",
        default="The dashboard summarizes only evidence files in the input directory.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    junit_paths, coverage_paths = discover_files(args.input_dir)
    summary = parse_junit(junit_paths)
    coverage = parse_coverage(coverage_paths)
    files = [*junit_paths, *coverage_paths]
    args.output_html.parent.mkdir(parents=True, exist_ok=True)
    args.output_svg.parent.mkdir(parents=True, exist_ok=True)
    args.output_html.write_text(
        render_html(
            title=args.title,
            scope=args.scope,
            note=args.note,
            summary=summary,
            coverage=coverage,
            files=files,
        ),
        encoding="utf-8",
    )
    args.output_svg.write_text(
        render_svg(title=args.title, scope=args.scope, summary=summary, coverage=coverage),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
