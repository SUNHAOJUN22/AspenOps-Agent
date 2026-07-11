import pytest

from aspenops.compat import ProgIdInfo, candidate_progids, order_progids, parse_progid
from aspenops.errors import CompatibilityError


def test_parse_and_order_progids(monkeypatch: pytest.MonkeyPatch) -> None:
    items = [
        parse_progid("Apwn.Document.40.0", "32-bit"),
        parse_progid("Apwn.Document.42.1", "64-bit"),
        parse_progid("Apwn.Document", "64-bit"),
        ProgIdInfo("Apwn.Document.40.0", 40, 0, "64-bit"),
    ]
    ordered = order_progids(items)
    assert [item.progid for item in ordered] == [
        "Apwn.Document.42.1",
        "Apwn.Document.40.0",
        "Apwn.Document",
    ]
    assert ordered[1].registry_view == "64-bit"

    monkeypatch.setenv("ASPENOPS_PROGID", "Apwn.Document.99.0")
    assert candidate_progids() == ["Apwn.Document.99.0", "Apwn.Document"]


def test_invalid_progid() -> None:
    with pytest.raises(CompatibilityError):
        parse_progid("HYSYS.Application")
