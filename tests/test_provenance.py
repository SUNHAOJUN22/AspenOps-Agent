import json
import zipfile
from pathlib import Path

from aspenops_nexus.provenance import verify_run_bundle, write_run_bundle

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src/aspenops_nexus/data/mock-case.json"
REGISTRY = ROOT / "src/aspenops_nexus/data/node-registry.json"


def test_bundle_roundtrip_and_tamper_detection(tmp_path: Path) -> None:
    request = {
        "model_path": str(MODEL),
        "registry_path": str(REGISTRY),
        "backend": "mock",
    }
    path = write_run_bundle(
        request=request,
        results=[{"ok": True, "values": {"x": 1.0}}],
        output_path=tmp_path / "run.zip",
    )
    assert verify_run_bundle(path)["ok"]

    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(tampered, "w") as target:
        for name in source.namelist():
            payload = source.read(name)
            if name == "results.json":
                payload = json.dumps([{"ok": True, "values": {"x": 2.0}}]).encode()
            target.writestr(name, payload)
    result = verify_run_bundle(tampered)
    assert result["ok"] is False
    assert result["checks"]["results_sha256"] is False
