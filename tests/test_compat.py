from aspenops_nexus.compat import (
    discover_aspen_plus_candidates,
    discover_hysys_candidates,
    parse_numeric_version,
)


def test_numeric_version_parser_is_marketing_version_agnostic() -> None:
    assert parse_numeric_version("Apwn.Document.40.0") == (40, 0)
    assert parse_numeric_version("Apwn.Document.39") == (39,)
    assert parse_numeric_version("Apwn.Document") == ()


def test_pinned_progids_override_discovery(monkeypatch) -> None:
    monkeypatch.setenv("ASPENOPS_PROGID", "Apwn.Document.99.0")
    monkeypatch.setenv("ASPENOPS_HYSYS_PROGID", "HYSYS.Application.99")
    assert discover_aspen_plus_candidates()[0].progid == "Apwn.Document.99.0"
    assert discover_aspen_plus_candidates()[0].pinned
    assert discover_hysys_candidates()[0].progid == "HYSYS.Application.99"


def test_non_windows_discovery_keeps_unversioned_fallback(monkeypatch) -> None:
    monkeypatch.delenv("ASPENOPS_PROGID", raising=False)
    monkeypatch.delenv("ASPENOPS_HYSYS_PROGID", raising=False)
    assert discover_aspen_plus_candidates()[-1].progid == "Apwn.Document"
    assert discover_hysys_candidates()[-1].progid == "HYSYS.Application"
