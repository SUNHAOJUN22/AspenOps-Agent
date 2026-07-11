"""AspenOps command-line interface."""

from __future__ import annotations

import json
import platform
import tempfile
from pathlib import Path
from typing import Annotated

import typer

from aspenops import __version__
from aspenops.compat import discover_aspen_progids, probe_aspen_automation
from aspenops.errors import AspenOpsError
from aspenops.models import ValueRead, ValueWrite
from aspenops.registry import load_bundled_registry
from aspenops.service import SessionManager

app = typer.Typer(
    name="aspenops",
    help="Version-adaptive Aspen Plus automation runtime.",
    no_args_is_help=True,
)


@app.command()
def version() -> None:
    """Print the runtime version."""
    typer.echo(__version__)


@app.command()
def doctor(
    probe: Annotated[
        bool,
        typer.Option("--probe", help="Create and close an Aspen COM document on Windows."),
    ] = False,
) -> None:
    """Inspect host, COM discovery and bundled registry state."""
    report: dict[str, object] = {
        "aspenops_version": __version__,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "registered_progids": [
            {
                "progid": item.progid,
                "version": [item.major, item.minor],
                "registry_view": item.registry_view,
                "clsid": item.clsid,
            }
            for item in discover_aspen_progids()
        ],
        "registry_nodes": len(load_bundled_registry().keys()),
    }
    if probe:
        try:
            report["probe"] = probe_aspen_automation()
        except AspenOpsError as exc:
            report["probe_error"] = str(exc)
    typer.echo(json.dumps(report, ensure_ascii=False, indent=2))


@app.command("registry")
def registry_command() -> None:
    """List semantic keys in the bundled allowlisted registry."""
    registry = load_bundled_registry()
    rows = []
    keys = registry.keys()
    for key in keys:
        spec = registry.get(key)
        rows.append(
            {
                "key": key,
                "access": spec.access.value,
                "quantity": spec.quantity,
                "unit": spec.default_unit,
                "status": spec.status,
                "identifiers": sorted(spec.identifiers),
            }
        )
    typer.echo(json.dumps(rows, ensure_ascii=False, indent=2))


@app.command()
def demo() -> None:
    """Run a complete no-Aspen smoke test through a spawned Mock worker."""
    with tempfile.TemporaryDirectory(prefix="aspenops-demo-") as directory:
        case_path = Path(directory) / "case.json"
        case_path.write_text("{}", encoding="utf-8")
        manager = SessionManager(allowed_roots=[Path(directory)], default_timeout_s=30)
        session = manager.open_session(case_path, backend="mock")
        try:
            manager.set_values(
                session.session_id,
                [
                    ValueWrite(
                        key="stream.input.temperature",
                        identifiers={"stream": "FEED"},
                        value=95,
                        unit="C",
                    ),
                    ValueWrite(
                        key="block.input.temperature",
                        identifiers={"block": "R-101"},
                        value=440,
                        unit="C",
                    ),
                ],
            )
            run = manager.run(session.session_id)
            values = manager.get_values(
                session.session_id,
                [
                    ValueRead(
                        key="stream.output.temperature",
                        identifiers={"stream": "PRODUCT"},
                        unit="C",
                    ),
                    ValueRead(
                        key="block.output.conversion",
                        identifiers={"block": "R-101"},
                        unit="fraction",
                    ),
                ],
            )
            typer.echo(
                json.dumps(
                    {
                        "run": run.model_dump(mode="json"),
                        "values": [item.model_dump(mode="json") for item in values],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        finally:
            manager.close_all()


@app.command("run-case")
def run_case(
    case: Annotated[Path, typer.Argument(help="Path to .bkp/.apw/.apwz or mock .json case")],
    backend: Annotated[str, typer.Option(help="aspen_plus or mock")] = "aspen_plus",
    visible: Annotated[bool, typer.Option(help="Show the Aspen GUI.")] = False,
    timeout_s: Annotated[float, typer.Option(min=1.0)] = 600.0,
) -> None:
    """Open, reinitialize, run and diagnose one case."""
    manager = SessionManager(allowed_roots=[case.resolve().parent], default_timeout_s=timeout_s)
    session = manager.open_session(case, backend=backend, visible=visible)
    try:
        manager.reinitialize(session.session_id)
        run = manager.run(session.session_id)
        diagnosis = manager.diagnose(session.session_id)
        typer.echo(
            json.dumps(
                {"run": run.model_dump(mode="json"), "diagnosis": diagnosis},
                ensure_ascii=False,
                indent=2,
            )
        )
        if run.state.value != "converged":
            raise typer.Exit(code=2)
    finally:
        manager.close_all()


def main() -> None:
    app()


if __name__ == "__main__":
    main()
