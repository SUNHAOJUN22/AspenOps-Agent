from pathlib import Path

from test_batch import request

from aspenops_nexus.certification import certify_batch_document
from aspenops_nexus.config import Settings


def test_mock_certification_is_deterministic(tmp_path: Path) -> None:
    report = certify_batch_document(
        request(),
        Settings(state_dir=tmp_path, max_workers=2, license_slots=2),
        repeats=2,
    )
    assert report["passed"] is True
    assert report["deterministic"] is True
    assert report["max_absolute_error"] == 0
