"""AspenOps deterministic execution runtime."""

from ._version import __version__

RUNTIME_SCHEMA = "aspenops.runtime/v1.2"
PROTOCOL_VERSION = 3

__all__ = ["PROTOCOL_VERSION", "RUNTIME_SCHEMA", "__version__"]
