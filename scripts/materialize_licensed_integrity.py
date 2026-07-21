from __future__ import annotations

from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"Expected integrity marker missing: {old[:140]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_between(path: Path, start: str, end: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    start_index = text.index(start)
    end_index = text.index(end, start_index)
    path.write_text(
        text[:start_index] + replacement + text[end_index:], encoding="utf-8"
    )


def main() -> None:
    path = Path("src/aspenops_nexus/licensed_certification.py")
    replace_once(path, "import re\n", "import re\nimport struct\n")
    replace_once(
        path,
        "from datetime import UTC, datetime\n",
        "from datetime import UTC, datetime, timedelta\n",
    )
    replace_once(
        path,
        "from .hashing import canonical_hash, sha256_file\n",
        '''from .hashing import canonical_hash, sha256_file
from .models import BalanceSpec, VariableRead
''',
    )
    replace_once(
        path,
        '''def _within(path: Path, roots: tuple[Path, ...]) -> bool:
    resolved = path.expanduser().resolve()
    return any(resolved == root or root in resolved.parents for root in roots)


''',
        '''def _within(path: Path, roots: tuple[Path, ...]) -> bool:
    resolved = path.expanduser().resolve()
    return any(resolved == root or root in resolved.parents for root in roots)


def _spec_identity(key: str, identifiers: dict[str, str]) -> str:
    suffix = ",".join(
        f"{name}={value}" for name, value in sorted(identifiers.items())
    )
    return key if not suffix else f"{key}:{suffix}"


def _planned_tolerance_keys(request: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for index, raw_read in enumerate(_array(request.get("reads", []), "request.reads")):
        read = VariableRead.from_dict(_object(raw_read, f"request.reads[{index}]"))
        keys.add(_spec_identity(read.key, read.identifiers))
    balance_details = {
        "residual",
        "absolute",
        "scale",
        "relative",
        "abs_tol",
        "rel_tol",
        "passed",
    }
    for index, raw_balance in enumerate(
        _array(request.get("balances", []), "request.balances")
    ):
        balance = BalanceSpec.from_dict(
            _object(raw_balance, f"request.balances[{index}]")
        )
        keys.update(
            f"balance:{balance.name}:{detail}" for detail in balance_details
        )
    return keys


''',
    )
    replace_once(
        path,
        '''        if max(repeatability.workers) > license_slots:
            raise ValueError(
                "repeatability.workers cannot exceed approved license_expectation.slots"
            )

        return cls(
''',
        '''        if max(repeatability.workers) > license_slots:
            raise ValueError(
                "repeatability.workers cannot exceed approved license_expectation.slots"
            )
        allowed_tolerances = _planned_tolerance_keys(request)
        unsupported_tolerances = sorted(
            set(repeatability.output_tolerances) - allowed_tolerances
        )
        if unsupported_tolerances:
            raise ValueError(
                "repeatability.output_tolerances contains keys outside the request: "
                + ", ".join(unsupported_tolerances)
            )

        return cls(
''',
    )
    replace_once(
        path,
        '''    compatibility: dict[str, Any] | None = None,
) -> dict[str, Any]:
''',
        '''    compatibility: dict[str, Any] | None = None,
    pointer_bits: int | None = None,
    current_time: datetime | None = None,
) -> dict[str, Any]:
''',
    )
    replace_once(
        path,
        '''    actual_system = system_name or platform.system()
    actual_arch = (machine_architecture or env.get("RUNNER_ARCH") or platform.machine()).upper()
    runner_name = env.get("RUNNER_NAME", "")
''',
        '''    actual_system = system_name or platform.system()
    actual_arch = (
        machine_architecture or env.get("RUNNER_ARCH") or platform.machine()
    ).upper()
    actual_pointer_bits = pointer_bits or struct.calcsize("P") * 8
    runner_name = env.get("RUNNER_NAME", "")
''',
    )
    replace_once(
        path,
        '''        "runner_environment": env.get("RUNNER_ENVIRONMENT"),
    }
''',
        '''        "runner_environment": env.get("RUNNER_ENVIRONMENT"),
        "python_pointer_bits": actual_pointer_bits,
    }
''',
    )
    replace_once(
        path,
        '''    if actual_arch != plan.runner_architecture:
        block(
            "runner_architecture_mismatch",
            "Runner architecture does not match the approved plan",
            expected=plan.runner_architecture,
            observed=actual_arch,
        )

    observed_commit = (
''',
        '''    if actual_arch != plan.runner_architecture:
        block(
            "runner_architecture_mismatch",
            "Runner architecture does not match the approved plan",
            expected=plan.runner_architecture,
            observed=actual_arch,
        )
    if actual_pointer_bits != 64:
        block(
            "python_64bit_required",
            "Licensed Aspen certification requires a 64-bit Python process",
            observed=actual_pointer_bits,
        )

    observed_commit = (
''',
    )
    replace_once(
        path,
        '''    if plan.engineering_acceptance.status != "approved":
        block(
            "engineering_acceptance_pending",
            "Engineering acceptance is not approved for this exact plan",
        )
    evidence["engineering_acceptance"] = asdict(plan.engineering_acceptance)

    if settings.license_slots != plan.license_slots:
''',
        '''    if plan.engineering_acceptance.status != "approved":
        block(
            "engineering_acceptance_pending",
            "Engineering acceptance is not approved for this exact plan",
        )
    approved_at = datetime.fromisoformat(plan.engineering_acceptance.approved_at)
    observed_time = current_time or datetime.now(UTC)
    if observed_time.tzinfo is None or observed_time.utcoffset() is None:
        raise ValueError("current_time must be timezone-aware")
    if approved_at > observed_time + timedelta(minutes=5):
        block(
            "engineering_approval_in_future",
            "Engineering approval timestamp is later than the certification run",
            approved_at=approved_at.isoformat(),
            observed_at=observed_time.isoformat(),
        )
    evidence["engineering_acceptance"] = asdict(plan.engineering_acceptance)

    if settings.license_slots != plan.license_slots:
''',
    )

    verifier = '''def _read_json_object_member(
    archive: zipfile.ZipFile,
    infos: dict[str, zipfile.ZipInfo],
    name: str,
    limits: ArchiveLimits,
) -> tuple[dict[str, Any], bytes]:
    payload = read_member_bounded(archive, infos[name], limits)
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError(f"{name} root must be an object")
    return {str(key): item for key, item in value.items()}, payload


def _licensed_bundle_semantic_checks(
    *,
    manifest: dict[str, Any],
    plan: LicensedCertificationPlan,
    preflight: dict[str, Any],
    report: dict[str, Any],
    environment: dict[str, Any],
) -> dict[str, bool]:
    evidence = preflight.get("evidence", {})
    return {
        "manifest_status_pending": manifest.get("certification_status")
        == PENDING_REAL_ASPEN_CERTIFICATION,
        "manifest_case_id": manifest.get("case_id") == plan.case_id,
        "manifest_commit": manifest.get("approved_commit") == plan.approved_commit,
        "manifest_plan_hash": manifest.get("plan_sha256")
        == canonical_hash(plan.to_dict()),
        "preflight_schema": preflight.get("schema") == PREFLIGHT_SCHEMA,
        "preflight_status_pending": preflight.get("certification_status")
        == PENDING_REAL_ASPEN_CERTIFICATION,
        "preflight_plan_hash": isinstance(evidence, dict)
        and evidence.get("plan_sha256") == canonical_hash(plan.to_dict()),
        "report_schema": report.get("schema") == REPORT_SCHEMA,
        "report_status_pending": report.get("certification_status")
        == PENDING_REAL_ASPEN_CERTIFICATION,
        "report_case_id": report.get("case_id") == plan.case_id,
        "report_commit": report.get("approved_commit") == plan.approved_commit,
        "report_backend": report.get("backend") == plan.backend,
        "environment_commit": str(environment.get("git_commit") or "").lower()
        == plan.approved_commit,
    }


def verify_licensed_certification_bundle(
    bundle_path: str | Path,
    *,
    trusted_public_key: KeySource,
    limits: ArchiveLimits = DEFAULT_ARCHIVE_LIMITS,
) -> dict[str, Any]:
    bundle = Path(bundle_path).expanduser().resolve()
    try:
        with zipfile.ZipFile(bundle, "r") as archive:
            infos = validate_archive(bundle, archive, limits)
            expected = _ALLOWED_MEMBERS | _RESERVED_MEMBERS
            actual = set(infos)
            if actual != expected:
                return {
                    "ok": False,
                    "verification_status": "structure-invalid",
                    "missing": sorted(expected - actual),
                    "unexpected": sorted(actual - expected),
                }
            manifest, _ = _read_json_object_member(
                archive, infos, "manifest.json", limits
            )
            _reject_unknown(
                manifest,
                {
                    "schema",
                    "created_at",
                    "runtime_schema",
                    "runtime_version",
                    "certification_status",
                    "case_id",
                    "approved_commit",
                    "plan_sha256",
                    "members",
                    "signing",
                    "boundary",
                },
                "licensed certification manifest",
            )
            if manifest.get("schema") != BUNDLE_SCHEMA:
                return {"ok": False, "verification_status": "structure-invalid"}
            _timezone_aware(manifest.get("created_at"), "manifest.created_at")
            declarations = _object(manifest.get("members"), "manifest.members")
            if set(declarations) != _ALLOWED_MEMBERS:
                return {
                    "ok": False,
                    "verification_status": "structure-invalid",
                    "manifest_member_missing": sorted(
                        _ALLOWED_MEMBERS - set(declarations)
                    ),
                    "manifest_member_unexpected": sorted(
                        set(declarations) - _ALLOWED_MEMBERS
                    ),
                }
            signing = _object(manifest.get("signing"), "manifest.signing")
            _reject_unknown(
                signing,
                {"status", "algorithm", "key_id"},
                "manifest.signing",
            )
            key_id = _text(signing.get("key_id"), "manifest.signing.key_id")
            if _KEY_ID_RE.fullmatch(key_id) is None:
                return {"ok": False, "verification_status": "structure-invalid"}
            if (
                signing.get("status") != "signed"
                or signing.get("algorithm") != "Ed25519"
            ):
                return {"ok": False, "verification_status": "structure-invalid"}
            key_id_payload = read_member_bounded(
                archive, infos["signing-key-id.txt"], limits
            )
            try:
                key_id_file = key_id_payload.decode("ascii").strip()
            except UnicodeDecodeError:
                return {"ok": False, "verification_status": "structure-invalid"}
            if key_id_file != key_id:
                return {"ok": False, "verification_status": "structure-invalid"}

            member_payloads: dict[str, bytes] = {}
            member_checks: dict[str, bool] = {}
            for name in sorted(_ALLOWED_MEMBERS):
                declaration = _object(
                    declarations.get(name), f"manifest.members.{name}"
                )
                _reject_unknown(
                    declaration,
                    {"sha256", "size"},
                    f"manifest.members.{name}",
                )
                digest = _digest(
                    declaration.get("sha256"), f"manifest.members.{name}.sha256"
                )
                size = declaration.get("size")
                if isinstance(size, bool) or not isinstance(size, int) or size < 0:
                    raise ValueError(
                        f"manifest.members.{name}.size must be a non-negative integer"
                    )
                payload = read_member_bounded(archive, infos[name], limits)
                member_payloads[name] = payload
                member_checks[name] = (
                    digest == _sha256_bytes(payload) and size == len(payload)
                )

            public_key = _load_public_key(trusted_public_key)
            if _key_id(public_key) != key_id:
                return {"ok": False, "verification_status": "signed-invalid"}
            encoded_signature = read_member_bounded(
                archive, infos["manifest.sig"], limits
            )
            try:
                signature = base64.b64decode(encoded_signature, validate=True)
                public_key.verify(signature, _canonical_bytes(manifest))
            except Exception:
                return {
                    "ok": False,
                    "verification_status": "signed-invalid",
                    "member_checks": member_checks,
                }

            plan_value = json.loads(member_payloads["plan.json"])
            plan = LicensedCertificationPlan.from_document(plan_value)
            preflight_value = json.loads(member_payloads["preflight.json"])
            report_value = json.loads(member_payloads["report.json"])
            environment_value = json.loads(member_payloads["environment.json"])
            if not isinstance(preflight_value, dict):
                raise ValueError("preflight.json root must be an object")
            if not isinstance(report_value, dict):
                raise ValueError("report.json root must be an object")
            if not isinstance(environment_value, dict):
                raise ValueError("environment.json root must be an object")
            semantic_checks = _licensed_bundle_semantic_checks(
                manifest=manifest,
                plan=plan,
                preflight=preflight_value,
                report=report_value,
                environment=environment_value,
            )
            content_valid = all(member_checks.values()) and all(
                semantic_checks.values()
            )
            return {
                "ok": content_valid,
                "verification_status": (
                    "signed-valid" if content_valid else "content-invalid"
                ),
                "member_checks": member_checks,
                "semantic_checks": semantic_checks,
                "manifest": manifest,
            }
    except (
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
        zipfile.BadZipFile,
        ArchiveSafetyError,
    ) as exc:
        return {
            "ok": False,
            "verification_status": "structure-invalid",
            "error": f"{type(exc).__name__}: {exc}",
        }


'''
    replace_between(
        path,
        "def verify_licensed_certification_bundle(\n",
        "def _runtime_scope_evidence(\n",
        verifier,
    )


if __name__ == "__main__":
    main()
