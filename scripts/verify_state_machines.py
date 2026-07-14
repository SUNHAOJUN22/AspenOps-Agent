from __future__ import annotations

import json

from aspenops_nexus.state_machines import ALL_STATE_MACHINES


def main() -> int:
    summary: list[dict[str, object]] = []
    for spec in ALL_STATE_MACHINES:
        spec.validate_complete()
        summary.append(
            {
                "name": spec.name,
                "initial": spec.initial,
                "states": len(spec.states),
                "transitions": len(spec.transitions),
                "terminal": sorted(spec.terminal),
                "status": "PASS",
            }
        )
    print(json.dumps({"schema": "aspenops.state-machines/v1", "machines": summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
