import copy
import math

import pytest

from aspenops_nexus.hashing import canonical_hash, canonical_json


def test_hash_is_independent_of_mapping_order() -> None:
    left = {"b": [2, 3], "a": {"x": 1}}
    right = {"a": {"x": 1}, "b": [2, 3]}
    assert canonical_hash(left) == canonical_hash(right)


def test_hash_is_stable_across_copy() -> None:
    value = {"model": "case.bkp", "inputs": [{"value": 1.25, "unit": "bar"}]}
    assert canonical_hash(value) == canonical_hash(copy.deepcopy(value))


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_nonfinite_values_are_rejected(value: float) -> None:
    with pytest.raises(ValueError):
        canonical_hash({"value": value})


def test_canonical_json_is_compact_and_utf8_preserving() -> None:
    assert canonical_json({"β": 2, "a": 1}) == '{"a":1,"β":2}'
