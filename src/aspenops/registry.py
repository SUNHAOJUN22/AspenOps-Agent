"""Semantic node registry and candidate-path resolution."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from string import Formatter
from typing import Any

import yaml

from aspenops.errors import NodeResolutionError, ValidationError
from aspenops.models import AccessMode
from aspenops.units import dimension_of


@dataclass(frozen=True)
class NodeSpec:
    key: str
    candidates: tuple[str, ...]
    access: AccessMode
    quantity: str
    default_unit: str | None
    minimum: float | None = None
    maximum: float | None = None
    integer: bool = False
    status: str = "verify_case"

    @property
    def identifiers(self) -> frozenset[str]:
        names: set[str] = set()
        formatter = Formatter()
        for candidate in self.candidates:
            for _, field, _, _ in formatter.parse(candidate):
                if field:
                    names.add(field)
        return frozenset(names)

    def validate_identifiers(self, identifiers: dict[str, str]) -> None:
        missing = self.identifiers - identifiers.keys()
        extra = identifiers.keys() - self.identifiers
        if missing:
            raise ValidationError(f"Missing identifiers for {self.key}: {sorted(missing)}")
        if extra:
            raise ValidationError(f"Unexpected identifiers for {self.key}: {sorted(extra)}")
        for name, value in identifiers.items():
            if not re.fullmatch(r"[A-Za-z0-9_.-]+", value):
                raise ValidationError(f"Unsafe identifier {name}={value!r}")

    def render_candidates(self, identifiers: dict[str, str]) -> tuple[str, ...]:
        self.validate_identifiers(identifiers)
        return tuple(candidate.format_map(identifiers) for candidate in self.candidates)


class NodeRegistry:
    def __init__(self, specs: dict[str, NodeSpec]) -> None:
        self._specs = specs

    @classmethod
    def from_yaml(cls, path: str | Path) -> NodeRegistry:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or "nodes" not in raw:
            raise ValidationError("Registry YAML must contain a 'nodes' mapping")
        specs: dict[str, NodeSpec] = {}
        nodes = raw["nodes"]
        if not isinstance(nodes, dict):
            raise ValidationError("Registry 'nodes' must be a mapping")
        for key, payload in nodes.items():
            if not isinstance(payload, dict):
                raise ValidationError(f"Node {key} must be a mapping")
            candidates = payload.get("candidates")
            if not isinstance(candidates, list) or not candidates:
                raise ValidationError(f"Node {key} requires candidate paths")
            unit = payload.get("default_unit")
            quantity = str(payload.get("quantity", "dimensionless"))
            if unit is not None and dimension_of(str(unit)) != quantity:
                raise ValidationError(
                    f"Node {key} unit {unit!r} does not match quantity {quantity!r}"
                )
            specs[str(key)] = NodeSpec(
                key=str(key),
                candidates=tuple(str(item) for item in candidates),
                access=AccessMode(str(payload.get("access", "read_only"))),
                quantity=quantity,
                default_unit=str(unit) if unit is not None else None,
                minimum=_optional_float(payload.get("minimum")),
                maximum=_optional_float(payload.get("maximum")),
                integer=bool(payload.get("integer", False)),
                status=str(payload.get("status", "verify_case")),
            )
        return cls(specs)

    def get(self, key: str) -> NodeSpec:
        try:
            return self._specs[key]
        except KeyError as exc:
            raise NodeResolutionError(f"Unknown semantic node: {key}") from exc

    def keys(self) -> tuple[str, ...]:
        return tuple(sorted(self._specs))

    def resolve(
        self,
        key: str,
        identifiers: dict[str, str],
        exists: Callable[[str], bool],
        cache: dict[tuple[str, tuple[tuple[str, str], ...]], str] | None = None,
    ) -> str:
        spec = self.get(key)
        cache_key = (key, tuple(sorted(identifiers.items())))
        if cache is not None and cache_key in cache:
            cached = cache[cache_key]
            if exists(cached):
                return cached
            del cache[cache_key]
        attempted: list[str] = []
        for path in spec.render_candidates(identifiers):
            attempted.append(path)
            if exists(path):
                if cache is not None:
                    cache[cache_key] = path
                return path
        raise NodeResolutionError(f"No candidate path resolved for {key}; attempted: {attempted}")


def bundled_registry_path() -> Path:
    return Path(__file__).parent / "data" / "nodes" / "aspen_plus.yaml"


def load_bundled_registry() -> NodeRegistry:
    return NodeRegistry.from_yaml(bundled_registry_path())


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)
