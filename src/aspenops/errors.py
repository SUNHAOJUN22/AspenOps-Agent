"""Domain-specific exceptions."""


class AspenOpsError(RuntimeError):
    """Base class for AspenOps failures."""


class ConfigurationError(AspenOpsError):
    """Invalid runtime configuration."""


class CompatibilityError(AspenOpsError):
    """Aspen Automation Server could not be discovered or created."""


class CaseOpenError(AspenOpsError):
    """A simulation case could not be opened."""


class NodeResolutionError(AspenOpsError):
    """No candidate Aspen tree path resolved for a semantic node."""


class AccessViolation(AspenOpsError):
    """A read or write violates the node policy."""


class UnitError(AspenOpsError):
    """A unit is unknown or dimensionally incompatible."""


class ValidationError(AspenOpsError):
    """A value violates engineering constraints."""


class WorkerError(AspenOpsError):
    """A worker process failed."""


class WorkerTimeout(WorkerError):
    """A worker did not answer before its deadline."""


class SimulationError(AspenOpsError):
    """The simulator failed to complete a requested operation."""
