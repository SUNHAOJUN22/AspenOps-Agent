from __future__ import annotations

import math

import pytest

from aspenops_nexus.hashing import canonical_hash


def test_canonical_hash_is_order_independent() -> None:
    assert canonical_hash({"b": 2, "a": 1}) == canonical_hash({"a": 1, "b": 2})


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_canonical_hash_rejects_nonfinite_values(value: float) -> None:
    with pytest.raises(ValueError):
        canonical_hash({"value": value})
