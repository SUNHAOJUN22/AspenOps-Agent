from __future__ import annotations

import json
import math
import os
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .errors import ValidationError

DEFAULT_MAX_JSON_DEPTH = 64
DEFAULT_MAX_JSON_NODES = 100_000
DEFAULT_MAX_STRING_CHARS = 1_000_000
DEFAULT_MAX_NUMBER_CHARS = 128


def _positive_int(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be an integer >= 1")
    return value


def _number_parser(
    name: str,
    max_chars: int,
    *,
    integer: bool,
) -> Callable[[str], int | float]:
    def parse(text: str) -> int | float:
        if len(text) > max_chars:
            raise ValidationError(
                f"{name} contains a numeric literal longer than {max_chars} characters"
            )
        value: int | float = int(text) if integer else float(text)
        if isinstance(value, float) and not math.isfinite(value):
            raise ValidationError(f"{name} contains a non-finite numeric value")
        return value

    return parse


def _validate_tree(
    value: Any,
    *,
    name: str,
    max_depth: int,
    max_nodes: int,
    max_string_chars: int,
) -> None:
    stack: list[tuple[Any, int, str]] = [(value, 0, name)]
    nodes = 0
    while stack:
        current, depth, location = stack.pop()
        nodes += 1
        if nodes > max_nodes:
            raise ValidationError(f"{name} exceeds the maximum node count {max_nodes}")
        if isinstance(current, dict):
            if depth >= max_depth and current:
                raise ValidationError(f"{name} exceeds the maximum nesting depth {max_depth}")
            for key, item in current.items():
                if not isinstance(key, str):
                    raise ValidationError(f"{location} contains a non-string object key")
                if len(key) > max_string_chars:
                    raise ValidationError(
                        f"{location} contains an object key longer than "
                        f"{max_string_chars} characters"
                    )
                stack.append((item, depth + 1, f"{location}.{key}"))
        elif isinstance(current, list):
            if depth >= max_depth and current:
                raise ValidationError(f"{name} exceeds the maximum nesting depth {max_depth}")
            for index, item in enumerate(current):
                stack.append((item, depth + 1, f"{location}[{index}]"))
        elif isinstance(current, str):
            if len(current) > max_string_chars:
                raise ValidationError(
                    f"{location} contains a string longer than {max_string_chars} characters"
                )
        elif current is None or isinstance(current, bool | int):
            continue
        elif isinstance(current, float):
            if not math.isfinite(current):
                raise ValidationError(f"{location} contains a non-finite number")
        else:
            raise ValidationError(
                f"{location} contains unsupported JSON type {type(current).__name__}"
            )


def strict_json_loads(
    raw: bytes | str,
    *,
    name: str = "JSON",
    max_depth: int = DEFAULT_MAX_JSON_DEPTH,
    max_nodes: int = DEFAULT_MAX_JSON_NODES,
    max_string_chars: int = DEFAULT_MAX_STRING_CHARS,
    max_number_chars: int = DEFAULT_MAX_NUMBER_CHARS,
) -> Any:
    depth_limit = _positive_int(max_depth, "max_depth")
    node_limit = _positive_int(max_nodes, "max_nodes")
    string_limit = _positive_int(max_string_chars, "max_string_chars")
    number_limit = _positive_int(max_number_chars, "max_number_chars")
    if isinstance(raw, bytes):
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValidationError(f"{name} must be UTF-8 JSON") from exc
    elif isinstance(raw, str):
        text = raw
    else:
        raise TypeError("raw JSON must be bytes or str")

    def reject_constant(value: str) -> None:
        raise ValidationError(f"{name} contains non-finite JSON constant {value!r}")

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for key, value in pairs:
            if key in output:
                raise ValidationError(f"{name} contains duplicate JSON key {key!r}")
            output[key] = value
        return output

    try:
        value = json.loads(
            text,
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_constant,
            parse_float=_number_parser(name, number_limit, integer=False),
            parse_int=_number_parser(name, number_limit, integer=True),
        )
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{name} is not valid JSON: {exc}") from exc
    _validate_tree(
        value,
        name=name,
        max_depth=depth_limit,
        max_nodes=node_limit,
        max_string_chars=string_limit,
    )
    return value


def strict_json_object(
    raw: bytes | str,
    *,
    name: str = "JSON",
    max_depth: int = DEFAULT_MAX_JSON_DEPTH,
    max_nodes: int = DEFAULT_MAX_JSON_NODES,
    max_string_chars: int = DEFAULT_MAX_STRING_CHARS,
    max_number_chars: int = DEFAULT_MAX_NUMBER_CHARS,
) -> dict[str, Any]:
    value = strict_json_loads(
        raw,
        name=name,
        max_depth=max_depth,
        max_nodes=max_nodes,
        max_string_chars=max_string_chars,
        max_number_chars=max_number_chars,
    )
    if not isinstance(value, dict):
        raise ValidationError(f"{name} root must be a JSON object")
    return value


def read_json_object(
    path: str | Path,
    *,
    max_bytes: int,
    max_depth: int = DEFAULT_MAX_JSON_DEPTH,
    max_nodes: int = DEFAULT_MAX_JSON_NODES,
    max_string_chars: int = DEFAULT_MAX_STRING_CHARS,
    max_number_chars: int = DEFAULT_MAX_NUMBER_CHARS,
) -> dict[str, Any]:
    byte_limit = _positive_int(max_bytes, "max_bytes")
    source = Path(path).expanduser()
    if source.is_symlink():
        raise ValidationError(f"Refusing symbolic-link JSON input: {source}")
    source = source.resolve()
    if not source.is_file():
        raise ValidationError(f"JSON input is not a regular file: {source}")
    with source.open("rb") as handle:
        size = os.fstat(handle.fileno()).st_size
        if size > byte_limit:
            raise ValidationError(f"{source} is {size} bytes; maximum is {byte_limit} bytes")
        raw = handle.read(byte_limit + 1)
    if len(raw) > byte_limit:
        raise ValidationError(f"{source} grew beyond the maximum {byte_limit} bytes while reading")
    return strict_json_object(
        raw,
        name=str(source),
        max_depth=max_depth,
        max_nodes=max_nodes,
        max_string_chars=max_string_chars,
        max_number_chars=max_number_chars,
    )


def json_text(value: Any, *, indent: int | None = 2) -> str:
    return json.dumps(
        value,
        indent=indent,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=None if indent is not None else (",", ":"),
    )


def json_bytes(value: Any, *, indent: int | None = 2) -> bytes:
    return (json_text(value, indent=indent) + "\n").encode("utf-8")


def atomic_write_bytes(
    path: str | Path,
    payload: bytes,
    *,
    overwrite: bool = True,
    mode: int = 0o600,
) -> Path:
    if not isinstance(payload, bytes):
        raise TypeError("payload must be bytes")
    if isinstance(mode, bool) or not isinstance(mode, int) or not 0 <= mode <= 0o777:
        raise ValueError("mode must be an integer between 0 and 0o777")
    target = Path(path).expanduser()
    if target.is_symlink():
        raise ValidationError(f"Refusing symbolic-link output target: {target}")
    target = target.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing file: {target}")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
    )
    temporary = Path(temporary_name)
    descriptor_open = True
    try:
        if os.name != "nt":
            os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            descriptor_open = False
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if overwrite:
            os.replace(temporary, target)
        else:
            try:
                os.link(temporary, target)
            except FileExistsError as exc:
                raise FileExistsError(f"Refusing to overwrite existing file: {target}") from exc
            temporary.unlink()
        if os.name != "nt":
            directory_descriptor = os.open(target.parent, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
        return target
    finally:
        if descriptor_open:
            os.close(descriptor)
        if temporary.exists():
            temporary.unlink()


def atomic_write_json(
    path: str | Path,
    value: Any,
    *,
    overwrite: bool = True,
    indent: int | None = 2,
) -> Path:
    return atomic_write_bytes(
        path,
        json_bytes(value, indent=indent),
        overwrite=overwrite,
    )


def ensure_json_object(value: Any, *, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{name} must be a JSON object")
    output: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValidationError(f"{name} keys must be strings")
        output[key] = item
    _validate_tree(
        output,
        name=name,
        max_depth=DEFAULT_MAX_JSON_DEPTH,
        max_nodes=DEFAULT_MAX_JSON_NODES,
        max_string_chars=DEFAULT_MAX_STRING_CHARS,
    )
    return output


def ensure_json_array(value: Any, *, name: str) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        raise ValidationError(f"{name} must be a JSON array")
    output = list(value)
    _validate_tree(
        output,
        name=name,
        max_depth=DEFAULT_MAX_JSON_DEPTH,
        max_nodes=DEFAULT_MAX_JSON_NODES,
        max_string_chars=DEFAULT_MAX_STRING_CHARS,
    )
    return output
