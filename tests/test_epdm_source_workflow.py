from __future__ import annotations

import ast
import hashlib
import io
import json
import textwrap
from pathlib import Path
from types import ModuleType, SimpleNamespace
from urllib.request import Request

import pytest

WORKFLOW = Path(".github/workflows/epdm-public-source-download.yml")


@pytest.fixture
def source_code() -> ModuleType:
    text = WORKFLOW.read_text(encoding="utf-8")
    code = textwrap.dedent(
        text.split("python3 - <<'PYTHON'\n", 1)[1].split("\n          PYTHON", 1)[0]
    )
    tree = ast.parse(code)
    module = ModuleType("epdm_workflow_contract")
    # The inline utility is imported without executing its guarded main or any network call.
    exec(compile(tree, str(WORKFLOW), "exec"), module.__dict__)
    return module


def test_utility_has_an_isolated_bounded_read_only_contract() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "branches: [main]" in text
    assert "paths: ['.github/workflows/epdm-public-source-download.yml']" in text
    assert '"$GITHUB_REF" != "refs/heads/main"' in text
    assert "set -euo pipefail" in text
    assert "permissions:\n  contents: read" in text
    assert "runs-on: ubuntu-24.04" in text
    assert "timeout-minutes: 8" in text
    assert "actions/checkout@" not in text
    assert "secrets." not in text and "github.token" not in text
    assert "${{ inputs." not in text and "self-hosted" not in text
    assert "if: always()" in text and "if-no-files-found: error" in text
    assert "name: epdm-public-originals-${{ github.run_id }}-${{ github.run_attempt }}" in text
    assert "retention-days: 1" in text


def test_source_inventory_and_limits_are_preserved(source_code: ModuleType) -> None:
    assert len(source_code.SOURCES) == 19
    assert len({name for name, _ in source_code.SOURCES}) == 19
    assert source_code.LIMIT == 35 * 1024 * 1024
    assert source_code.MAX_CANDIDATES == 3
    assert source_code.SourceRedirects.max_redirections == 3
    assert source_code.SourceRedirects.max_repeats == 2
    for _, url in source_code.SOURCES:
        source_code.validate_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://www.dow.com/source.pdf",
        "file:///etc/hosts",
        "https://unlisted.example/source.pdf",
        "https://www.dow.com.unlisted.example/source.pdf",
        "https://user:password@www.dow.com/source.pdf",
        "https://www.dow.com:8443/source.pdf",
        "https://www.dow.com:invalid/source.pdf",
        "https://www.dow.com/\nsource.pdf",
        "/source.pdf",
        "https://www.dow.com/" + "a" * 8192,
        None,
    ],
)
def test_disallowed_urls_fail_before_open(
    source_code: ModuleType, monkeypatch: pytest.MonkeyPatch, url: object
) -> None:
    calls: list[object] = []
    monkeypatch.setattr(source_code, "build_opener", lambda *args: calls.append(args))
    with pytest.raises(ValueError):
        source_code.get(url)
    assert not calls


@pytest.mark.parametrize("code", [301, 302, 303, 307, 308])
def test_redirect_checks_next_hop_before_request_creation(
    source_code: ModuleType, code: int
) -> None:
    handler = source_code.SourceRedirects()
    request = Request("https://www.dow.com/start")
    with pytest.raises(ValueError, match="allowlist"):
        handler.redirect_request(
            request, None, code, "redirect", {}, "https://unlisted.example/pdf"
        )
    allowed = handler.redirect_request(
        request, None, code, "redirect", {}, "https://www.dow.com/end.pdf"
    )
    assert allowed.full_url == "https://www.dow.com/end.pdf"


@pytest.mark.parametrize("count,accepted", [(4, True), (5, False)])
def test_response_read_is_bounded_and_closed(
    source_code: ModuleType, monkeypatch: pytest.MonkeyPatch, count: int, accepted: bool
) -> None:
    reads: list[int] = []

    class Response(io.BytesIO):
        url = "https://www.dow.com/source.pdf"
        headers = {"Content-Type": "application/pdf"}

        def read(self, size: int = -1) -> bytes:
            reads.append(size)
            return super().read(size)

    response = Response(b"x" * count)
    calls: list[int] = []

    def open_response(request: Request, *, timeout: int) -> Response:
        assert request.full_url == response.url
        calls.append(timeout)
        return response

    def opener(handler: object) -> SimpleNamespace:
        assert isinstance(handler, source_code.SourceRedirects)
        return SimpleNamespace(open=open_response)

    monkeypatch.setattr(source_code, "LIMIT", 4)
    monkeypatch.setattr(source_code, "build_opener", opener)
    if accepted:
        assert source_code.get(response.url)[0] == b"xxxx"
    else:
        with pytest.raises(ValueError, match="size limit"):
            source_code.get(response.url)
    assert calls == [35] and reads == [5] and response.closed


def test_html_candidates_are_bounded_unique_and_handle_empty_attributes(
    source_code: ModuleType,
) -> None:
    parser = source_code.Links()
    parser.feed('<meta name><meta name="citation_pdf_url" content><a href>')
    parser.feed('<meta name="citation_pdf_url" content="first.pdf">' * 20)
    for index in range(30):
        parser.feed(f'<a href="EPDM-{index}.pdf">link</a>')
    assert parser.pdfs == ["first.pdf", "EPDM-0.pdf", "EPDM-1.pdf"]


def test_exact_download_bytes_and_digest_are_recorded(
    source_code: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    payload = b"%PDF-1.4\n% synthetic bytes; no scientific content\n"
    monkeypatch.setattr(source_code, "ROOT", tmp_path)
    monkeypatch.setattr(source_code, "get", lambda url: (payload, url, "application/pdf"))
    result = source_code.one(("TEST", "https://www.dow.com/fixture.pdf"))
    assert result["status"] == "downloaded"
    assert result["sha256"] == hashlib.sha256(payload).hexdigest()
    assert result["bytes"] == len(payload)
    assert (tmp_path / "TEST.pdf").read_bytes() == payload


def test_failed_candidates_do_not_create_surrogate_pdfs(
    source_code: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    html = b'<meta name="citation_pdf_url" content="https://unlisted.example/file.pdf">'
    calls: list[str] = []

    def get(url: str) -> tuple[bytes, str, str]:
        calls.append(url)
        source_code.validate_url(url)
        return html, url, "text/html"

    monkeypatch.setattr(source_code, "ROOT", tmp_path)
    monkeypatch.setattr(source_code, "get", get)
    result = source_code.one(("TEST", "https://www.dow.com/start"))
    assert result["status"] == "failed" and "allowlist" in result["error"]
    assert len(calls) == 2
    assert (tmp_path / "TEST.html").read_bytes() == html
    assert not list(tmp_path.glob("*.pdf"))


@pytest.mark.parametrize(
    "statuses,expected,exit_code",
    [
        (["failed", "failed"], "FAILED", 1),
        (["downloaded", "failed"], "PARTIAL", 0),
        (["downloaded", "downloaded"], "COMPLETE", 0),
    ],
)
def test_summary_does_not_confuse_partial_or_total_failure_with_completion(
    source_code: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    statuses: list[str],
    expected: str,
    exit_code: int,
) -> None:
    monkeypatch.setattr(source_code, "ROOT", tmp_path)
    monkeypatch.setattr(source_code, "SOURCES", list(enumerate(statuses)))
    monkeypatch.setattr(source_code, "one", lambda source: {"id": source[0], "status": source[1]})
    assert source_code.main() == exit_code
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["status"] == expected
    assert summary["downloaded"] == statuses.count("downloaded")
    assert summary["failed"] + summary["downloaded"] == summary["sources"] == len(manifest)
    assert summary["scientific_validation"] == "NOT_EVALUATED"
