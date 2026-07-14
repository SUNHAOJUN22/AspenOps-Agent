from __future__ import annotations

import argparse
import json
import tempfile
from importlib.resources import as_file, files
from pathlib import Path

from aspenops_nexus.provenance import verify_run_bundle, write_run_bundle


def _resource(name: str) -> Path:
    with as_file(files("aspenops_nexus.data").joinpath(name)) as path:
        return Path(path)


def _self_test() -> dict[str, object]:
    request = {
        "backend": "mock",
        "model_path": str(_resource("mock-case.json")),
        "registry_path": str(_resource("node-registry.json")),
        "writes": [],
        "reads": [],
    }
    results = [
        {
            "ok": True,
            "communication_ok": True,
            "engine_ok": True,
            "converged": True,
            "feasible": True,
            "elapsed_s": 0.0,
            "diagnostics": {},
            "values": {},
            "units": {},
            "violations": [],
            "balance_residuals": {},
        }
    ]
    with tempfile.TemporaryDirectory(prefix="aspenops-evidence-") as directory:
        bundle = write_run_bundle(
            request=request,
            results=results,
            output_path=Path(directory) / "self-test.zip",
        )
        return verify_run_bundle(bundle)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify an AspenOps evidence bundle")
    parser.add_argument("bundle", nargs="?", type=Path)
    args = parser.parse_args()
    result = verify_run_bundle(args.bundle) if args.bundle is not None else _self_test()
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
