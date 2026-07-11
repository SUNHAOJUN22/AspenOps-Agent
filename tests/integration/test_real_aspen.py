import os
import platform
from pathlib import Path

import pytest

from aspenops.models import RunState
from aspenops.service import SessionManager


@pytest.mark.aspen_integration
def test_open_and_run_real_aspen_case() -> None:
    case_raw = os.getenv("ASPENOPS_TEST_CASE")
    if platform.system() != "Windows" or not case_raw:
        pytest.skip("Requires Windows, Aspen Plus and ASPENOPS_TEST_CASE")
    case = Path(case_raw)
    manager = SessionManager(allowed_roots=[case.parent], default_timeout_s=1200)
    session = manager.open_session(case, backend="aspen_plus", read_only=True)
    try:
        manager.reinitialize(session.session_id)
        report = manager.run(session.session_id)
        assert report.state == RunState.CONVERGED, report.messages
        diagnosis = manager.diagnose(session.session_id)
        assert diagnosis["progid"]
    finally:
        manager.close_all()
