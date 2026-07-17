from __future__ import annotations

from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Expected marker missing from {path}: {old[:80]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_base(root: Path) -> None:
    path = root / "src/aspenops_nexus/backends/base.py"
    marker = "    @abstractmethod\n    def runtime_identity(self) -> dict[str, Any]: ...\n\n"
    replacement = marker + (
        "    def set_process_supervision(self, job_managed: bool) -> None:\n"
        "        del job_managed\n\n"
    )
    replace_once(path, marker, replacement)


def patch_worker(root: Path) -> None:
    path = root / "src/aspenops_nexus/worker.py"
    replace_once(
        path,
        "from .registry import NodeRegistry\n",
        "from .registry import NodeRegistry\nfrom .windows_job import WindowsJobScope\n",
    )
    replace_once(
        path,
        "    backend = create_backend(backend_name)\n"
        "    registry = NodeRegistry(registry_path)\n"
        "    try:\n"
        "        backend.open(Path(source_model), visible=visible)\n",
        "    backend = create_backend(backend_name)\n"
        "    registry = NodeRegistry(registry_path)\n"
        "    job_scope = WindowsJobScope()\n"
        "    job_scope.start()\n"
        "    backend.set_process_supervision(job_scope.managed)\n"
        "    try:\n"
        "        backend.open(Path(source_model), visible=visible)\n",
    )
    replace_once(
        path,
        '        connection.send(\n            {\n                "protocol": 1,\n'
        '                "kind": "ready",\n                "worker_id": worker_id,\n'
        '                "generation": generation,\n                "runtime": backend.runtime_identity(),\n'
        "            }\n        )\n",
        '        runtime = backend.runtime_identity()\n'
        '        runtime["process_supervision"] = job_scope.identity()\n'
        '        connection.send(\n            {\n                "protocol": 1,\n'
        '                "kind": "ready",\n                "worker_id": worker_id,\n'
        '                "generation": generation,\n                "runtime": runtime,\n'
        "            }\n        )\n",
    )
    replace_once(
        path,
        "        except Exception:\n            pass\n\n\ndef start_worker(\n",
        "        except Exception:\n"
        "            pass\n"
        "        finally:\n"
        "            job_scope.close()\n\n\n"
        "def start_worker(\n",
    )


def patch_aspen(root: Path) -> None:
    path = root / "src/aspenops_nexus/backends/aspen_plus.py"
    replace_once(
        path,
        "from ..registry import ResolvedNode\n",
        "from ..registry import ResolvedNode\n"
        "from ..windows_job import (\n"
        "    ProcessFingerprint,\n"
        "    fingerprint_matches,\n"
        "    is_descendant,\n"
        "    process_fingerprint,\n"
        ")\n",
    )
    old_function = '''def _aspen_pids() -> set[int]:
    result: set[int] = set()
    for process in psutil.process_iter(["pid", "name"]):
        try:
            name = str(process.info.get("name") or "").lower()
            if name in {"aspenplus.exe", "apwn.exe"} or "aspenplus" in name:
                result.add(int(process.info["pid"]))
        except (psutil.Error, KeyError, TypeError, ValueError):
            continue
    return result
'''
    new_function = '''def _aspen_processes() -> dict[int, ProcessFingerprint]:
    result: dict[int, ProcessFingerprint] = {}
    for process in psutil.process_iter(["pid", "name"]):
        try:
            name = str(process.info.get("name") or "").lower()
            if name not in {"aspenplus.exe", "apwn.exe"} and "aspenplus" not in name:
                continue
            pid = int(process.info["pid"])
            fingerprint = process_fingerprint(pid)
            if fingerprint is not None:
                result[pid] = fingerprint
        except (psutil.Error, KeyError, TypeError, ValueError):
            continue
    return result
'''
    replace_once(path, old_function, new_function)
    replace_once(
        path,
        "        self.owned_pids: set[int] = set()\n"
        "        self.open_errors: list[str] = []\n",
        "        self.owned_processes: dict[int, ProcessFingerprint] = {}\n"
        "        self.job_managed = False\n"
        "        self.worker_pid = os.getpid()\n"
        "        self.open_errors: list[str] = []\n",
    )
    replace_once(
        path,
        "    def open(self, model_path: Path, *, visible: bool = False) -> None:\n",
        "    def set_process_supervision(self, job_managed: bool) -> None:\n"
        "        self.job_managed = job_managed\n\n"
        "    def open(self, model_path: Path, *, visible: bool = False) -> None:\n",
    )
    replace_once(path, "        before = _aspen_pids()\n", "        before = _aspen_processes()\n")
    replace_once(
        path,
        "        time.sleep(float(os.getenv(\"ASPENOPS_COM_SETTLE_S\", \"0.25\")))\n"
        "        self.owned_pids = _aspen_pids() - before\n",
        "        time.sleep(float(os.getenv(\"ASPENOPS_COM_SETTLE_S\", \"0.25\")))\n"
        "        after = _aspen_processes()\n"
        "        self.owned_processes = {\n"
        "            pid: fingerprint\n"
        "            for pid, fingerprint in after.items()\n"
        "            if pid not in before and is_descendant(pid, self.worker_pid)\n"
        "        }\n",
    )
    old_cleanup = '''    def cleanup_owned_pids(self) -> None:
        # Only processes created after this worker opened its document are eligible for cleanup.
        for pid in sorted(self.owned_pids):
            try:
                process = psutil.Process(pid)
                process.terminate()
                process.wait(timeout=5)
            except psutil.TimeoutExpired:
                with suppress(psutil.Error):
                    process.kill()
            except psutil.Error:
                continue
'''
    new_cleanup = '''    def cleanup_owned_pids(self) -> None:
        if self.job_managed:
            return
        for fingerprint in sorted(
            self.owned_processes.values(), key=lambda item: item.pid
        ):
            if not fingerprint_matches(fingerprint):
                continue
            if not is_descendant(fingerprint.pid, self.worker_pid):
                continue
            try:
                process = psutil.Process(fingerprint.pid)
                process.terminate()
                process.wait(timeout=5)
            except psutil.TimeoutExpired:
                if fingerprint_matches(fingerprint):
                    with suppress(psutil.Error):
                        process.kill()
            except psutil.Error:
                continue
'''
    replace_once(path, old_cleanup, new_cleanup)
    replace_once(
        path,
        '            "owned_pids": sorted(self.owned_pids),\n',
        '            "owned_pids": sorted(self.owned_processes),\n'
        '            "job_managed": self.job_managed,\n',
    )


def add_backend_tests(root: Path) -> None:
    path = root / "tests/test_aspen_process_ownership.py"
    path.write_text(
        '''from __future__ import annotations

from pathlib import Path

import pytest

from aspenops_nexus.backends.aspen_plus import AspenPlusBackend
from aspenops_nexus.windows_job import ProcessFingerprint


class FakeProcess:
    def __init__(self, pid: int):
        self.pid = pid
        self.terminated = False
        self.killed = False

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: float) -> None:
        del timeout

    def kill(self) -> None:
        self.killed = True


def test_cleanup_skips_unverified_processes(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = AspenPlusBackend()
    backend.worker_pid = 100
    backend.owned_processes = {
        200: ProcessFingerprint(200, 1.0, 100, "C:/Aspen/apwn.exe"),
        300: ProcessFingerprint(300, 1.0, 999, "C:/Aspen/apwn.exe"),
    }
    processes = {200: FakeProcess(200), 300: FakeProcess(300)}
    monkeypatch.setattr(
        "aspenops_nexus.backends.aspen_plus.fingerprint_matches",
        lambda fingerprint: fingerprint.pid == 200,
    )
    monkeypatch.setattr(
        "aspenops_nexus.backends.aspen_plus.is_descendant",
        lambda pid, ancestor: pid == 200 and ancestor == 100,
    )
    monkeypatch.setattr(
        "aspenops_nexus.backends.aspen_plus.psutil.Process",
        lambda pid: processes[pid],
    )
    backend.cleanup_owned_pids()
    assert processes[200].terminated is True
    assert processes[300].terminated is False


def test_job_managed_backend_never_uses_pid_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = AspenPlusBackend()
    backend.set_process_supervision(True)
    backend.owned_processes = {
        200: ProcessFingerprint(200, 1.0, 100, "C:/Aspen/apwn.exe")
    }
    monkeypatch.setattr(
        "aspenops_nexus.backends.aspen_plus.psutil.Process",
        lambda pid: pytest.fail(f"manual cleanup attempted for {pid}"),
    )
    backend.cleanup_owned_pids()


def test_backend_runtime_retains_model_path_type() -> None:
    backend = AspenPlusBackend()
    backend.model_path = Path("case.bkp")
    assert backend.runtime_identity()["model_path"].endswith("case.bkp")
''',
        encoding="utf-8",
    )


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    patch_base(root)
    patch_worker(root)
    patch_aspen(root)
    add_backend_tests(root)
    (root / "scripts/apply_process_supervision.py").unlink(missing_ok=True)
    (root / ".github/workflows/apply-process-supervision.yml").unlink(
        missing_ok=True
    )


if __name__ == "__main__":
    main()
