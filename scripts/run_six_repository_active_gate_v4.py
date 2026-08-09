#!/usr/bin/env python3
"""V4 exact-SHA active qualification entry point.

The governed V3 runner remains the single implementation of monotonic timing,
ledger persistence, remote-main identity checks and failure propagation.  This
entry point extends only the ResinDB formal command vector with the real
Chromium bilingual scientific-UI gate required by the V4 acceptance contract.
"""

from __future__ import annotations

import runpy
from pathlib import Path
from typing import Any, Callable

_BASE_RUNNER = Path(__file__).with_name("run_six_repository_active_gate.py")
_STATE: dict[str, Any] = runpy.run_path(str(_BASE_RUNNER))
COMMANDS = _STATE["COMMANDS"]
_BROWSER_GATE = ("npm", "run", "test:ui")

if _BROWSER_GATE in COMMANDS["resindb"]:
    raise RuntimeError("ResinDB browser gate is already present in the base runner")
COMMANDS["resindb"] = (*COMMANDS["resindb"], _BROWSER_GATE)
_STATE["COMMANDS"] = COMMANDS
_BASE_MAIN: Callable[[], int] = _STATE["main"]


def main() -> int:
    """Delegate to the governed runner after applying the V4 command contract."""

    return _BASE_MAIN()


if __name__ == "__main__":
    raise SystemExit(main())
