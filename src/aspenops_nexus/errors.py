from __future__ import annotations

from typing import Any, ClassVar


class AspenOpsError(RuntimeError):
    code: ClassVar[str] = "ASPENOPS_ERROR"
    retryable: ClassVar[bool] = False

    def __init__(self, message: str, *, context: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.context = dict(context or {})

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "context": self.context,
        }


class ValidationError(AspenOpsError, ValueError):
    code = "VALIDATION_ERROR"


class AuthorizationError(AspenOpsError, PermissionError):
    code = "AUTHORIZATION_ERROR"


class UnitError(ValidationError):
    code = "UNIT_ERROR"


class BoundError(ValidationError):
    code = "BOUND_ERROR"


class RegistryError(ValidationError):
    code = "REGISTRY_ERROR"


class ModelOpenError(AspenOpsError):
    code = "MODEL_OPEN_ERROR"


class ComActivationError(AspenOpsError):
    code = "COM_ACTIVATION_ERROR"


class ComTransportError(AspenOpsError):
    code = "COM_TRANSPORT_ERROR"
    retryable = True


class EngineError(AspenOpsError):
    code = "ENGINE_ERROR"


class ConvergenceError(EngineError):
    code = "CONVERGENCE_ERROR"


class ConstraintError(ValidationError):
    code = "CONSTRAINT_ERROR"


class BalanceError(ValidationError):
    code = "BALANCE_ERROR"


class TimeoutError(AspenOpsError):
    code = "TIMEOUT_ERROR"


class WorkerCrashError(AspenOpsError):
    code = "WORKER_CRASH_ERROR"
    retryable = True


class DatabaseError(AspenOpsError):
    code = "DATABASE_ERROR"


class CacheCorruptionError(AspenOpsError):
    code = "CACHE_CORRUPTION_ERROR"


class EvidenceIntegrityError(AspenOpsError):
    code = "EVIDENCE_INTEGRITY_ERROR"


class SurrogateDomainError(ValidationError):
    code = "SURROGATE_DOMAIN_ERROR"


class SurrogateDriftError(ValidationError):
    code = "SURROGATE_DRIFT_ERROR"


class ApprovalError(AuthorizationError):
    code = "APPROVAL_ERROR"


_ERROR_TYPES: tuple[type[AspenOpsError], ...] = (
    ValidationError,
    AuthorizationError,
    UnitError,
    BoundError,
    RegistryError,
    ModelOpenError,
    ComActivationError,
    ComTransportError,
    EngineError,
    ConvergenceError,
    ConstraintError,
    BalanceError,
    TimeoutError,
    WorkerCrashError,
    DatabaseError,
    CacheCorruptionError,
    EvidenceIntegrityError,
    SurrogateDomainError,
    SurrogateDriftError,
    ApprovalError,
)
ERROR_BY_CODE = {error_type.code: error_type for error_type in _ERROR_TYPES}


def classify_exception(exc: BaseException) -> dict[str, Any]:
    if isinstance(exc, AspenOpsError):
        return exc.to_dict()
    return {
        "code": "UNCLASSIFIED_ERROR",
        "message": str(exc),
        "retryable": False,
        "context": {"exception_type": type(exc).__name__},
    }
