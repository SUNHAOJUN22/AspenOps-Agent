from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

Severity = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]

ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = (ROOT / "src", ROOT / "scripts")
OUTPUT = ROOT / "reports" / "logic-risk-scan.json"
SCHEMA = "aspenops.logic-risk-scan/v1"


@dataclass(frozen=True, slots=True)
class Finding:
    rule: str
    severity: Severity
    path: str
    line: int
    column: int
    symbol: str
    message: str


@dataclass(frozen=True, slots=True)
class ParseFailure:
    path: str
    line: int
    column: int
    message: str


def _qualified_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        owner = _qualified_name(node.value)
        return node.attr if owner is None else f"{owner}.{node.attr}"
    return None


def _source_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_mutable_literal(node: ast.AST) -> bool:
    return isinstance(node, ast.List | ast.Dict | ast.Set)


def _is_float_like(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return isinstance(node.value, float)
    if isinstance(node, ast.Call):
        return _qualified_name(node.func) in {"float", "math.nan", "math.inf"}
    return False


def _keyword(call: ast.Call, name: str) -> ast.AST | None:
    for item in call.keywords:
        if item.arg == name:
            return item.value
    return None


def _constant_bool(node: ast.AST | None) -> bool | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return node.value
    return None


def _string_constant(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


class RiskVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.relative_path = path.relative_to(ROOT).as_posix()
        self.findings: list[Finding] = []
        self.scope: list[str] = []

    @property
    def symbol(self) -> str:
        return ".".join(self.scope) if self.scope else "<module>"

    def add(self, node: ast.AST, rule: str, severity: Severity, message: str) -> None:
        self.findings.append(
            Finding(
                rule=rule,
                severity=severity,
                path=self.relative_path,
                line=getattr(node, "lineno", 0),
                column=getattr(node, "col_offset", 0),
                symbol=self.symbol,
                message=message,
            )
        )

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.scope.append(node.name)
        defaults = [*node.args.defaults, *[item for item in node.args.kw_defaults if item is not None]]
        for default in defaults:
            if _is_mutable_literal(default):
                self.add(
                    default,
                    "PY_MUTABLE_DEFAULT",
                    "HIGH",
                    "Mutable function defaults share state across calls.",
                )
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is None:
            self.add(
                node,
                "PY_BARE_EXCEPT",
                "HIGH",
                "Bare except catches process-control exceptions and obscures failure taxonomy.",
            )
        else:
            name = _qualified_name(node.type)
            if name in {"Exception", "BaseException", "builtins.Exception", "builtins.BaseException"}:
                severity: Severity = "HIGH" if name and "BaseException" in name else "MEDIUM"
                self.add(
                    node,
                    "PY_BROAD_EXCEPTION",
                    severity,
                    f"Broad handler for {name} requires an explicit boundary justification.",
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = _qualified_name(node.func)
        if name == "bool":
            self.add(
                node,
                "PY_BOOL_COERCION",
                "MEDIUM",
                "bool(value) treats non-empty strings such as 'false' as True.",
            )
        elif name == "sum":
            severity: Severity = (
                "HIGH"
                if any(token in self.symbol.casefold() for token in ("balance", "residual", "energy"))
                else "LOW"
            )
            self.add(
                node,
                "NUM_ORDINARY_SUM",
                severity,
                "Ordinary sum may accumulate floating-point cancellation; verify math.fsum is unnecessary.",
            )
        elif name == "json.loads":
            self.add(
                node,
                "IO_LOOSE_JSON_LOADS",
                "HIGH",
                "json.loads accepts duplicate keys and non-finite constants unless wrapped by strict parsing.",
            )
        elif name == "json.dumps":
            if _constant_bool(_keyword(node, "allow_nan")) is not False:
                self.add(
                    node,
                    "IO_JSON_ALLOW_NAN_DEFAULT",
                    "MEDIUM",
                    "json.dumps defaults to emitting NaN/Infinity, which are outside strict JSON.",
                )
            default = _keyword(node, "default")
            if _qualified_name(default) == "str":
                self.add(
                    node,
                    "IO_JSON_DEFAULT_STR",
                    "HIGH",
                    "default=str silently changes typed data into strings and can expose paths or secrets.",
                )
        elif name == "time.time":
            severity = (
                "HIGH"
                if any(token in self.symbol.casefold() for token in ("deadline", "timeout", "lease"))
                else "MEDIUM"
            )
            self.add(
                node,
                "TIME_WALL_CLOCK",
                severity,
                "Wall-clock time can jump; elapsed-time and deadline logic should use time.monotonic().",
            )
        elif name in {
            "random.random",
            "random.uniform",
            "random.randint",
            "random.randrange",
            "random.choice",
            "random.sample",
            "random.shuffle",
        }:
            self.add(
                node,
                "NUM_GLOBAL_RANDOM",
                "MEDIUM",
                "Module-global random state weakens deterministic replay; use an explicit seeded generator.",
            )
        elif name in {"eval", "exec", "os.system"}:
            self.add(
                node,
                "SEC_DYNAMIC_EXECUTION",
                "CRITICAL",
                f"Dynamic execution via {name} is unsafe for agent-controlled inputs.",
            )
        elif name in {"pickle.load", "pickle.loads"}:
            self.add(
                node,
                "SEC_PICKLE_LOAD",
                "CRITICAL",
                "Unpickling untrusted bytes can execute arbitrary code.",
            )
        elif name in {"subprocess.run", "subprocess.Popen", "subprocess.call", "subprocess.check_call"}:
            if _constant_bool(_keyword(node, "shell")) is True:
                self.add(
                    node,
                    "SEC_SUBPROCESS_SHELL",
                    "CRITICAL",
                    "shell=True permits command injection when any argument is externally influenced.",
                )
        elif name == "hash":
            self.add(
                node,
                "IDENTITY_PROCESS_HASH",
                "HIGH",
                "Python hash() is process-randomized and must not define persistent identity.",
            )
        elif name in {"Path.write_text", "Path.write_bytes"}:
            self.add(
                node,
                "IO_NONATOMIC_WRITE",
                "LOW",
                "Direct writes are non-atomic; verify partial publication cannot be observed.",
            )
        elif name in {"min", "max"} and node.args:
            if any(
                isinstance(argument, ast.Call)
                and _qualified_name(argument.func) in {"min", "max"}
                for argument in node.args
            ):
                self.add(
                    node,
                    "NUM_SILENT_CLIPPING",
                    "MEDIUM",
                    "Nested min/max silently clips values; verify clipping is explicit and reported.",
                )
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        operands = [node.left, *node.comparators]
        if any(isinstance(operator, ast.Eq | ast.NotEq) for operator in node.ops) and any(
            _is_float_like(operand) for operand in operands
        ):
            self.add(
                node,
                "NUM_FLOAT_EQUALITY",
                "LOW",
                "Direct floating-point equality requires exact-representation justification.",
            )
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str):
            normalized = " ".join(node.value.upper().split())
            if "INSERT OR REPLACE" in normalized or normalized.startswith("REPLACE INTO"):
                self.add(
                    node,
                    "DB_REPLACE_SEMANTICS",
                    "HIGH",
                    "SQLite REPLACE deletes then inserts; verify foreign keys, audit history and versions.",
                )
        self.generic_visit(node)


def _python_files() -> list[Path]:
    files: set[Path] = set()
    for root in SCAN_ROOTS:
        if root.is_dir():
            files.update(path for path in root.rglob("*.py") if path.is_file())
    return sorted(files, key=lambda path: path.relative_to(ROOT).as_posix())


def scan() -> dict[str, Any]:
    findings: list[Finding] = []
    parse_failures: list[ParseFailure] = []
    file_hashes: dict[str, str] = {}
    for path in _python_files():
        relative = path.relative_to(ROOT).as_posix()
        file_hashes[relative] = _source_sha256(path)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        except (SyntaxError, UnicodeDecodeError) as exc:
            parse_failures.append(
                ParseFailure(
                    path=relative,
                    line=getattr(exc, "lineno", 0) or 0,
                    column=getattr(exc, "offset", 0) or 0,
                    message=str(exc),
                )
            )
            continue
        visitor = RiskVisitor(path)
        visitor.visit(tree)
        findings.extend(visitor.findings)
    findings.sort(key=lambda item: (item.path, item.line, item.column, item.rule))
    parse_failures.sort(key=lambda item: (item.path, item.line, item.column))
    counts: dict[str, int] = {}
    severity_counts: dict[str, int] = {}
    for item in findings:
        counts[item.rule] = counts.get(item.rule, 0) + 1
        severity_counts[item.severity] = severity_counts.get(item.severity, 0) + 1
    return {
        "schema": SCHEMA,
        "truth_boundary": (
            "Heuristic AST findings are an audit navigation index, not proof of a defect or proof "
            "that a file has been manually reviewed."
        ),
        "scan_roots": [path.relative_to(ROOT).as_posix() for path in SCAN_ROOTS],
        "files_scanned": len(file_hashes),
        "file_sha256": file_hashes,
        "finding_count": len(findings),
        "counts_by_rule": dict(sorted(counts.items())),
        "counts_by_severity": dict(sorted(severity_counts.items())),
        "parse_failures": [asdict(item) for item in parse_failures],
        "findings": [asdict(item) for item in findings],
    }


def main() -> None:
    report = scan()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "files_scanned": report["files_scanned"],
                "finding_count": report["finding_count"],
                "parse_failures": len(report["parse_failures"]),
                "output": OUTPUT.relative_to(ROOT).as_posix(),
            },
            sort_keys=True,
        )
    )
    if report["parse_failures"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
