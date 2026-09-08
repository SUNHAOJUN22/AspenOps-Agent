from __future__ import annotations

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
