from __future__ import annotations

from pathlib import Path


def test_wheel_smoke_uses_hashed_locked_runtime_dependencies() -> None:
    text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "uv export --frozen" in text
    assert "--no-default-groups" in text
    assert "--no-emit-project" in text
    assert "--format requirements.txt" in text
    assert "--output-file var/ci/runtime-requirements.txt" in text
    assert "uv pip sync" in text
    assert "--require-hashes" in text
    assert "uv pip install" in text
    assert "--offline" in text
    assert "--no-deps" in text
    assert "uv pip check --python /tmp/aspenops-wheel/bin/python" in text
    assert "/tmp/aspenops-wheel/bin/aspenops scheduler --help" in text
    assert "/tmp/aspenops-wheel/bin/aspenops cancel --help" in text
    assert "/tmp/aspenops-wheel/bin/aspenops optimize --help" in text
    assert "tests/test_cli_durable_queue.py" in text
    assert "uv run aspenops submit examples/batch-request.example.json" in text
    assert "uv run aspenops cancel \"$job_id\" --grace-s 0" in text
    assert "uv run aspenops optimize examples/optimization-request.example.json" in text
    assert "/tmp/aspenops-wheel/bin/pip install dist/*.whl" not in text
