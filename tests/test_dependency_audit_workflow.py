from __future__ import annotations

from pathlib import Path


def test_dependency_audit_collects_every_target_before_failing() -> None:
    text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "UV_PREVIEW_FEATURES: json-output" in text
    assert "for platform in linux windows; do" in text
    assert "for version in 3.11 3.12 3.13; do" in text
    assert 'stem="var/ci/dependency-audit-${platform}-py${version}"' in text
    assert 'output="${stem}.json"' in text
    assert 'error_log="${stem}.log"' in text
    assert "audit_failed=0" in text
    assert "if ! uv audit --frozen" in text
    assert '> "$output" 2> "$error_log"' in text
    assert "if ! python -m json.tool \"$output\" >/dev/null" in text
    assert "audit_failed=1" in text
    assert "One or more locked dependency audits failed" in text
    assert text.index("for platform in linux windows; do") < text.index(
        'if [[ "$audit_failed" -ne 0 ]]'
    )
