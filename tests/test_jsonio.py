import json
import math
from pathlib import Path

import pytest

from aspenops_nexus.errors import ValidationError
from aspenops_nexus.jsonio import (
    atomic_write_json,
    ensure_json_array,
    ensure_json_object,
    json_text,
    read_json_object,
    strict_json_loads,
    strict_json_object,
)


def test_duplicate_keys_and_nonfinite_numbers_are_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicate JSON key"):
        strict_json_object('{"x": 1, "x": 2}')
    for raw in ("NaN", "Infinity", "-Infinity", "1e9999"):
        with pytest.raises(ValidationError, match="non-finite"):
            strict_json_loads(raw)


def test_json_limits_are_enforced() -> None:
    with pytest.raises(ValidationError, match="nesting depth"):
        strict_json_loads('[[[0]]]', max_depth=2)
    with pytest.raises(ValidationError, match="node count"):
        strict_json_loads('[0, 1, 2]', max_nodes=3)
    with pytest.raises(ValidationError, match="string longer"):
        strict_json_loads('"abcd"', max_string_chars=3)
    with pytest.raises(ValidationError, match="numeric literal"):
        strict_json_loads("12345", max_number_chars=4)


def test_utf8_bom_is_accepted_but_invalid_utf8_is_rejected() -> None:
    assert strict_json_object(b"\xef\xbb\xbf{\"x\": 1}") == {"x": 1}
    with pytest.raises(ValidationError, match="UTF-8"):
        strict_json_loads(b"\xff")


def test_root_and_in_memory_shapes_are_strict() -> None:
    with pytest.raises(ValidationError, match="root"):
        strict_json_object("[]")
    with pytest.raises(ValidationError, match="object"):
        ensure_json_object([], name="request")
    with pytest.raises(ValidationError, match="array"):
        ensure_json_array({}, name="points")
    with pytest.raises(ValidationError, match="non-finite"):
        ensure_json_object({"x": math.nan}, name="request")


def test_read_json_object_rejects_size_and_symbolic_links(tmp_path: Path) -> None:
    source = tmp_path / "request.json"
    source.write_text('{"x": 1}', encoding="utf-8")
    assert read_json_object(source, max_bytes=100) == {"x": 1}
    with pytest.raises(ValidationError, match="maximum"):
        read_json_object(source, max_bytes=1)

    link = tmp_path / "request-link.json"
    link.symlink_to(source)
    with pytest.raises(ValidationError, match="symbolic-link"):
        read_json_object(link, max_bytes=100)


def test_atomic_json_write_is_complete_and_can_refuse_overwrite(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "result.json"
    atomic_write_json(target, {"b": 2, "a": 1}, overwrite=False)
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 1, "b": 2}
    assert not list(target.parent.glob("*.tmp"))
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        atomic_write_json(target, {"a": 2}, overwrite=False)


def test_json_serialization_never_falls_back_to_stringification() -> None:
    with pytest.raises(TypeError):
        json_text({"path": Path("secret")})
    with pytest.raises(ValueError):
        json_text({"x": math.nan})
