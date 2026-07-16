from __future__ import annotations

import hashlib
import json
import math
import re
import string
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .units import UnitError, convert, dimension


class RegistryError(ValueError):
    pass


_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_. -]{1,128}$")
_IDENTIFIER_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
_VALID_BACKENDS = {"any", "mock", "aspen_plus", "hysys"}


@dataclass(frozen=True, slots=True)
class ResolvedNode:
    key: str
    access: str
    native_unit: str | None
    quantity: str | None
    paths: tuple[str, ...]
    identifiers: dict[str, str]
    lower: float | None
    upper: float | None
    integer: bool
    backend: str
    locator: dict[str, Any]
    verification: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class NodeRegistry:
    """Case-specific semantic allowlist.

    The registry is the security and reproducibility boundary between an agent and Aspen's mutable
    object tree. Paths are templates owned by the project, never strings invented by an LLM.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        raw = self.path.read_bytes()
        self.sha256 = hashlib.sha256(raw).hexdigest()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RegistryError(f"Invalid registry JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise RegistryError("Registry root must be an object")
        nodes = data.get("nodes", {})
        if not isinstance(nodes, dict) or not nodes:
            raise RegistryError("Registry must contain a non-empty 'nodes' object")
        self._nodes: dict[str, dict[str, Any]] = {}
        for key, value in nodes.items():
            if not isinstance(key, str) or not key.strip():
                raise RegistryError("Semantic keys must be non-empty strings")
            if not isinstance(value, dict):
                raise RegistryError(f"Registry node {key!r} must be an object")
            self._validate_definition(key, value)
            self._nodes[key] = dict(value)
        self.name = str(data.get("name", self.path.stem))
        self.version = str(data.get("version", "1.0"))
        self.schema = str(data.get("schema", "aspenops.registry/v1"))

    @staticmethod
    def _finite_bound(key: str, name: str, value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, bool):
            raise RegistryError(f"{name} bound for {key} must be numeric, not Boolean")
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise RegistryError(f"{name} bound for {key} must be numeric") from exc
        if not math.isfinite(numeric):
            raise RegistryError(f"{name} bound for {key} must be finite")
        return numeric

    @staticmethod
    def _validate_template(key: str, template: str, identifiers: tuple[str, ...]) -> None:
        try:
            parsed = tuple(string.Formatter().parse(template))
        except ValueError as exc:
            raise RegistryError(f"Invalid template for {key}: {template!r}") from exc
        for _literal, field_name, format_spec, conversion in parsed:
            if field_name is None:
                continue
            if field_name not in identifiers:
                raise RegistryError(
                    f"Template for {key} references undeclared identifier {field_name!r}"
                )
            if format_spec or conversion:
                raise RegistryError(
                    f"Template for {key} may only use plain identifier placeholders"
                )

    @classmethod
    def _validate_definition(cls, key: str, node: dict[str, Any]) -> None:
        access = str(node.get("access", "read"))
        if access not in {"read", "write", "readwrite"}:
            raise RegistryError(f"Invalid access for {key}: {access}")
        unit = None if node.get("unit") is None else str(node["unit"])
        quantity = None if node.get("quantity") is None else str(node["quantity"])
        unit_dimension = None if unit is None else dimension(unit)
        if quantity is not None:
            if not quantity.strip():
                raise RegistryError(f"Quantity for {key} must not be blank")
            if unit_dimension is None:
                raise RegistryError(f"Quantity {quantity!r} for {key} requires a canonical unit")
            if quantity != unit_dimension:
                raise RegistryError(
                    f"Quantity {quantity!r} for {key} does not match unit {unit!r} "
                    f"dimension {unit_dimension!r}"
                )
        lower = cls._finite_bound(key, "lower", node.get("lower"))
        upper = cls._finite_bound(key, "upper", node.get("upper"))
        if lower is not None and upper is not None and lower > upper:
            raise RegistryError(f"Lower bound exceeds upper bound for {key}")
        integer = node.get("integer", False)
        if not isinstance(integer, bool):
            raise RegistryError(f"integer for {key} must be a JSON Boolean")
        backend = str(node.get("backend", "aspen_plus"))
        if backend not in _VALID_BACKENDS:
            raise RegistryError(f"Invalid backend for {key}: {backend!r}")
        raw_identifiers = node.get("identifiers", [])
        if not isinstance(raw_identifiers, list) or not all(
            isinstance(item, str) for item in raw_identifiers
        ):
            raise RegistryError(f"identifiers for {key} must be a list of strings")
        identifiers = tuple(raw_identifiers)
        if len(set(identifiers)) != len(identifiers):
            raise RegistryError(f"identifiers for {key} must be unique")
        for identifier in identifiers:
            if not _IDENTIFIER_NAME_RE.fullmatch(identifier):
                raise RegistryError(f"Invalid identifier name {identifier!r} for {key}")
        paths = node.get("paths", [])
        locator = node.get("locator", {})
        if not paths and not locator:
            raise RegistryError(f"Node {key} requires at least one path or locator")
        if not isinstance(paths, list) or not all(isinstance(path, str) and path for path in paths):
            raise RegistryError(f"paths for {key} must be a list of non-empty strings")
        if not isinstance(locator, dict):
            raise RegistryError(f"locator for {key} must be an object")
        for path in paths:
            cls._validate_template(key, path, identifiers)
        for locator_key, locator_value in locator.items():
            if not isinstance(locator_key, str) or not locator_key:
                raise RegistryError(f"locator keys for {key} must be non-empty strings")
            if isinstance(locator_value, str):
                cls._validate_template(key, locator_value, identifiers)

    def keys(self) -> list[str]:
        return sorted(self._nodes)

    def describe(self) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        for key in self.keys():
            node = self._nodes[key]
            output.append(
                {
                    "key": key,
                    "access": node.get("access", "read"),
                    "unit": node.get("unit"),
                    "quantity": node.get("quantity"),
                    "identifiers": node.get("identifiers", []),
                    "lower": node.get("lower"),
                    "upper": node.get("upper"),
                    "integer": node.get("integer", False),
                    "backend": node.get("backend", "aspen_plus"),
                    "verification": node.get("verification", "project-required"),
                    "description": node.get("description", ""),
                }
            )
        return output

    @staticmethod
    def _validate_identifiers(identifiers: dict[str, str]) -> None:
        for name, value in identifiers.items():
            if not _IDENTIFIER_NAME_RE.fullmatch(name) or not _IDENTIFIER_RE.fullmatch(value):
                raise RegistryError(
                    f"Unsafe identifier {name!r}={value!r}; path separators and template syntax "
                    "are not allowed"
                )

    def resolve(self, key: str, identifiers: dict[str, str]) -> ResolvedNode:
        try:
            node = self._nodes[key]
        except KeyError as exc:
            raise RegistryError(f"Unknown semantic key: {key}") from exc
        normalized = {str(k): str(v) for k, v in identifiers.items()}
        self._validate_identifiers(normalized)
        required = tuple(str(x) for x in node.get("identifiers", []))
        missing = [name for name in required if name not in normalized]
        extra = [name for name in normalized if name not in required]
        if missing:
            raise RegistryError(f"Missing identifiers for {key}: {', '.join(missing)}")
        if extra:
            raise RegistryError(f"Unexpected identifiers for {key}: {', '.join(extra)}")
        try:
            paths = tuple(str(path).format(**normalized) for path in node.get("paths", []))
            locator = {
                str(k): (str(v).format(**normalized) if isinstance(v, str) else v)
                for k, v in dict(node.get("locator", {})).items()
            }
        except KeyError as exc:
            raise RegistryError(f"Unresolved identifier {exc.args[0]!r} for {key}") from exc
        return ResolvedNode(
            key=key,
            access=str(node.get("access", "read")),
            native_unit=None if node.get("unit") is None else str(node["unit"]),
            quantity=None if node.get("quantity") is None else str(node["quantity"]),
            paths=paths,
            identifiers=normalized,
            lower=self._finite_bound(key, "lower", node.get("lower")),
            upper=self._finite_bound(key, "upper", node.get("upper")),
            integer=node.get("integer", False),
            backend=str(node.get("backend", "aspen_plus")),
            locator=locator,
            verification=str(node.get("verification", "project-required")),
            description=str(node.get("description", "")),
        )

    def validate_backend(self, node: ResolvedNode, backend: str) -> None:
        if backend == "mock":
            return
        if node.backend not in {backend, "any"}:
            raise RegistryError(
                f"Semantic key {node.key} targets backend {node.backend!r}, not {backend!r}"
            )

    def validate_write(
        self,
        node: ResolvedNode,
        value: float | int | str | bool,
        unit: str | None,
    ) -> float | int | str | bool:
        if node.access not in {"write", "readwrite"}:
            raise RegistryError(f"Semantic key is read-only: {node.key}")
        if isinstance(value, bool | str):
            if node.native_unit is not None:
                value_type = type(value).__name__
                raise RegistryError(f"Numeric variable {node.key} cannot receive {value_type}")
            return value
        try:
            numeric = convert(float(value), unit, node.native_unit)
        except UnitError as exc:
            raise RegistryError(f"Invalid unit for {node.key}: {exc}") from exc
        if node.integer:
            rounded = round(numeric)
            if not math.isclose(numeric, rounded, rel_tol=0.0, abs_tol=1e-9):
                raise RegistryError(f"{node.key} requires an integer value")
            numeric = float(rounded)
        if node.lower is not None and numeric < node.lower:
            raise RegistryError(f"{node.key}={numeric} below lower bound {node.lower}")
        if node.upper is not None and numeric > node.upper:
            raise RegistryError(f"{node.key}={numeric} above upper bound {node.upper}")
        return int(numeric) if node.integer else numeric
