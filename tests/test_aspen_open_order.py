from pathlib import Path

from aspenops_nexus.backends.aspen_plus import AspenPlusBackend


class ArchiveFallbackDocument:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def InitFromArchive2(self, path: str) -> None:
        self.calls.append("InitFromArchive2")
        raise RuntimeError("archive method unavailable")

    def InitFromFile2(self, path: str) -> None:
        self.calls.append("InitFromFile2")
        raise RuntimeError("file2 method unavailable")

    def InitFromFile(self, path: str) -> None:
        self.calls.append("InitFromFile")


def test_archive_open_fallback_attempts_each_method_once() -> None:
    document = ArchiveFallbackDocument()
    AspenPlusBackend._open_document(document, Path("case.bkp"))
    assert document.calls == [
        "InitFromArchive2",
        "InitFromFile2",
        "InitFromFile",
    ]
