from __future__ import annotations

from pathlib import Path


def main() -> None:
    path = Path("tests/test_small_logic_edges.py")
    text = path.read_text(encoding="utf-8")
    old = '''    assert {item["key"] for item in report["comparisons"]} == {
        "__ok__",
        "label",
        "only_candidate",
        "only_reference",
        "x",
    }
'''
    new = '''    comparison_keys = {item["key"] for item in report["comparisons"]}
    assert {
        "__ok__",
        "__communication_ok__",
        "__engine_ok__",
        "__converged__",
        "__feasible__",
        "__units__",
        "__violations__",
        "__request_hash__",
        "label",
        "only_candidate",
        "only_reference",
        "x",
    } == comparison_keys
'''
    if new in text:
        return
    if old not in text:
        raise RuntimeError("Certification comparison assertion marker is missing")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


if __name__ == "__main__":
    main()
