from pathlib import Path

from aspenops.backends.mock import MockBackend
from aspenops.models import RunState


def test_mock_run_and_save(tmp_path: Path) -> None:
    backend = MockBackend()
    backend.open_case(tmp_path / "input.json")
    report = backend.run()
    assert report.state == RunState.CONVERGED
    assert 0 < float(backend.get_raw("mock.reactor.conversion").value) < 1
    output = tmp_path / "saved.json"
    backend.save(output)
    assert output.exists()
    diagnosis = backend.diagnose()
    assert diagnosis["opened"] is True
    backend.close()


def test_mock_divergence() -> None:
    backend = MockBackend()
    backend.open_case(Path("unused.json"))
    backend.set_raw("mock.reactor.temperature", 700, "C")
    report = backend.run()
    assert report.state == RunState.FAILED


def test_mock_error_paths(tmp_path: Path) -> None:
    backend = MockBackend()
    import pytest

    from aspenops.errors import CaseOpenError, SimulationError

    with pytest.raises(SimulationError):
        backend.get_raw("mock.feed.temperature")
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    with pytest.raises(CaseOpenError):
        backend.open_case(bad)
    backend.open_case(Path("unused.json"))
    with pytest.raises(SimulationError):
        backend.get_raw("missing")
    with pytest.raises(SimulationError):
        backend.set_raw("missing", 1)
