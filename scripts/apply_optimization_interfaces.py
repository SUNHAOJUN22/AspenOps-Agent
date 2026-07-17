from __future__ import annotations

import importlib.util
from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Expected patch marker not found in {path}: {old[:80]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def apply_strict_module_if_staged(root: Path) -> None:
    migration = root / "scripts/apply_optimization_strict_types.py"
    if not migration.exists():
        return
    spec = importlib.util.spec_from_file_location("optimization_type_migration", migration)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load staged optimization type migration")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    target = getattr(module, "TARGET")
    (root / "src/aspenops_nexus/optimization.py").write_text(target, encoding="utf-8")
    migration.unlink(missing_ok=True)
    (root / ".github/workflows/apply-optimization-strict-types.yml").unlink(
        missing_ok=True
    )


def patch_optimization(root: Path) -> None:
    path = root / "src/aspenops_nexus/optimization.py"
    replace_once(
        path,
        'if TYPE_CHECKING:\n    from .pool_manager import PoolManager\n',
        'if TYPE_CHECKING:\n    from .pool import CasePool\n    from .pool_manager import PoolManager\n',
    )
    replace_once(
        path,
        "        cancel_check: Callable[[], bool] | None,\n    ) -> None:\n",
        "        cancel_check: Callable[[], bool] | None,\n"
        "        pool_observer: Callable[[CasePool | None], None] | None,\n"
        "    ) -> None:\n",
    )
    replace_once(
        path,
        "        self.cancel_check = cancel_check\n        self.trace: list[OptimizationTracePoint] = []\n",
        "        self.cancel_check = cancel_check\n"
        "        self.pool_observer = pool_observer\n"
        "        self.trace: list[OptimizationTracePoint] = []\n",
    )
    replace_once(
        path,
        "            cancel_check=self.cancel_check,\n        )\n",
        "            cancel_check=self.cancel_check,\n"
        "            pool_observer=self.pool_observer,\n"
        "        )\n",
    )
    replace_once(
        path,
        "    cancel_check: Callable[[], bool] | None = None,\n) -> dict[str, Any]:\n",
        "    cancel_check: Callable[[], bool] | None = None,\n"
        "    pool_observer: Callable[[CasePool | None], None] | None = None,\n"
        ") -> dict[str, Any]:\n",
    )
    replace_once(
        path,
        "    evaluator = _Evaluator(problem, settings, pool_manager, cancel_check)\n",
        "    evaluator = _Evaluator(\n"
        "        problem, settings, pool_manager, cancel_check, pool_observer\n"
        "    )\n",
    )


def patch_scheduler(root: Path) -> None:
    path = root / "src/aspenops_nexus/scheduler.py"
    replace_once(
        path,
        "from .hashing import canonical_hash\nfrom .pool import CasePool\n",
        "from .hashing import canonical_hash\n"
        "from .optimization import OptimizationProblem, run_optimization_document\n"
        "from .pool import CasePool\n",
    )
    replace_once(
        path,
        "    def submit(self, request: dict[str, Any]) -> str:\n"
        "        dry_run_document(request, self.settings)\n"
        "        self.start()\n"
        "        return self.store.create(request, self.settings.job_max_attempts)\n",
        "    def submit(self, request: dict[str, Any]) -> str:\n"
        "        if \"optimization\" in request:\n"
        "            OptimizationProblem.from_document(request)\n"
        "            dry_run_document(\n"
        "                {key: value for key, value in request.items() if key != \"optimization\"},\n"
        "                self.settings,\n"
        "            )\n"
        "        else:\n"
        "            dry_run_document(request, self.settings)\n"
        "        self.start()\n"
        "        return self.store.create(request, self.settings.job_max_attempts)\n",
    )
    old = (
        "                results = run_batch_document(\n"
        "                    request,\n"
        "                    self.settings,\n"
        "                    pool_manager=self.pool_manager,\n"
        "                    cancel_check=partial(self.store.is_cancel_requested, job_id),\n"
        "                    pool_observer=partial(self._observe_pool, job_id),\n"
        "                )\n"
    )
    new = (
        "                cancel_check = partial(self.store.is_cancel_requested, job_id)\n"
        "                pool_observer = partial(self._observe_pool, job_id)\n"
        "                if \"optimization\" in request:\n"
        "                    optimization_result = run_optimization_document(\n"
        "                        request,\n"
        "                        self.settings,\n"
        "                        pool_manager=self.pool_manager,\n"
        "                        cancel_check=cancel_check,\n"
        "                        pool_observer=pool_observer,\n"
        "                    )\n"
        "                    results = [optimization_result]\n"
        "                else:\n"
        "                    results = run_batch_document(\n"
        "                        request,\n"
        "                        self.settings,\n"
        "                        pool_manager=self.pool_manager,\n"
        "                        cancel_check=cancel_check,\n"
        "                        pool_observer=pool_observer,\n"
        "                    )\n"
    )
    replace_once(path, old, new)


def patch_cli(root: Path) -> None:
    path = root / "src/aspenops_nexus/cli.py"
    replace_once(
        path,
        "from .doctor import diagnose\nfrom .provenance import verify_run_bundle, write_run_bundle\n",
        "from .doctor import diagnose\n"
        "from .optimization import run_optimization_document\n"
        "from .pool_manager import PoolManager\n"
        "from .provenance import verify_run_bundle, write_run_bundle\n",
    )
    marker = "\ndef command_certify(args: argparse.Namespace) -> int:\n"
    command = '''
def command_optimize(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    document = _load(args.request)
    with PoolManager(
        cache_path=settings.state_dir / "cache.sqlite3",
        license_slots=settings.license_slots,
        max_resident_cases=settings.max_resident_cases,
        idle_timeout_s=settings.pool_idle_timeout_s,
        worker_max_points=settings.worker_max_points,
        worker_max_age_s=settings.worker_max_age_s,
        startup_timeout_s=settings.startup_timeout_s,
        cache_failures=settings.cache_failures,
    ) as pool_manager:
        result = run_optimization_document(
            document,
            settings,
            pool_manager=pool_manager,
        )
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    _json_print({"result_path": str(output), "result": result})
    return 0 if result["status"] == "completed" else 2


'''
    replace_once(path, marker, "\n" + command + "def command_certify(args: argparse.Namespace) -> int:\n")
    parser_marker = (
        "    certify = sub.add_parser(\"certify\", help=\"Repeat from independent model copies\")\n"
    )
    optimize_parser = (
        "    optimize = sub.add_parser(\n"
        "        \"optimize\", help=\"Run a budgeted batch constrained optimization\"\n"
        "    )\n"
        "    optimize.add_argument(\"request\")\n"
        "    optimize.add_argument(\n"
        "        \"--output\", default=\"var/optimization-result.json\"\n"
        "    )\n"
        "    optimize.set_defaults(func=command_optimize)\n\n"
    )
    replace_once(path, parser_marker, optimize_parser + parser_marker)


def patch_mcp(root: Path) -> None:
    path = root / "src/aspenops_nexus/mcp_server.py"
    marker = (
        "    @mcp.tool()\n"
        "    def job_status(job_id: str) -> dict[str, Any]:\n"
    )
    tools = '''    @mcp.tool()
    def submit_optimization(request: dict[str, Any]) -> dict[str, str]:
        """Submit a durable budgeted optimization job."""
        if "optimization" not in request:
            raise ValueError("Optimization request requires an optimization object")
        return {"job_id": scheduler.submit(request)}

    @mcp.tool()
    def optimization_status(job_id: str) -> dict[str, Any]:
        """Return durable optimization lease, progress and cancellation state."""
        record = scheduler.store.get(job_id)
        return {"found": record is not None, "job": record}

    @mcp.tool()
    def optimization_result(job_id: str) -> dict[str, Any]:
        """Return the completed or cancelled optimization result."""
        record = scheduler.store.get(job_id)
        if record is None:
            return {"found": False}
        results = record.get("results")
        result = None
        if isinstance(results, list) and results:
            result = results[0]
        return {
            "found": True,
            "status": record["status"],
            "result": result,
            "bundle_path": record["bundle_path"],
            "error": record["error"],
        }

    @mcp.tool()
    def cancel_optimization(job_id: str) -> dict[str, Any]:
        """Cancel a pending optimization or enforce its active worker deadline."""
        return {"cancel_requested": scheduler.cancel(job_id)}

'''
    replace_once(path, marker, tools + marker)


def patch_mcp_test(root: Path) -> None:
    path = root / "tests/test_mcp.py"
    replace_once(
        path,
        '        "submit_batch",\n        "job_status",\n',
        '        "submit_batch",\n'
        '        "submit_optimization",\n'
        '        "optimization_status",\n'
        '        "optimization_result",\n'
        '        "cancel_optimization",\n'
        '        "job_status",\n',
    )


def add_interface_tests(root: Path) -> None:
    path = root / "tests/test_optimization_interfaces.py"
    path.write_text(
        '''from __future__ import annotations

import time
from pathlib import Path

from aspenops_nexus.cli import build_parser
from aspenops_nexus.config import Settings
from aspenops_nexus.scheduler import BackgroundScheduler
from test_optimization import document


def test_cli_exposes_optimize_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["optimize", "request.json"])
    assert args.command == "optimize"
    assert args.output == "var/optimization-result.json"


def test_scheduler_runs_durable_optimization(tmp_path: Path) -> None:
    scheduler = BackgroundScheduler(
        Settings(
            state_dir=tmp_path,
            max_workers=2,
            license_slots=2,
            scheduler_poll_s=0.02,
        )
    )
    job_id = scheduler.submit(document())
    deadline = time.time() + 30
    record = None
    while time.time() < deadline:
        record = scheduler.store.get(job_id)
        if record and record["status"] in {"completed", "failed", "dead_letter"}:
            break
        time.sleep(0.05)
    scheduler.stop()
    assert record is not None
    assert record["status"] == "completed", record
    assert record["results"][0]["schema"] == "aspenops.optimization-result/v1"
    assert record["results"][0]["evaluations"] == 8
    assert Path(record["bundle_path"]).exists()
''',
        encoding="utf-8",
    )


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    apply_strict_module_if_staged(root)
    patch_optimization(root)
    patch_scheduler(root)
    patch_cli(root)
    patch_mcp(root)
    patch_mcp_test(root)
    add_interface_tests(root)
    (root / "scripts/apply_optimization_interfaces.py").unlink(missing_ok=True)
    (root / ".github/workflows/apply-optimization-interfaces.yml").unlink(
        missing_ok=True
    )


if __name__ == "__main__":
    main()
