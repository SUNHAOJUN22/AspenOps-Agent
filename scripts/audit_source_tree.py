from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

_DIRECT_FORBIDDEN = {
    "builtins.eval": "dynamic_eval",
    "builtins.exec": "dynamic_exec",
    "eval": "dynamic_eval",
    "exec": "dynamic_exec",
    "marshal.load": "unsafe_deserialization",
    "marshal.loads": "unsafe_deserialization",
    "os.system": "shell_execution",
    "pickle.load": "unsafe_deserialization",
    "pickle.loads": "unsafe_deserialization",
    "tempfile.mktemp": "unsafe_temporary_path",
    "yaml.load": "unsafe_yaml_load",
}
_SUBPROCESS_CALLS = {
    "subprocess.Popen",
    "subprocess.call",
    "subprocess.check_call",
    "subprocess.check_output",
    "subprocess.run",
}
_BROAD_EXCEPTIONS = {
    "Exception",
    "BaseException",
    "builtins.Exception",
    "builtins.BaseException",
}


def _call_name(node: ast.expr | None) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _location(path: Path, node: ast.AST) -> dict[str, Any]:
    return {
        "path": path.as_posix(),
        "line": int(getattr(node, "lineno", 0)),
        "column": int(getattr(node, "col_offset", 0)),
    }


def audit_tree(root: Path) -> dict[str, Any]:
    root = root.resolve()
    files = sorted(
        path
        for base in (root / "src", root / "scripts")
        if base.exists()
        for path in base.rglob("*.py")
    )
    forbidden: list[dict[str, Any]] = []
    advisory: list[dict[str, Any]] = []
    totals = {
        "files": len(files),
        "lines": 0,
        "functions": 0,
        "async_functions": 0,
        "classes": 0,
        "calls": 0,
    }

    for path in files:
        relative = path.relative_to(root)
        source = path.read_text(encoding="utf-8")
        totals["lines"] += len(source.splitlines())
        try:
            tree = ast.parse(source, filename=relative.as_posix())
        except SyntaxError as exc:
            forbidden.append(
                {
                    "kind": "syntax_error",
                    "path": relative.as_posix(),
                    "line": int(exc.lineno or 0),
                    "column": int(exc.offset or 0),
                    "detail": str(exc),
                }
            )
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                totals["functions"] += 1
            elif isinstance(node, ast.AsyncFunctionDef):
                totals["async_functions"] += 1
            elif isinstance(node, ast.ClassDef):
                totals["classes"] += 1
            elif isinstance(node, ast.ExceptHandler):
                caught = _call_name(node.type)
                if caught in _BROAD_EXCEPTIONS:
                    advisory.append(
                        {
                            "kind": "broad_exception_handler",
                            **_location(relative, node),
                            "detail": caught,
                        }
                    )
            elif isinstance(node, ast.Call):
                totals["calls"] += 1
                name = _call_name(node.func)
                kind = _DIRECT_FORBIDDEN.get(name)
                if kind is not None:
                    forbidden.append(
                        {
                            "kind": kind,
                            **_location(relative, node),
                            "detail": name,
                        }
                    )
                if name in _SUBPROCESS_CALLS:
                    shell_keywords = [
                        item for item in node.keywords if item.arg == "shell"
                    ]
                    for keyword in shell_keywords:
                        safe_false = (
                            isinstance(keyword.value, ast.Constant)
                            and keyword.value.value is False
                        )
                        if not safe_false:
                            forbidden.append(
                                {
                                    "kind": "subprocess_shell",
                                    **_location(relative, node),
                                    "detail": name,
                                }
                            )

    forbidden.sort(key=lambda item: (item["path"], item["line"], item["kind"]))
    advisory.sort(key=lambda item: (item["path"], item["line"], item["kind"]))
    return {
        "schema": "aspenops.source-tree-audit/v1",
        "root": root.as_posix(),
        "status": "PASS" if not forbidden else "FAIL",
        "totals": totals,
        "forbidden_findings": forbidden,
        "advisory_findings": advisory,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit AspenOps Python source for unsafe constructs"
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = audit_tree(args.root)
    payload = json.dumps(report, indent=2, sort_keys=True, allow_nan=False)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
