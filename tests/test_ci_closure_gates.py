from __future__ import annotations

from pathlib import Path

from scripts.run_test_order_gate import _random_order, _reverse_order

ROOT = Path(__file__).resolve().parents[1]
CI = ROOT / ".github" / "workflows" / "ci.yml"
ORDER_GATE = ROOT / "scripts" / "run_test_order_gate.py"


def test_order_helpers_are_deterministic_and_non_mutating() -> None:
    original = ["a::test_one", "b::test_two", "c::test_three", "d::test_four"]

    assert _reverse_order(original) == list(reversed(original))
    assert _random_order(original, 20260728) == _random_order(original, 20260728)
    assert sorted(_random_order(original, 20260728)) == sorted(original)
    assert original == ["a::test_one", "b::test_two", "c::test_three", "d::test_four"]


def test_ci_has_fail_closed_exact_bandit_gate() -> None:
    text = CI.read_text(encoding="utf-8")

    assert "Bandit security analysis" in text
    assert "bandit==1.9.4" in text
    assert "--isolated" in text
    assert "--recursive src scripts" in text
    assert "--severity-level high" in text
    assert "--confidence-level high" in text
    assert "--format json" in text
    assert "var/ci/bandit.json" in text
    assert "python -m json.tool var/ci/bandit.json" in text
    assert "--exit-zero" not in text


def test_ci_runs_complete_reverse_and_seeded_random_order_gate() -> None:
    workflow = CI.read_text(encoding="utf-8")
    script = ORDER_GATE.read_text(encoding="utf-8")

    assert "Verify complete-suite order independence" in workflow
    assert "matrix.python-version == '3.12'" in workflow
    assert "scripts/run_test_order_gate.py" in workflow
    assert "--seed 20260728" in workflow
    assert "--output-dir var/ci" in workflow
    assert "--collect-only" in script
    assert "error::ResourceWarning" in script
    assert 'label="reverse"' in script
    assert 'label=f"random-{args.seed}"' in script
