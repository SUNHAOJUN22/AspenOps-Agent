from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class PolicyError(PermissionError):
    pass


@dataclass(frozen=True, slots=True)
class Policy:
    mode: str
    allowed_roots: tuple[Path, ...]

    def assert_path(self, path: str | Path) -> Path:
        resolved = Path(path).expanduser().resolve()
        if not self.allowed_roots:
            return resolved
        for root in self.allowed_roots:
            try:
                resolved.relative_to(root)
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
