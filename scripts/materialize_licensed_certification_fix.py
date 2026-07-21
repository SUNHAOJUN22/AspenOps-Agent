from __future__ import annotations

from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"Expected marker missing from {path}: {old[:100]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    module = Path("src/aspenops_nexus/licensed_certification.py")
    test = Path("tests/test_licensed_certification.py")

    replace_once(
        module,
        "from typing import Any, Mapping, TypeAlias, cast\n",
        "from collections.abc import Mapping\nfrom typing import Any, TypeAlias, cast\n",
    )
    replace_once(
        module,
        '        _reject_unknown(mapping, {"status", "reviewer", "approved_at", "scope"}, "engineering_acceptance")\n',
        '        _reject_unknown(\n            mapping,\n            {"status", "reviewer", "approved_at", "scope"},\n            "engineering_acceptance",\n        )\n',
    )
    replace_once(
        module,
        '            block("signing_key_inside_workspace", "Signing key must be outside the repository workspace")\n',
        '            block(\n                "signing_key_inside_workspace",\n                "Signing key must be outside the repository workspace",\n            )\n',
    )
    replace_once(
        module,
        '            block("dry_run_failed", f"Certification request dry-run failed: {type(exc).__name__}: {exc}")\n',
        '            block(\n                "dry_run_failed",\n                f"Certification request dry-run failed: {type(exc).__name__}: {exc}",\n            )\n',
    )
    replace_once(
        module,
        '        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:\n',
        '        with zipfile.ZipFile(\n            temporary,\n            "w",\n            compression=zipfile.ZIP_DEFLATED,\n            compresslevel=9,\n        ) as archive:\n',
    )
    replace_once(
        module,
        '            manifest_value = json.loads(read_member_bounded(archive, infos["manifest.json"], limits))\n',
        '            manifest_payload = read_member_bounded(\n                archive, infos["manifest.json"], limits\n            )\n            manifest_value = json.loads(manifest_payload)\n',
    )
    replace_once(
        module,
        '            if not isinstance(manifest_value, dict) or manifest_value.get("schema") != BUNDLE_SCHEMA:\n',
        '            if (\n                not isinstance(manifest_value, dict)\n                or manifest_value.get("schema") != BUNDLE_SCHEMA\n            ):\n',
    )
    replace_once(
        module,
        '        raise PermissionError("Licensed certification output must be inside state_dir or allowed roots")\n',
        '        raise PermissionError(\n            "Licensed certification output must be inside state_dir or allowed roots"\n        )\n',
    )
    replace_once(
        module,
        '''    observed_progids = {
        str(item.get("progid", "")).casefold()
        for item in candidates
        if isinstance(item, dict)
    }
''',
        '''    observed_progids = {
        str(item.get("progid", "")).casefold()
        for item in candidates
        if isinstance(item, dict)
        and str(item.get("registry_view", "")).casefold() != "fallback"
    }
''',
    )
    replace_once(test, "    BUNDLE_SCHEMA,\n", "")
    replace_once(
        test,
        '    with zipfile.ZipFile(bundle, "a", compression=zipfile.ZIP_DEFLATED) as archive:\n        with pytest.warns(UserWarning, match="Duplicate name"):\n            archive.writestr("report.json", b\'{"tampered":true}\')\n',
        '    with (\n        zipfile.ZipFile(bundle, "a", compression=zipfile.ZIP_DEFLATED) as archive,\n        pytest.warns(UserWarning, match="Duplicate name"),\n    ):\n        archive.writestr("report.json", b\'{"tampered":true}\')\n',
    )
    replace_once(
        test,
        '''    env = environment(tmp_path, private_path)
    monkeypatch.setattr(licensed, "compatibility_report", lambda: compatibility())
''',
        '''    env = environment(tmp_path, private_path)
    monkeypatch.setattr(licensed.platform, "system", lambda: "Windows")
    monkeypatch.setattr(licensed.platform, "machine", lambda: "X64")
    monkeypatch.setattr(licensed, "compatibility_report", lambda: compatibility())
''',
    )
    replace_once(
        test,
        '    assert REAL_CERTIFICATION_TEXT not in json.dumps(report)\n',
        '    assert report["certification_status"] != REAL_CERTIFICATION_TEXT\n',
    )
    replace_once(
        test,
        '''
@pytest.mark.parametrize(
    ("field", "value", "code"),
''',
        '''
def test_preflight_rejects_compatibility_fallback_as_registration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, configured, env, _ = valid_preflight(tmp_path, monkeypatch)
    monkeypatch.setattr(
        licensed, "compatibility_report", lambda: compatibility(fallback=True)
    )

    report = certification_preflight(plan, configured, environment=env)

    assert report["ready"] is False
    assert "approved_progid_missing" in {
        item["code"] for item in report["blockers"]
    }


@pytest.mark.parametrize(
    ("field", "value", "code"),
''',
    )


if __name__ == "__main__":
    main()
