from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    observed = text.count(old)
    if observed != 1:
        raise RuntimeError(
            f"Patch anchor mismatch for {path}: expected 1, observed {observed}"
        )
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    replace_once(
        "src/aspenops_nexus/evaluation.py",
        """def _finite_number(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, int | float)
        and math.isfinite(float(value))
    )


def _numeric_value""",
        """def _finite_number(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, int | float)
        and math.isfinite(float(value))
    )


def _finite(value: Any) -> bool:
    \"\"\"Compatibility helper; numeric runtime gates use _finite_number instead.\"\"\"
    if isinstance(value, bool | str):
        return True
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _numeric_value""",
    )
    replace_once(
        "src/aspenops_nexus/native_builder.py",
        "from typing import Any, Protocol\n",
        "from typing import Any, Protocol, cast\n",
    )
    replace_once(
        "src/aspenops_nexus/native_builder.py",
        """    return method


def _assert_isolation_result""",
        """    return cast(Callable[..., Any], method)


def _assert_isolation_result""",
    )


if __name__ == "__main__":
    main()
