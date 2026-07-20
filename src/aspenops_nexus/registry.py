from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .units import convert, dimension


class RegistryError(ValueError):
    pass


_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_. -]{1,128}$")
_CONVERGENCE_OPERATORS = {"<", "<=", ">", ">=", "=="}


def _convergence_marker(value: Any, *, label: str) -> tuple[str, Any]:
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if not normalized:
            raise RegistryError(f"{label} values must not be empty strings")
        return ("text", normalized)
    if isinstance(value, int):
        return ("number", float(value))
    if isinstance(value, float) and math.isfinite(value):
        return ("number", value)
    raise RegistryError(f"{label} values must be finite scalar JSON values")


def _validate_convergence_locator(key: str, locator: dict[str, Any]) -> None:
    operator_present = "convergence_operator" in locator
    threshold_present = "convergence_threshold" in locator
    tolerance_present = "convergence_tolerance" in locator
    if operator_present != threshold_present:
        raise RegistryError(
            f"Convergence node {key} must define convergence_operator and "
            "convergence_threshold together"
        )
    if tolerance_present and not threshold_present:
        raise RegistryError(
            f"Convergence node {key} cannot define convergence_tolerance without a threshold"
        )

    if operator_present:
        operator = locator["convergence_operator"]
        if not isinstance(operator, str) or operator not in _CONVERGENCE_OPERATORS:
            raise RegistryError(f"Invalid convergence operator for {key}: {operator}")
        threshold = locator["convergence_threshold"]
        if isinstance(threshold, bool) or not isinstance(threshold, int | float):
            raise RegistryError(f"Convergence threshold for {key} must be finite numeric")
        if not math.isfinite(float(threshold)):
            raise RegistryError(f"Convergence threshold for {key} must be finite numeric")
        tolerance = locator.get("convergence_tolerance", 0.0)
        if isinstance(tolerance, bool) or not isinstance(tolerance, int | float):
            raise RegistryError(
                f"Convergence tolerance for {key} must be finite non-negative numeric"
            )
        if not math.isfinite(float(tolerance)) or float(tolerance) < 0:
            raise RegistryError(
                f"Convergence tolerance for {key} must be finite non-negative numeric"
            )

    marker_sets: dict[str, set[tuple[str, Any]]] = {}
    for field in ("converged_values", "not_converged_values"):
        if field not in locator:
            continue
        raw_values = locator[field]
        if not isinstance(raw_values, list) or not raw_values:
            raise RegistryError(f"Convergence node {key} {field} must be a non-empty array")
        markers = {
            _convergence_marker(item, label=f"Convergence node {key} {field}")
            for item in raw_values
        }
        if len(markers) != len(raw_values):
            raise RegistryError(f"Convergence node {key} {field} must contain unique values")
        marker_sets[field] = markers

    if operator_present and marker_sets:
        raise RegistryError(
            f"Convergence node {key} cannot mix threshold and enumerated convergence contracts"
        )
    overlap = marker_sets.get("converged_values", set()) & marker_sets.get(
        "not_converged_values", set()
    )
    if overlap:
        raise RegistryError(
            f"Convergence node {key} has values declared as both converged and not converged"
        )


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
    role: str = "variable"

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
    def _validate_definition(key: str, node: dict[str, Any]) -> None:
        access = str(node.get("access", "read"))
        if access not in {"read", "write", "readwrite"}:
            raise RegistryError(f"Invalid access for {key}: {access}")
        role = str(node.get("role", "variable"))
        if role not in {"variable", "convergence"}:
            raise RegistryError(f"Invalid role for {key}: {role}")
        if role == "convergence" and access not in {"read", "readwrite"}:
            raise RegistryError(f"Convergence node {key} must be readable")
        if role == "convergence" and node.get("identifiers", []):
            raise RegistryError(f"Convergence node {key} cannot require identifiers")
        unit = node.get("unit")
        if unit is not None:
            dimension(str(unit))
        lower = node.get("lower")
        upper = node.get("upper")
        if lower is not None and upper is not None and float(lower) > float(upper):
            raise RegistryError(f"Lower bound exceeds upper bound for {key}")
        paths = node.get("paths", [])
        locator = node.get("locator", {})
        if not paths and not locator:
            raise RegistryError(f"Node {key} requires at least one path or locator")
        if paths and not isinstance(paths, list):
            raise RegistryError(f"paths for {key} must be a list")
        if locator and not isinstance(locator, dict):
            raise RegistryError(f"locator for {key} must be an object")
        if role == "convergence":
            _validate_convergence_locator(key, dict(locator))

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
                    "integer": bool(node.get("integer", False)),
                    "backend": node.get("backend", "aspen_plus"),
                    "role": node.get("role", "variable"),
                    "verification": node.get("verification", "project-required"),
                    "description": node.get("description", ""),
                }
            )
        return output

    @staticmethod
    def _validate_identifiers(identifiers: dict[str, str]) -> None:
        for name, value in identifiers.items():
            if not name or not _IDENTIFIER_RE.fullmatch(value):
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
            lower=None if node.get("lower") is None else float(node["lower"]),
            upper=None if node.get("upper") is None else float(node["upper"]),
            integer=bool(node.get("integer", False)),
            backend=str(node.get("backend", "aspen_plus")),
            locator=locator,
            verification=str(node.get("verification", "project-required")),
            description=str(node.get("description", "")),
            role=str(node.get("role", "variable")),
        )

    def convergence_nodes(self, backend: str) -> list[ResolvedNode]:
        output: list[ResolvedNode] = []
        for key in self.keys():
            definition = self._nodes[key]
            if str(definition.get("role", "variable")) != "convergence":
                continue
            node_backend = str(definition.get("backend", "aspen_plus"))
            if backend != "mock" and node_backend not in {backend, "any"}:
                continue
            output.append(self.resolve(key, {}))
        return output

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
        numeric = convert(float(value), unit, node.native_unit)
        if node.integer:
            rounded = round(numeric)
            if abs(numeric - rounded) > 1e-9:
                raise RegistryError(f"{node.key} requires an integer value")
            numeric = float(rounded)
        if node.lower is not None and numeric < node.lower:
            raise RegistryError(f"{node.key}={numeric} below lower bound {node.lower}")
        if node.upper is not None and numeric > node.upper:
            raise RegistryError(f"{node.key}={numeric} above upper bound {node.upper}")
        return int(numeric) if node.integer else numeric
