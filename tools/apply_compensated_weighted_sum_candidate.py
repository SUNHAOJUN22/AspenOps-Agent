from __future__ import annotations

from pathlib import Path
from textwrap import dedent


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one patch target in {path}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def normalize_generated_benchmarks() -> None:
    """Repair source text emitted through nested triple-quoted generator strings."""
    for path in (
        Path("scripts/benchmark_result_deepcopy.py"),
        Path("scripts/benchmark_result_serialization.py"),
    ):
        text = path.read_text(encoding="utf-8")
        broken_literal = '+ "' + "\n" + '",'
        escaped_literal = '+ "\\n",'
        text = text.replace(broken_literal, escaped_literal)
        first_line, remaining = text.split("\n", 1)
        path.write_text(first_line + "\n" + dedent(remaining), encoding="utf-8")


def patch_weighted_sum() -> None:
    path = Path("src/aspenops_nexus/optimization.py")
    replace_once(
        path,
        """    else:
        total = sum(terms)
        if math.isfinite(total):
            return total
    exact = sum(
""",
        """    else:
        try:
            total = math.fsum(terms)
        except OverflowError:
            pass
        else:
            if math.isfinite(total):
                return total
    exact = sum(
""",
    )


def write_regression_tests() -> None:
    path = Path("tests/test_weighted_sum_compensation.py")
    path.write_text(
        """from __future__ import annotations

import math
import sys

from aspenops_nexus.optimization import _finite_weighted_sum


def test_finite_weighted_sum_preserves_mixed_magnitude_contribution() -> None:
    assert _finite_weighted_sum(((1.0, 1e16), (1.0, 1.0), (1.0, -1e16))) == 1.0
    assert _finite_weighted_sum(((1.0, -1e16), (1.0, 1.0), (1.0, 1e16))) == 1.0


def test_finite_weighted_sum_keeps_ordinary_finite_semantics() -> None:
    pairs = ((0.5, 4.0), (2.0, -1.25), (1.5, 3.0))
    assert math.isclose(_finite_weighted_sum(pairs), math.fsum(w * v for w, v in pairs))


def test_finite_weighted_sum_retains_exact_overflow_saturation() -> None:
    assert _finite_weighted_sum(((2.0, 1e308), (2.0, 1e308))) == sys.float_info.max
    assert _finite_weighted_sum(((-2.0, 1e308), (-2.0, 1e308))) == -sys.float_info.max
    assert _finite_weighted_sum(((2.0, 1e308), (-2.0, 1e308))) == 0.0
""",
        encoding="utf-8",
    )


def main() -> None:
    normalize_generated_benchmarks()
    patch_weighted_sum()
    write_regression_tests()


if __name__ == "__main__":
    main()
