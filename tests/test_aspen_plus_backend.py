from pathlib import Path

import pytest

from aspenops.backends.aspen_plus import AspenPlusBackend
from aspenops.errors import AccessViolation, CaseOpenError
from aspenops.models import RunState


def test_status_classification_fails_closed() -> None:
    assert AspenPlusBackend._classify_status(None, []) == RunState.UNKNOWN
    assert AspenPlusBackend._classify_status("unrecognized", []) == RunState.UNKNOWN
    assert AspenPlusBackend._classify_status("Completed", []) == RunState.CONVERGED
    assert AspenPlusBackend._classify_status(None, ["solver diverged"]) == RunState.FAILED
    assert AspenPlusBackend._classify_status("completed", ["fatal error"]) == RunState.FAILED


def test_read_only_open_never_falls_back_to_writable_signature() -> None:
    class WritableOnlyDocument:
        def __init__(self) -> None:
            self.opened = False

        def InitFromArchive2(self, path: str) -> None:
            del path
            self.opened = True

    backend = AspenPlusBackend()
    document = WritableOnlyDocument()
    with pytest.raises(CaseOpenError, match="read-only"):
        backend._open_document(document, Path("case.bkp"), read_only=True)
    assert not document.opened
    backend._open_document(document, Path("case.bkp"), read_only=False)
    assert document.opened


def test_read_only_backend_rejects_mutation_and_save() -> None:
    backend = AspenPlusBackend()
    backend._read_only = True
    with pytest.raises(AccessViolation, match="Read-only"):
        backend.set_raw("\\Data\\Streams\\FEED\\Input\\TEMP", 100.0, "C")
    with pytest.raises(AccessViolation, match="Read-only"):
        backend.save()
