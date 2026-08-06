from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class PolicyError(PermissionError):
    pass


_SUPPORTED_MODES = {"readonly", "default", "enhanced"}


@dataclass(frozen=True, slots=True)
class Policy:
    mode: str
    allowed_roots: tuple[Path, ...]

    def __post_init__(self) -> None:
        if self.mode not in _SUPPORTED_MODES:
            raise ValueError(f"Unsupported policy mode={self.mode!r}")
        if not isinstance(self.allowed_roots, tuple) or any(
            not isinstance(root, Path) for root in self.allowed_roots
        ):
            raise ValueError("allowed_roots must be a tuple of Path values")

    def assert_path(self, path: str | Path) -> Path:
        resolved = Path(path).expanduser().resolve()
        if not self.allowed_roots:
            return resolved
        for root in self.allowed_roots:
            resolved_root = root.expanduser().resolve()
            try:
                resolved.relative_to(resolved_root)
                return resolved
            except ValueError:
                continue
        raise PolicyError(f"Path is outside ASPENOPS_ALLOWED_ROOTS: {resolved}")

    def assert_writes_allowed(self) -> None:
        if self.mode == "readonly":
            raise PolicyError("Writes are disabled in readonly mode")

    def assert_enhanced(self) -> None:
        if self.mode != "enhanced":
            raise PolicyError("Operation requires ASPENOPS_MODE=enhanced")
