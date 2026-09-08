from pathlib import Path

from aspenops_nexus import __version__
from aspenops_nexus.config import Settings
from aspenops_nexus.doctor import diagnose


def test_mock_doctor_is_ready_cross_platform(tmp_path: Path) -> None:
    result = diagnose(Settings(state_dir=tmp_path, backend="mock"), probe=True)
    assert result["ready"] is True
    assert result["runtime"]["version"] == __version__
    assert result["compatibility"]["strategy"]
