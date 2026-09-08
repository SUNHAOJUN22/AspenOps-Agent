from __future__ import annotations

import importlib.util
import platform
import struct
import sys
from typing import Any

from . import RUNTIME_SCHEMA, __version__
from .compat import compatibility_report
from .config import Settings


def diagnose(settings: Settings, *, probe: bool = False) -> dict[str, Any]:
    report = compatibility_report()
    result: dict[str, Any] = {
        "runtime": {
            "name": "AspenOps",
            "version": __version__,
            "schema": RUNTIME_SCHEMA,
        },
        "host": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "python_bits": struct.calcsize("P") * 8,
            "executable": sys.executable,
        },
        "settings": {
            "backend": settings.backend,
            "mode": settings.mode,
            "license_slots": settings.license_slots,
            "max_workers": settings.max_workers,
            "effective_workers": settings.effective_workers,
            "allowed_roots": [str(x) for x in settings.allowed_roots],
            "state_dir": str(settings.state_dir),
            "visible": settings.visible,
            "worker_max_points": settings.worker_max_points,
            "worker_max_age_s": settings.worker_max_age_s,
        },
        "packages": {
            "psutil": importlib.util.find_spec("psutil") is not None,
            "pywin32": importlib.util.find_spec("win32com") is not None,
            "pythoncom": importlib.util.find_spec("pythoncom") is not None,
            "mcp": importlib.util.find_spec("mcp") is not None,
        },
        "compatibility": report,
        "checks": [],
    }
    checks: list[dict[str, Any]] = result["checks"]
    checks.append(
        {
            "name": "native_windows_for_real_com",
            "passed": platform.system() == "Windows" or settings.backend == "mock",
            "required": settings.backend != "mock",
        }
    )
    checks.append(
        {
            "name": "pywin32_installed",
            "passed": result["packages"]["pywin32"] or settings.backend == "mock",
            "required": settings.backend != "mock",
        }
    )
    checks.append(
        {
            "name": "allowed_roots_configured",
            "passed": bool(settings.allowed_roots) or settings.backend == "mock",
            "required": settings.backend != "mock",
        }
    )
    candidates = report.get(settings.backend, []) if settings.backend != "mock" else ["mock"]
    checks.append(
        {
            "name": "automation_server_candidate",
            "passed": bool(candidates),
            "required": settings.backend != "mock",
            "candidate_count": len(candidates),
        }
    )
    result["ready"] = all(item["passed"] for item in checks if item["required"])
    if probe:
        result["probe_boundary"] = (
            "Doctor enumerates local registrations without opening a licensed case. Run the real "
            "certification workflow with an approved model to prove executable compatibility."
        )
    return result
