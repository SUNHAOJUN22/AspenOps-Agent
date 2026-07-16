from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .errors import AuthorizationError, ValidationError

_VALID_MODES = {"readonly", "default", "enhanced"}
_MAX_PATH_CHARS = 4096


class PolicyError(AuthorizationError):
    pass


def _normalize_suffixes(suffixes: tuple[str, ...]) -> tuple[str, ...]:
    normalized: list[str] = []
    for suffix in suffixes:
        if not isinstance(suffix, str) or not suffix.startswith(".") or len(suffix) < 2:
            raise ValueError("Allowed suffixes must be strings beginning with '.'")
        normalized.append(suffix.casefold())
    return tuple(sorted(set(normalized)))


@dataclass(frozen=True, slots=True)
class Policy:
    mode: str
    allowed_roots: tuple[Path, ...]

    def __post_init__(self) -> None:
        if self.mode not in _VALID_MODES:
            raise ValueError(f"Unsupported policy mode: {self.mode!r}")
        roots: list[Path] = []
        for root in tuple(self.allowed_roots):
            if not isinstance(root, Path):
                raise TypeError("allowed_roots must contain only pathlib.Path values")
            resolved = root.expanduser().resolve()
            if resolved not in roots:
                roots.append(resolved)
        object.__setattr__(self, "allowed_roots", tuple(roots))

    @staticmethod
    def _raw_path(path: str | Path, name: str) -> Path:
        if not isinstance(path, str | Path):
            raise TypeError(f"{name} must be a string or Path")
        text = os.fspath(path)
        if not text or not text.strip():
            raise ValidationError(f"{name} must not be blank")
        if "\x00" in text:
            raise ValidationError(f"{name} contains a NUL character")
        if len(text) > _MAX_PATH_CHARS:
            raise ValidationError(f"{name} exceeds {_MAX_PATH_CHARS} characters")
        return Path(text).expanduser()

    def _assert_within_roots(self, resolved: Path) -> Path:
        if self.allowed_roots and not any(
            resolved == root or root in resolved.parents for root in self.allowed_roots
        ):
            roots = ", ".join(str(root) for root in self.allowed_roots)
            raise PolicyError(
                f"Path {resolved} is outside ASPENOPS_ALLOWED_ROOTS: {roots}",
                context={"path": str(resolved), "allowed_roots": roots},
            )
        return resolved

    @staticmethod
    def _assert_suffix(path: Path, suffixes: tuple[str, ...]) -> None:
        normalized = _normalize_suffixes(suffixes)
        if normalized and path.suffix.casefold() not in normalized:
            raise ValidationError(
                f"Path {path} has suffix {path.suffix!r}; allowed suffixes are {normalized}"
            )

    def assert_path(self, path: str | Path) -> Path:
        raw = self._raw_path(path, "path")
        return self._assert_within_roots(raw.resolve())

    def assert_input_file(
        self,
        path: str | Path,
        *,
        max_bytes: int | None = None,
        suffixes: tuple[str, ...] = (),
    ) -> Path:
        raw = self._raw_path(path, "input path")
        if raw.is_symlink():
            raise PolicyError(
                f"Symbolic-link inputs are not allowed: {raw}",
                context={"path": str(raw)},
            )
        resolved = self._assert_within_roots(raw.resolve())
        if not resolved.is_file():
            raise ValidationError(f"Input path is not a regular file: {resolved}")
        self._assert_suffix(resolved, suffixes)
        if max_bytes is not None:
            if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 1:
                raise ValueError("max_bytes must be an integer >= 1")
            size = resolved.stat().st_size
            if size > max_bytes:
                raise ValidationError(
                    f"Input file {resolved} is {size} bytes; maximum is {max_bytes} bytes"
                )
        return resolved

    def assert_output_path(
        self,
        path: str | Path,
        *,
        suffixes: tuple[str, ...] = (),
        create_parent: bool = False,
    ) -> Path:
        raw = self._raw_path(path, "output path")
        if raw.is_symlink():
            raise PolicyError(
                f"Symbolic-link outputs are not allowed: {raw}",
                context={"path": str(raw)},
            )
        parent = raw.parent.resolve()
        resolved = self._assert_within_roots(parent / raw.name)
        self._assert_suffix(resolved, suffixes)
        if resolved.exists() and not resolved.is_file():
            raise ValidationError(f"Output path exists but is not a regular file: {resolved}")
        if create_parent:
            parent.mkdir(parents=True, exist_ok=True)
        elif not parent.is_dir():
            raise ValidationError(f"Output parent directory does not exist: {parent}")
        return resolved

    def assert_writes_allowed(self) -> None:
        if self.mode == "readonly":
            raise PolicyError("Writes are disabled because ASPENOPS_MODE=readonly")

    def assert_enhanced(self) -> None:
        if self.mode != "enhanced":
            raise PolicyError("Operation requires ASPENOPS_MODE=enhanced")
