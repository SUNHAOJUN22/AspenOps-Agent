from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import psutil
import pytest

from aspenops_nexus.backends import aspen_plus as aspen_module
from aspenops_nexus.backends import hysys as hysys_module
from aspenops_nexus.backends.aspen_plus import AspenPlusBackend, _iter_collection
from aspenops_nexus.backends.base import BackendError
from aspenops_nexus.backends.hysys import HysysBackend
from aspenops_nexus.compat import ComCandidate
from aspenops_nexus.registry import ResolvedNode
from aspenops_nexus.windows_job import ProcessFingerprint


def resolved_node(
    key: str = "value",
    *,
    paths: tuple[str, ...] = ("path-1", "path-2"),
    locator: dict[str, Any] | None = None,
    backend: str = "aspen_plus",
) -> ResolvedNode:
    return ResolvedNode(
        key=key,
        access="readwrite",
        native_unit=None,
        quantity=None,
        paths=paths,
        identifiers={"stream": "FEED"} if paths else {},
        lower=None,
        upper=None,
        integer=False,
        backend=backend,
        locator=locator or {},
        verification="test",
        description="test node",
    )


class IndexedCollection:
    def __init__(
        self,
        values: list[Any],
        *,
        base: int,
        fail_indexes: set[int] | None = None,
    ) -> None:
        self.values = values
        self.base = base
        self.fail_indexes = fail_indexes or set()
        self.Count = len(values)

    def Item(self, index: int) -> Any:
        if index in self.fail_indexes:
            raise RuntimeError("unavailable item")
        offset = index - self.base
        if offset < 0 or offset >= len(self.values):
            raise IndexError(index)
        return self.values[offset]


class BrokenCountCollection:
    @property
    def Count(self) -> int:
        raise RuntimeError("count unavailable")


def test_iter_collection_detects_index_base_once_and_honors_limits() -> None:
    values = ["first", "second", "third"]
    assert list(_iter_collection(IndexedCollection(values, base=0))) == values
    assert list(_iter_collection(IndexedCollection(values, base=1))) == values
    assert list(_iter_collection(IndexedCollection(values, base=1), limit=2)) == values[:2]
    assert list(_iter_collection(IndexedCollection([], base=0))) == []
    assert list(_iter_collection(BrokenCountCollection())) == []


def test_iter_collection_skips_individual_item_failures_without_duplication() -> None:
    collection = IndexedCollection(["first", "second", "third"], base=0, fail_indexes={1})
    assert list(_iter_collection(collection)) == ["first", "third"]


def test_aspen_process_discovery_filters_names_and_bad_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    processes = [
        SimpleNamespace(info={"pid": 1, "name": "apwn.exe"}),
        SimpleNamespace(info={"pid": 2, "name": "AspenPlus.exe"}),
        SimpleNamespace(info={"pid": 3, "name": "notepad.exe"}),
        SimpleNamespace(info={"name": "aspenplus.exe"}),
    ]
    monkeypatch.setattr(aspen_module.psutil, "process_iter", lambda attrs: processes)

    def fingerprint(pid: int) -> ProcessFingerprint | None:
        if pid == 1:
            return ProcessFingerprint(pid, 1.0, 0, "C:/Aspen/apwn.exe")
        return None

    monkeypatch.setattr(aspen_module, "process_fingerprint", fingerprint)
    result = aspen_module._aspen_processes()
    assert list(result) == [1]
    assert result[1].executable.endswith("apwn.exe")


class OpenDocument:
    def __init__(self, *, fail_file2: bool = False, fail_all: bool = False) -> None:
        self.calls: list[tuple[str, str]] = []
        self.closed = False
        self.fail_file2 = fail_file2
        self.fail_all = fail_all

    def InitFromFile2(self, path: str) -> None:
        self.calls.append(("InitFromFile2", path))
        if self.fail_file2 or self.fail_all:
            raise RuntimeError("file2 failed")

    def InitFromArchive2(self, path: str) -> None:
        self.calls.append(("InitFromArchive2", path))
        if self.fail_all:
            raise RuntimeError("archive failed")

    def InitFromFile(self, path: str) -> None:
        self.calls.append(("InitFromFile", path))
        if self.fail_all:
            raise RuntimeError("file failed")

    def Close(self, save: bool) -> None:
        self.closed = True


def test_aspen_open_document_prefers_archive_and_falls_back(tmp_path: Path) -> None:
    archive = tmp_path / "case.bkp"
    document = OpenDocument()
    AspenPlusBackend._open_document(document, archive)
    assert document.calls == [("InitFromArchive2", str(archive))]

    file_path = tmp_path / "case.apw"
    fallback = OpenDocument(fail_file2=True)
    AspenPlusBackend._open_document(fallback, file_path)
    assert fallback.calls == [
        ("InitFromFile2", str(file_path)),
        ("InitFromArchive2", str(file_path)),
    ]


def test_aspen_open_document_reports_all_method_failures(tmp_path: Path) -> None:
    document = OpenDocument(fail_all=True)
    with pytest.raises(BackendError, match="No compatible Aspen document-open method") as caught:
        AspenPlusBackend._open_document(document, tmp_path / "case.apw")
    message = str(caught.value)
    assert "InitFromFile2" in message
    assert "InitFromArchive2" in message
    assert "InitFromFile" in message


class ValueNode:
    def __init__(self, value: Any, *, write_transform: Any | None = None) -> None:
        self._value = value
        self.write_transform = write_transform

    @property
    def Value(self) -> Any:
        return self._value

    @Value.setter
    def Value(self, value: Any) -> None:
        self._value = self.write_transform if self.write_transform is not None else value


class MappingTree:
    def __init__(self, mapping: dict[str, Any]) -> None:
        self.mapping = mapping
        self.calls: list[str] = []

    def FindNode(self, path: str) -> Any:
        self.calls.append(path)
        value = self.mapping.get(path)
        if isinstance(value, BaseException):
            raise value
        return value


def test_aspen_find_node_cache_fallback_read_and_write_verification() -> None:
    first = ValueNode(1.0)
    second = ValueNode(2.0)
    tree = MappingTree({"path-1": first, "path-2": second})
    backend = AspenPlusBackend()
    backend.document = SimpleNamespace(Tree=tree)
    target = resolved_node()

    assert backend.read(target) == 1.0
    assert backend.read(target) == 1.0
    assert tree.calls == ["path-1", "path-1"]
    backend.write(target, 3.0)
    assert first.Value == 3.0

    cache_key = target.key + repr(sorted(target.identifiers.items()))
    backend.path_cache[cache_key] = "missing"
    assert backend.read(target) == 3.0
    assert backend.path_cache[cache_key] == "path-1"

    mismatch = ValueNode(1.0, write_transform=99.0)
    backend.document = SimpleNamespace(Tree=MappingTree({"path-1": mismatch}))
    backend.path_cache.clear()
    with pytest.raises(BackendError, match="write verification failed"):
        backend.write(target, 4.0)


def test_aspen_find_node_errors_are_explicit() -> None:
    backend = AspenPlusBackend()
    with pytest.raises(BackendError, match="No Aspen document"):
        backend.read(resolved_node())

    backend.document = SimpleNamespace(
        Tree=MappingTree({"path-1": RuntimeError("bad path"), "path-2": None})
    )
    with pytest.raises(BackendError, match="No Aspen node resolved") as caught:
        backend.read(resolved_node())
    assert "bad path" in str(caught.value)


def test_aspen_reinitialize_uses_engine_fallback_and_clears_cache() -> None:
    backend = AspenPlusBackend()
    with pytest.raises(BackendError, match="No Aspen document"):
        backend.reinitialize()

    events: list[str] = []

    def fail_document() -> None:
        events.append("document")
        raise RuntimeError("document reset failed")

    def reset_engine() -> None:
        events.append("engine")

    backend.document = SimpleNamespace(
        Reinit=fail_document,
        Engine=SimpleNamespace(Reinit=reset_engine),
    )
    backend.path_cache["cached"] = "path"
    backend.reinitialize()
    assert events == ["document", "engine"]
    assert backend.path_cache == {}

    backend.document = SimpleNamespace(Reinit=fail_document, Engine=None)
    with pytest.raises(BackendError, match="reinitialization failed"):
        backend.reinitialize()


class MessageItem:
    def __init__(self, **attributes: Any) -> None:
        self.attributes = attributes

    def __getattr__(self, name: str) -> Any:
        if name not in self.attributes:
            raise AttributeError(name)
        value = self.attributes[name]
        if isinstance(value, BaseException):
            raise value
        return value

    def __str__(self) -> str:
        return "fallback-message"


def test_aspen_status_messages_running_and_runtime_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_status = ValueNode("converged")
    default_status = ValueNode("completed")
    extra_status = ValueNode("custom ok")
    tree = MappingTree(
        {
            "registry-path": registry_status,
            "extra-path": extra_status,
            aspen_module._DEFAULT_STATUS_PATHS[0]: default_status,
            aspen_module._DEFAULT_STATUS_PATHS[1]: RuntimeError("unavailable"),
        }
    )
    errors = IndexedCollection([MessageItem(Description="error one")], base=1)
    messages = IndexedCollection(
        [
            MessageItem(Description=RuntimeError("bad description"), Text="message two"),
            MessageItem(),
        ],
        base=0,
    )
    engine = SimpleNamespace(Errors=errors, Messages=messages, Warnings=None)
    document = SimpleNamespace(
        Tree=tree,
        Engine=engine,
        Version="40.0",
        VersionNumber=40,
        Name="Aspen Plus",
        FullName=None,
    )
    backend = AspenPlusBackend()
    backend.document = document
    backend.progid = "Apwn.Document.40.0"
    backend.model_path = Path("case.bkp")
    backend.configure_convergence_nodes([resolved_node("status", paths=("registry-path",))])
    monkeypatch.setenv("ASPENOPS_STATUS_PATHS", " extra-path ; ;")

    status = backend._status_values()
    assert status[0]["value"] == "converged"
    assert any(item.get("path") == "extra-path" for item in status)
    assert any(item.get("value") == "completed" for item in status)
    assert backend._engine_messages() == [
        "error one",
        "message two",
        "fallback-message",
    ]

    assert AspenPlusBackend._engine_running(SimpleNamespace(IsRunning=False)) is False
    assert AspenPlusBackend._engine_running(SimpleNamespace(Running=lambda: True)) is True
    assert AspenPlusBackend._engine_running(SimpleNamespace()) is None

    identity = backend.runtime_identity()
    assert identity["progid"] == "Apwn.Document.40.0"
    assert identity["exposed"] == {
        "Version": "40.0",
        "VersionNumber": "40",
        "Name": "Aspen Plus",
    }
    assert identity["model_path"].endswith("case.bkp")


def test_aspen_status_and_messages_are_empty_without_document() -> None:
    backend = AspenPlusBackend()
    assert backend._status_values() == []
    assert backend._engine_messages() == []
    with pytest.raises(BackendError, match="No Aspen document"):
        backend.run()


def test_aspen_close_suppresses_document_errors_and_uninitializes_com(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    class BrokenDocument:
        def Close(self, save: bool) -> None:
            events.append("close")
            raise RuntimeError("close failed")

    pythoncom = ModuleType("pythoncom")
    pythoncom.CoUninitialize = lambda: events.append("uninitialize")  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pythoncom", pythoncom)
    backend = AspenPlusBackend()
    backend.document = BrokenDocument()
    backend.path_cache["cached"] = "path"
    backend._coinitialized = True
    backend.close()
    assert backend.document is None
    assert backend.path_cache == {}
    assert backend._coinitialized is False
    assert events == ["close", "uninitialize"]


class TimeoutProcess:
    def __init__(self) -> None:
        self.terminated = False
        self.killed = False

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: float) -> None:
        raise psutil.TimeoutExpired(timeout)

    def kill(self) -> None:
        self.killed = True


def test_aspen_cleanup_kills_verified_timeout_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fingerprint = ProcessFingerprint(42, 1.0, 10, "C:/Aspen/apwn.exe")
    process = TimeoutProcess()
    backend = AspenPlusBackend()
    backend.worker_pid = 10
    backend.owned_processes = {42: fingerprint}
    monkeypatch.setattr(aspen_module, "fingerprint_matches", lambda item: True)
    monkeypatch.setattr(aspen_module, "is_descendant", lambda pid, ancestor: True)
    monkeypatch.setattr(aspen_module.psutil, "Process", lambda pid: process)
    backend.cleanup_owned_pids()
    assert process.terminated is True
    assert process.killed is True


def install_fake_com(
    monkeypatch: pytest.MonkeyPatch,
    dispatch: Any,
) -> list[str]:
    events: list[str] = []
    pythoncom = ModuleType("pythoncom")
    pythoncom.COINIT_APARTMENTTHREADED = 2  # type: ignore[attr-defined]
    pythoncom.CoInitializeEx = lambda mode: events.append(f"init:{mode}")  # type: ignore[attr-defined]
    pythoncom.CoUninitialize = lambda: events.append("uninit")  # type: ignore[attr-defined]
    client = ModuleType("win32com.client")
    client.DispatchEx = dispatch  # type: ignore[attr-defined]
    win32com = ModuleType("win32com")
    win32com.client = client  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pythoncom", pythoncom)
    monkeypatch.setitem(sys.modules, "win32com", win32com)
    monkeypatch.setitem(sys.modules, "win32com.client", client)
    return events


def test_aspen_open_rejects_nonwindows_and_tracks_owned_descendants(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = AspenPlusBackend()
    monkeypatch.setattr(aspen_module.platform, "system", lambda: "Linux")
    with pytest.raises(BackendError, match="native Windows"):
        backend.open(tmp_path / "case.bkp")

    model = tmp_path / "case.apw"
    model.write_text("model", encoding="utf-8")
    document = OpenDocument()
    events = install_fake_com(monkeypatch, lambda progid: document)
    monkeypatch.setattr(aspen_module.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        aspen_module,
        "discover_aspen_plus_candidates",
        lambda: [ComCandidate("aspen_plus", "Apwn.Document.40.0", (40, 0), "64-bit")],
    )
    fingerprint = ProcessFingerprint(101, 1.0, backend.worker_pid, "C:/Aspen/apwn.exe")
    snapshots = iter([{}, {101: fingerprint}])
    monkeypatch.setattr(aspen_module, "_aspen_processes", lambda: next(snapshots))
    monkeypatch.setattr(aspen_module, "is_descendant", lambda pid, ancestor: True)
    monkeypatch.setenv("ASPENOPS_COM_SETTLE_S", "0")
    backend.open(model, visible=True)
    assert backend.document is document
    assert backend.progid == "Apwn.Document.40.0"
    assert backend.model_path == model.resolve()
    assert backend.owned_processes == {101: fingerprint}
    assert events == ["init:2"]


def test_aspen_open_records_candidate_failures_and_closes_documents(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = tmp_path / "case.apw"
    model.write_text("model", encoding="utf-8")
    failed = OpenDocument(fail_all=True)
    install_fake_com(monkeypatch, lambda progid: failed)
    monkeypatch.setattr(aspen_module.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        aspen_module,
        "discover_aspen_plus_candidates",
        lambda: [ComCandidate("aspen_plus", "Apwn.Document.1", (1,), "64-bit")],
    )
    monkeypatch.setattr(aspen_module, "_aspen_processes", lambda: {})
    backend = AspenPlusBackend()
    with pytest.raises(BackendError, match="Unable to create Aspen Plus"):
        backend.open(model)
    assert failed.closed is True
    assert backend.open_errors and "Apwn.Document.1" in backend.open_errors[0]


def hysys_node(
    key: str = "cell",
    *,
    spreadsheet: str | None = "ASPENOPS_IO",
    cell: str | None = "B2",
) -> ResolvedNode:
    locator: dict[str, Any] = {}
    if spreadsheet is not None:
        locator["spreadsheet"] = spreadsheet
    if cell is not None:
        locator["cell"] = cell
    return resolved_node(key, paths=(), locator=locator, backend="hysys")


class FakeCell:
    def __init__(self, value: Any, *, write_transform: Any | None = None) -> None:
        self._value = value
        self.write_transform = write_transform

    @property
    def CellValue(self) -> Any:
        return self._value

    @CellValue.setter
    def CellValue(self, value: Any) -> None:
        self._value = self.write_transform if self.write_transform is not None else value


class FakeSheet:
    def __init__(self, cells: dict[str, FakeCell]) -> None:
        self.cells = cells

    def Cell(self, name: str) -> FakeCell:
        return self.cells[name]


class FakeOperations:
    def __init__(self, sheets: dict[str, FakeSheet]) -> None:
        self.sheets = sheets

    def Item(self, name: str) -> FakeSheet:
        return self.sheets[name]


def fake_case(cells: dict[str, FakeCell] | None = None) -> Any:
    cells = cells or {"B2": FakeCell(1.0)}
    return SimpleNamespace(
        Flowsheet=SimpleNamespace(Operations=FakeOperations({"ASPENOPS_IO": FakeSheet(cells)})),
        Solver=SimpleNamespace(CanSolve=False, IsSolving=False),
    )


def test_hysys_cell_read_write_and_locator_errors() -> None:
    backend = HysysBackend()
    with pytest.raises(BackendError, match="No HYSYS case"):
        backend.read(hysys_node())

    backend.case = fake_case()
    with pytest.raises(BackendError, match="requires spreadsheet and cell"):
        backend.read(hysys_node(spreadsheet=None))
    with pytest.raises(BackendError, match="Unable to resolve HYSYS"):
        backend.read(hysys_node(cell="Z99"))

    target = hysys_node()
    assert backend.read(target) == 1.0
    backend.write(target, 2.0)
    assert backend.read(target) == 2.0

    mismatch = FakeCell(1.0, write_transform=99.0)
    backend.case = fake_case({"B2": mismatch})
    with pytest.raises(BackendError, match="write verification failed"):
        backend.write(target, 3.0)


def test_hysys_reinitialize_success_and_failure() -> None:
    backend = HysysBackend()
    with pytest.raises(BackendError, match="No HYSYS case"):
        backend.reinitialize()

    solver = SimpleNamespace(CanSolve=False)
    backend.case = SimpleNamespace(Solver=solver)
    backend.reinitialize()
    assert solver.CanSolve is True

    class BrokenSolver:
        @property
        def CanSolve(self) -> bool:
            return False

        @CanSolve.setter
        def CanSolve(self, value: bool) -> None:
            raise RuntimeError("reset failed")

    backend.case = SimpleNamespace(Solver=BrokenSolver())
    with pytest.raises(BackendError, match="Unable to reset HYSYS"):
        backend.reinitialize()


def test_hysys_solver_normalization_status_and_runtime_identity() -> None:
    assert HysysBackend._solver_running(SimpleNamespace(IsSolving=False)) is False
    assert HysysBackend._solver_running(SimpleNamespace(Solving=lambda: True)) is True
    assert HysysBackend._solver_running(SimpleNamespace()) is None
    assert HysysBackend._normalize_convergence_value(True) == "converged"
    assert HysysBackend._normalize_convergence_value(False) == "not converged"
    assert HysysBackend._normalize_convergence_value(1) == "converged"
    assert HysysBackend._normalize_convergence_value(0.0) == "not converged"
    assert HysysBackend._normalize_convergence_value(2) == 2

    backend = HysysBackend()
    backend.case = fake_case({"B2": FakeCell(True)})
    backend.application = SimpleNamespace(Version="15", Name="HYSYS", FullName=None)
    backend.case.Version = "case-version"
    backend.case.Name = "case-name"
    backend.case.FullName = None
    backend.progid = "HYSYS.Application.15"
    backend.model_path = Path("case.hsc")
    backend.configure_convergence_nodes([hysys_node("status")])
    status = backend._status_values()
    assert status == [
        {
            "key": "status",
            "source": "registry",
            "raw_value": True,
            "value": "converged",
        }
    ]
    identity = backend.runtime_identity()
    assert identity["exposed"] == {
        "application.Version": "15",
        "application.Name": "HYSYS",
        "case.Version": "case-version",
        "case.Name": "case-name",
    }
    assert identity["convergence_contract_nodes"] == ["status"]
    assert identity["model_path"].endswith("case.hsc")


def test_hysys_status_records_read_errors() -> None:
    backend = HysysBackend()
    backend.case = fake_case()
    backend.configure_convergence_nodes([hysys_node("missing", cell="Z99")])
    status = backend._status_values()
    assert status[0]["key"] == "missing"
    assert "BackendError" in status[0]["error"]
    with pytest.raises(BackendError, match="No HYSYS case"):
        HysysBackend().run()


def test_hysys_close_suppresses_errors_and_uninitializes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    class BrokenCase:
        def Close(self, save: bool) -> None:
            events.append("case-close")
            raise RuntimeError("close failed")

    class BrokenApplication:
        def Quit(self) -> None:
            events.append("quit")
            raise RuntimeError("quit failed")

    pythoncom = ModuleType("pythoncom")
    pythoncom.CoUninitialize = lambda: events.append("uninit")  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pythoncom", pythoncom)
    backend = HysysBackend()
    backend.case = BrokenCase()
    backend.application = BrokenApplication()
    backend._coinitialized = True
    backend.close()
    assert events == ["case-close", "quit", "uninit"]
    assert backend.case is None
    assert backend.application is None
    assert backend._coinitialized is False


class FakeSimulationCases:
    def __init__(self, case: Any, *, fail: bool = False) -> None:
        self.case = case
        self.fail = fail

    def Open(self, path: str) -> Any:
        if self.fail:
            raise RuntimeError("open failed")
        return self.case


class FakeHysysApplication:
    def __init__(self, case: Any, *, fail: bool = False) -> None:
        self.SimulationCases = FakeSimulationCases(case, fail=fail)
        self.Visible = False
        self.quit_calls = 0

    def Quit(self) -> None:
        self.quit_calls += 1


def test_hysys_open_rejects_nonwindows_and_opens_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = HysysBackend()
    monkeypatch.setattr(hysys_module.platform, "system", lambda: "Linux")
    with pytest.raises(BackendError, match="native Windows"):
        backend.open(tmp_path / "case.hsc")

    model = tmp_path / "case.hsc"
    model.write_text("model", encoding="utf-8")
    case = fake_case()
    application = FakeHysysApplication(case)
    events = install_fake_com(monkeypatch, lambda progid: application)
    monkeypatch.setattr(hysys_module.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        hysys_module,
        "discover_hysys_candidates",
        lambda: [ComCandidate("hysys", "HYSYS.Application.15", (15,), "64-bit")],
    )
    backend.open(model, visible=True)
    assert backend.application is application
    assert backend.case is case
    assert backend.model_path == model.resolve()
    assert backend.progid == "HYSYS.Application.15"
    assert application.Visible is True
    assert events == ["init:2"]


def test_hysys_open_records_failure_and_quits_application(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = tmp_path / "case.hsc"
    model.write_text("model", encoding="utf-8")
    application = FakeHysysApplication(fake_case(), fail=True)
    install_fake_com(monkeypatch, lambda progid: application)
    monkeypatch.setattr(hysys_module.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        hysys_module,
        "discover_hysys_candidates",
        lambda: [ComCandidate("hysys", "HYSYS.Application.1", (1,), "64-bit")],
    )
    backend = HysysBackend()
    with pytest.raises(BackendError, match="Unable to create HYSYS"):
        backend.open(model)
    assert application.quit_calls == 1
    assert backend.open_errors and "HYSYS.Application.1" in backend.open_errors[0]
