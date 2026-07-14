from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from typing import Any

from .errors import SurrogateDomainError
from .hashing import canonical_hash

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _finite(value: float, name: str) -> float:
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    return numeric


def _validate_hash(value: str, name: str) -> None:
    if not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")


@dataclass(frozen=True, slots=True)
class FeatureSpec:
    name: str
    unit: str
    lower: float
    upper: float
    mean: float
    std: float

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.unit.strip():
            raise ValueError("Feature name and unit must not be blank")
        for field_name in ("lower", "upper", "mean", "std"):
            _finite(getattr(self, field_name), f"feature {self.name} {field_name}")
        if self.lower > self.upper:
            raise ValueError(f"Feature {self.name} lower bound exceeds upper bound")
        if self.std <= 0.0:
            raise ValueError(f"Feature {self.name} standard deviation must be positive")


@dataclass(frozen=True, slots=True)
class OutputSpec:
    name: str
    unit: str

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.unit.strip():
            raise ValueError("Output name and unit must not be blank")


@dataclass(frozen=True, slots=True)
class SurrogateManifest:
    aspen_model_sha256: str
    registry_sha256: str
    dataset_sha256: str
    features: tuple[FeatureSpec, ...]
    outputs: tuple[OutputSpec, ...]
    training_version: str
    provider: str
    metrics: dict[str, float]
    standardized_distance_limit: float
    uncertainty_limit: float
    covariance: tuple[tuple[float, ...], ...] | None = None
    mahalanobis_limit: float | None = None
    max_covariance_condition: float = 1e8
    schema: str = "aspenops.surrogate-manifest/v1"

    def __post_init__(self) -> None:
        for value, name in (
            (self.aspen_model_sha256, "aspen_model_sha256"),
            (self.registry_sha256, "registry_sha256"),
            (self.dataset_sha256, "dataset_sha256"),
        ):
            _validate_hash(value, name)
        if not self.features or not self.outputs:
            raise ValueError("Surrogate manifest requires features and outputs")
        feature_names = [feature.name for feature in self.features]
        output_names = [output.name for output in self.outputs]
        if len(feature_names) != len(set(feature_names)):
            raise ValueError("Feature names must be unique")
        if len(output_names) != len(set(output_names)):
            raise ValueError("Output names must be unique")
        if not self.training_version.strip() or not self.provider.strip():
            raise ValueError("Training version and provider must not be blank")
        for metric, value in self.metrics.items():
            _finite(value, f"metric {metric}")
        if _finite(self.standardized_distance_limit, "standardized distance limit") <= 0.0:
            raise ValueError("standardized_distance_limit must be positive")
        if _finite(self.uncertainty_limit, "uncertainty limit") < 0.0:
            raise ValueError("uncertainty_limit must be nonnegative")
        if _finite(self.max_covariance_condition, "max covariance condition") <= 1.0:
            raise ValueError("max_covariance_condition must exceed one")
        if self.mahalanobis_limit is not None:
            if _finite(self.mahalanobis_limit, "Mahalanobis limit") <= 0.0:
                raise ValueError("mahalanobis_limit must be positive")
            if self.covariance is None:
                raise ValueError("mahalanobis_limit requires covariance")
        if self.covariance is not None:
            validate_covariance(
                self.covariance,
                dimension=len(self.features),
                max_condition=self.max_covariance_condition,
            )

    @property
    def manifest_sha256(self) -> str:
        return canonical_hash(asdict(self))

    def compatible_with(self, model_sha256: str, registry_sha256: str) -> bool:
        return (
            model_sha256 == self.aspen_model_sha256
            and registry_sha256 == self.registry_sha256
        )


@dataclass(frozen=True, slots=True)
class DomainAssessment:
    in_box: bool
    standardized_distance: float
    standardized_passed: bool
    mahalanobis_distance: float | None
    mahalanobis_passed: bool | None
    covariance_condition: float | None
    covariance_regularization: float | None
    applicable: bool
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _matrix_norm_inf(matrix: list[list[float]]) -> float:
    return max(math.fsum(abs(value) for value in row) for row in matrix)


def _inverse(matrix: list[list[float]]) -> list[list[float]]:
    size = len(matrix)
    augmented = [
        [*row, *(1.0 if i == j else 0.0 for j in range(size))]
        for i, row in enumerate(matrix)
    ]
    for column in range(size):
        pivot_row = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        pivot = augmented[pivot_row][column]
        if abs(pivot) <= 1e-15:
            raise SurrogateDomainError("Covariance matrix is singular")
        augmented[column], augmented[pivot_row] = augmented[pivot_row], augmented[column]
        pivot = augmented[column][column]
        augmented[column] = [value / pivot for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor == 0.0:
                continue
            augmented[row] = [
                value - factor * pivot_value
                for value, pivot_value in zip(augmented[row], augmented[column], strict=True)
            ]
    return [row[size:] for row in augmented]


def _cholesky(matrix: list[list[float]]) -> list[list[float]]:
    size = len(matrix)
    lower = [[0.0] * size for _ in range(size)]
    for row in range(size):
        for column in range(row + 1):
            subtotal = math.fsum(
                lower[row][index] * lower[column][index] for index in range(column)
            )
            if row == column:
                diagonal = matrix[row][row] - subtotal
                if diagonal <= 0.0:
                    raise SurrogateDomainError("Covariance matrix is not positive definite")
                lower[row][column] = math.sqrt(diagonal)
            else:
                lower[row][column] = (matrix[row][column] - subtotal) / lower[column][column]
    return lower


def validate_covariance(
    covariance: tuple[tuple[float, ...], ...],
    *,
    dimension: int,
    max_condition: float,
) -> tuple[list[list[float]], list[list[float]], float, float]:
    if len(covariance) != dimension or any(len(row) != dimension for row in covariance):
        raise SurrogateDomainError("Covariance matrix dimension does not match feature count")
    matrix = [[_finite(value, "covariance entry") for value in row] for row in covariance]
    for row in range(dimension):
        for column in range(row + 1, dimension):
            if not math.isclose(
                matrix[row][column],
                matrix[column][row],
                rel_tol=1e-12,
                abs_tol=1e-15,
            ):
                raise SurrogateDomainError("Covariance matrix must be symmetric")
    diagonal_scale = max(max(abs(matrix[index][index]), 1.0) for index in range(dimension))
    regularization = 0.0
    for attempt in range(9):
        candidate = [row[:] for row in matrix]
        if regularization:
            for index in range(dimension):
                candidate[index][index] += regularization
        try:
            cholesky = _cholesky(candidate)
            inverse = _inverse(candidate)
            condition = _matrix_norm_inf(candidate) * _matrix_norm_inf(inverse)
        except SurrogateDomainError:
            condition = math.inf
        if math.isfinite(condition) and condition <= max_condition:
            return candidate, cholesky, condition, regularization
        regularization = diagonal_scale * 10.0 ** (-12 + attempt)
    raise SurrogateDomainError(
        f"Covariance matrix remains singular or ill-conditioned above {max_condition:g}"
    )


def _mahalanobis(delta: list[float], cholesky: list[list[float]]) -> float:
    transformed: list[float] = []
    for row in range(len(delta)):
        subtotal = math.fsum(cholesky[row][index] * transformed[index] for index in range(row))
        transformed.append((delta[row] - subtotal) / cholesky[row][row])
    return math.sqrt(math.fsum(value * value for value in transformed))


def assess_domain(manifest: SurrogateManifest, values: dict[str, float]) -> DomainAssessment:
    expected = {feature.name for feature in manifest.features}
    missing = sorted(expected - values.keys())
    extra = sorted(values.keys() - expected)
    if missing or extra:
        raise SurrogateDomainError(
            f"Feature set mismatch; missing={missing or 'none'}, extra={extra or 'none'}"
        )
    ordered = [_finite(values[feature.name], feature.name) for feature in manifest.features]
    in_box = all(
        feature.lower <= value <= feature.upper
        for feature, value in zip(manifest.features, ordered, strict=True)
    )
    standardized = [
        (value - feature.mean) / feature.std
        for feature, value in zip(manifest.features, ordered, strict=True)
    ]
    standardized_distance = math.sqrt(math.fsum(value * value for value in standardized))
    standardized_passed = standardized_distance <= manifest.standardized_distance_limit
    mahalanobis_distance: float | None = None
    mahalanobis_passed: bool | None = None
    condition: float | None = None
    regularization: float | None = None
    if manifest.covariance is not None:
        _matrix, cholesky, condition, regularization = validate_covariance(
            manifest.covariance,
            dimension=len(manifest.features),
            max_condition=manifest.max_covariance_condition,
        )
        mahalanobis_distance = _mahalanobis(
            [value - feature.mean for feature, value in zip(manifest.features, ordered, strict=True)],
            cholesky,
        )
        if manifest.mahalanobis_limit is not None:
            mahalanobis_passed = mahalanobis_distance <= manifest.mahalanobis_limit
    reasons: list[str] = []
    if not in_box:
        reasons.append("outside_box_domain")
    if not standardized_passed:
        reasons.append("standardized_distance_exceeded")
    if mahalanobis_passed is False:
        reasons.append("mahalanobis_distance_exceeded")
    applicable = in_box and standardized_passed and mahalanobis_passed is not False
    return DomainAssessment(
        in_box=in_box,
        standardized_distance=standardized_distance,
        standardized_passed=standardized_passed,
        mahalanobis_distance=mahalanobis_distance,
        mahalanobis_passed=mahalanobis_passed,
        covariance_condition=condition,
        covariance_regularization=regularization,
        applicable=applicable,
        reasons=tuple(reasons),
    )
