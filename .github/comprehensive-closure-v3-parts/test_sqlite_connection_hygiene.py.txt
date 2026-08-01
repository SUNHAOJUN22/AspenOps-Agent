from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_test_suite_closes_every_direct_sqlite_connection() -> None:
    violations: list[str] = []
    for path in sorted((ROOT / "tests").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        parents: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            target = node.func
            if not (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "sqlite3"
                and target.attr == "connect"
            ):
                continue
            parent = parents.get(node)
            safely_closed = bool(
                isinstance(parent, ast.Call)
                and isinstance(parent.func, ast.Name)
                and parent.func.id == "closing"
            )
            if not safely_closed:
                violations.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert not violations, "Unclosed direct sqlite3.connect calls: " + ", ".join(violations)
