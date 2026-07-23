from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return {str(key): item for key, item in value.items()}


def _array(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a JSON array")
    return value


def _integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _boolean(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be a boolean")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _load_report(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    payload = _object(value, "process IR report")
    report = _object(payload.get("report"), "process IR report.report")
    counts = _object(report.get("counts"), "process IR report.report.counts")
    issues = _array(report.get("issues"), "process IR report.report.issues")
    backends = _array(payload.get("backends"), "process IR report.backends")
    pipeline = _array(payload.get("agent_pipeline"), "process IR report.agent_pipeline")
    normalized_counts = {
        key: _integer(counts.get(key), f"counts.{key}")
        for key in ("components", "units", "streams", "ports", "parameters")
    }
    normalized_issues: list[dict[str, str]] = []
    for index, raw_issue in enumerate(issues):
        issue = _object(raw_issue, f"issues[{index}]")
        normalized_issues.append(
            {
                "severity": _text(issue.get("severity"), f"issues[{index}].severity"),
                "code": _text(issue.get("code"), f"issues[{index}].code"),
                "path": _text(issue.get("path"), f"issues[{index}].path"),
                "message": _text(issue.get("message"), f"issues[{index}].message"),
            }
        )
    normalized_backends: list[dict[str, Any]] = []
    for index, raw_backend in enumerate(backends):
        backend = _object(raw_backend, f"backends[{index}]")
        normalized_backends.append(
            {
                "backend": _text(backend.get("backend"), f"backends[{index}].backend"),
                "execution": _text(
                    backend.get("execution"),
                    f"backends[{index}].execution",
                ),
                "ir_compiler": _text(
                    backend.get("ir_compiler"),
                    f"backends[{index}].ir_compiler",
                ),
                "requires_license": _boolean(
                    backend.get("requires_license"),
                    f"backends[{index}].requires_license",
                ),
            }
        )
    normalized_pipeline: list[dict[str, str]] = []
    for index, raw_stage in enumerate(pipeline):
        stage = _object(raw_stage, f"agent_pipeline[{index}]")
        normalized_pipeline.append(
            {
                "id": _text(stage.get("id"), f"agent_pipeline[{index}].id"),
                "responsibility": _text(
                    stage.get("responsibility"),
                    f"agent_pipeline[{index}].responsibility",
                ),
                "permitted_output": _text(
                    stage.get("permitted_output"),
                    f"agent_pipeline[{index}].permitted_output",
                ),
            }
        )
    return {
        "name": _text(payload.get("name"), "process IR report.name"),
        "schema": _text(payload.get("schema"), "process IR report.schema"),
        "valid": _boolean(report.get("valid"), "process IR report.report.valid"),
        "digest": _text(report.get("digest"), "process IR report.report.digest"),
        "counts": normalized_counts,
        "issues": normalized_issues,
        "backends": normalized_backends,
        "pipeline": normalized_pipeline,
    }


def _styles(status_color: str) -> str:
    return "\n".join(
        [
            ":root { color-scheme:light dark; --accent:#2563eb; }",
            "* { box-sizing:border-box; }",
            "body { margin:0; font-family:system-ui,-apple-system,Segoe UI,sans-serif; }",
            "body { background:#f4f6f8; color:#17202a; }",
            "main { max-width:1080px; margin:auto; padding:28px; }",
            "header { display:flex; justify-content:space-between; gap:20px; }",
            "h1 { margin:0 0 6px; font-size:28px; }",
            ".badge { border-radius:999px; padding:8px 13px; font-weight:700; }",
            f".badge {{ background:{status_color}; color:white; }}",
            ".metrics { display:grid; gap:12px; margin:22px 0; }",
            ".metrics { grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); }",
            ".metric,.panel,.node { background:white; border:1px solid #dbe2e8; }",
            ".metric,.panel,.node { border-radius:14px; padding:16px; }",
            ".panel { margin:14px 0; }",
            ".metric-label,.metric-note,small { color:#5b6770; font-size:13px; }",
            ".metric-value { font-size:28px; font-weight:750; margin:4px 0; }",
            ".tabs { display:flex; gap:8px; flex-wrap:wrap; }",
            "button { border:1px solid #cbd5df; background:white; border-radius:10px; }",
            "button { padding:9px 12px; cursor:pointer; }",
            "button[aria-pressed='true'] { background:var(--accent); color:white; }",
            ".hidden { display:none; }",
            ".grid { display:grid; gap:12px; }",
            ".grid { grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); }",
            "table { width:100%; border-collapse:collapse; }",
            "th,td { border-bottom:1px solid #dbe2e8; padding:9px; text-align:left; }",
            "code { word-break:break-all; }",
            "@media (prefers-color-scheme:dark) {",
            " body { background:#111827; color:#e5e7eb; }",
            " .metric,.panel,.node,button { background:#18212f; border-color:#334155; }",
            " .metric,.panel,.node,button { color:#e5e7eb; }",
            " .metric-label,.metric-note,small { color:#a8b3c0; }",
            " th,td { border-color:#334155; }",
            "}",
        ]
    )


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


def render_html(data: dict[str, Any]) -> str:
    valid = bool(data["valid"])
    issues = list(data["issues"])
    errors = sum(item["severity"] == "error" for item in issues)
    warnings = sum(item["severity"] == "warning" for item in issues)
    status = "VALID" if valid else "INVALID"
    status_color = "#15803d" if valid else "#b91c1c"
    counts = data["counts"]
    metrics = "".join(
        [
            _metric("Components", str(counts["components"]), "Declared chemicals"),
            _metric("Units", str(counts["units"]), "Unit operations"),
            _metric("Streams", str(counts["streams"]), "Directed connections"),
            _metric("Errors / warnings", f"{errors} / {warnings}", "Validation findings"),
        ]
    )
    issue_rows = "".join(
        "<tr>"
        f"<td>{html.escape(item['severity'])}</td>"
        f"<td><code>{html.escape(item['code'])}</code></td>"
        f"<td><code>{html.escape(item['path'])}</code></td>"
        f"<td>{html.escape(item['message'])}</td>"
        "</tr>"
        for item in issues
    )
    issue_rows = issue_rows or '<tr><td colspan="4">No validation issues.</td></tr>'
    backend_rows = "".join(
        "<tr>"
        f"<td>{html.escape(item['backend'])}</td>"
        f"<td>{html.escape(item['execution'])}</td>"
        f"<td>{html.escape(item['ir_compiler'])}</td>"
        f"<td>{'yes' if item['requires_license'] else 'no'}</td>"
        "</tr>"
        for item in data["backends"]
    )
    pipeline_nodes = "".join(
        '<section class="node">'
        f"<strong>{html.escape(item['id'])}</strong>"
        f"<p>{html.escape(item['responsibility'])}</p>"
        f"<small>Output: {html.escape(item['permitted_output'])}</small>"
        "</section>"
        for item in data["pipeline"]
    )
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width,initial-scale=1">',
            f"<title>{html.escape(data['name'])} IR dashboard</title>",
            "<style>",
            _styles(status_color),
            "</style>",
            "</head>",
            "<body><main>",
            "<header>",
            f"<div><h1>{html.escape(data['name'])}</h1>",
            f"<p>Schema <code>{html.escape(data['schema'])}</code></p></div>",
            f'<div class="badge">{status}</div>',
            "</header>",
            f'<div class="metrics">{metrics}</div>',
            '<div class="tabs" role="group" aria-label="IR dashboard sections">',
            '<button type="button" data-target="issues" aria-pressed="true">Issues</button>',
            '<button type="button" data-target="backends" aria-pressed="false">Backends</button>',
            '<button type="button" data-target="pipeline" aria-pressed="false">',
            "Agent pipeline</button>",
            "</div>",
            '<section id="issues" class="panel">',
            "<h2>Validation issues</h2>",
            "<table><thead><tr><th>Severity</th><th>Code</th><th>Path</th>",
            f"<th>Message</th></tr></thead><tbody>{issue_rows}</tbody></table></section>",
            '<section id="backends" class="panel hidden">',
            "<h2>Backend capability declaration</h2>",
            "<table><thead><tr><th>Backend</th><th>Execution</th>",
            "<th>IR compiler</th><th>License</th></tr></thead>",
            f"<tbody>{backend_rows}</tbody></table>",
            "<p>No planned compiler is represented as implemented.</p></section>",
            '<section id="pipeline" class="panel hidden">',
            f'<h2>Bounded Agent stages</h2><div class="grid">{pipeline_nodes}</div></section>',
            '<section class="panel"><strong>Digest:</strong> ',
            f"<code>{html.escape(data['digest'])}</code></section>",
            "<small>Generated from validated AspenOps process intent evidence. ",
            "No network resources.</small>",
            "</main>",
            "<script>",
            "const buttons=document.querySelectorAll('button[data-target]');",
            "buttons.forEach((button)=>button.addEventListener('click',()=>{",
            " buttons.forEach((item)=>item.setAttribute('aria-pressed',String(item===button)));",
            " document.querySelectorAll('main > section[id]').forEach((section)=>",
            "  section.classList.add('hidden'));",
            " document.getElementById(button.dataset.target).classList.remove('hidden');",
            "}));",
            "</script></body></html>",
        ]
    )


def render_svg(data: dict[str, Any]) -> str:
    valid = bool(data["valid"])
    issues = list(data["issues"])
    errors = sum(item["severity"] == "error" for item in issues)
    warnings = sum(item["severity"] == "warning" for item in issues)
    status = "VALID" if valid else "INVALID"
    status_color = "#15803d" if valid else "#b91c1c"
    counts = data["counts"]
    execution_available = sum(
        item["execution"] == "available" for item in data["backends"]
    )
    compilers_available = sum(
        item["ir_compiler"] == "available" for item in data["backends"]
    )
    values = [
        ("Components", counts["components"]),
        ("Units", counts["units"]),
        ("Streams", counts["streams"]),
        ("Errors", errors),
        ("Warnings", warnings),
        ("Execution backends", execution_available),
        ("IR compilers", compilers_available),
    ]
    cards = []
    for index, (label, value) in enumerate(values):
        x = 55 + (index % 4) * 285
        y = 160 + (index // 4) * 155
        cards.extend(
            [
                f'<rect x="{x}" y="{y}" width="250" height="120" rx="16"',
                ' fill="#ffffff" stroke="#dbe2e8"/>',
                f'<text x="{x + 24}" y="{y + 38}" font-size="17" fill="#5b6770">',
                f"{html.escape(label)}</text>",
                f'<text x="{x + 24}" y="{y + 93}" font-size="46" font-weight="700">',
                f"{value}</text>",
            ]
        )
    return "\n".join(
        [
            '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="675"',
            ' viewBox="0 0 1200 675" role="img"',
            f' aria-label="{html.escape(data["name"])} process IR dashboard">',
            '<rect width="1200" height="675" fill="#f7f9fb"/>',
            '<g font-family="Arial, sans-serif" fill="#17202a">',
            '<text x="55" y="70" font-size="34" font-weight="700">',
            f"{html.escape(data['name'])}</text>",
            '<text x="55" y="108" font-size="18" fill="#5b6770">',
            f"{html.escape(data['schema'])}</text>",
            f'<rect x="1015" y="45" width="130" height="44" rx="22" fill="{status_color}"/>',
            '<text x="1080" y="74" text-anchor="middle" font-size="19"',
            f' font-weight="700" fill="#ffffff">{status}</text>',
            *cards,
            '<text x="55" y="610" font-size="16" fill="#5b6770">',
            "Execution availability and IR compiler availability are separate claims.</text>",
            '<text x="55" y="640" font-size="14" fill="#5b6770">',
            f"Digest: {html.escape(data['digest'])}</text>",
            "</g></svg>",
        ]
    )


def _write(path: str | Path, content: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render AspenOps process IR visual evidence")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-html", required=True)
    parser.add_argument("--output-svg", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    data = _load_report(args.input)
    _write(args.output_html, render_html(data))
    _write(args.output_svg, render_svg(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
