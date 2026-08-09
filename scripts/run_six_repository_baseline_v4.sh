#!/usr/bin/env bash
set -euo pipefail

kind="${1:?repository kind is required}"
unicode_output="${2:?Unicode report output is required}"
controller_root="${3:?controller root is required}"

python "$controller_root/scripts/validate_repository_unicode_v4.py" \
  --root . --output "$unicode_output"

case "$kind" in
  aspenops)
    uv run python scripts/refresh_current_main_readme.py --check
    uv run ruff check .
    uv run ruff format --check .
    uv run mypy src
    uv run pytest -W error::ResourceWarning -q
    uv run python scripts/verify_delivery.py --root . \
      --output "${RUNNER_TEMP:-/tmp}/aspenops-delivery-v4.json"
    ;;
  scicomputation)
    node scripts/refresh-current-main-readme.mjs --check
    python scripts/verify_all.py --profile quality
    python scripts/verify_all.py --profile core
    python scripts/verify_all.py --profile benchmark
    python scripts/verify_all.py --profile package
    ;;
  processing)
    node scripts/refresh-current-main-readme.mjs --check
    python scripts/run_ci.py
    python -m tsao.cli doctor --root . --profile core
    ;;
  resindb)
    node scripts/refresh-current-main-readme.mjs --check
    npm run validate:ci
    npm run test:ui
    ;;
  dft)
    node scripts/refresh-current-main-readme.mjs --check
    python scripts/quality_gate.py
    python scripts/build_release_acceptance.py --help >/dev/null
    python scripts/capture_compute_contract_evidence.py --help >/dev/null
    ;;
  researcher)
    node scripts/refresh-current-main-readme.mjs --check
    if test -f scripts/validate_unicode_integrity.py; then
      python scripts/validate_unicode_integrity.py --check
    fi
    python scripts/sync_version.py --check
    python scripts/sync_runtime_data.py --check
    python scripts/validate_schemas.py
    python scripts/validate_mathematical_contracts.py --check
    python scripts/audit_repository.py
    python scripts/validate_structure.py
    python scripts/build_readme_facts.py --check
    python scripts/build_sbom.py --check
    python scripts/build_validation_evidence.py --check
    python scripts/build_test_dashboard.py --check
    python scripts/build_research_dashboard.py --check
    python scripts/generate_checksums.py --check
    python scripts/build_capability_index.py --check
    python scripts/final_acceptance_preflight.py --root . --json
    python -m pytest -q -p hypothesis.extra.pytestplugin
    ;;
  *)
    echo "unknown repository kind: $kind" >&2
    exit 2
    ;;
esac

git diff --exit-code
git diff --check
