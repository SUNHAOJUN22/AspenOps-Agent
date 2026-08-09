#!/usr/bin/env bash
set -euo pipefail

kind="${1:?repository kind is required}"
case "$kind" in
  aspenops)
    uv lock --check
    uv sync --frozen --extra dev --extra agent --extra signing
    ;;
  scicomputation)
    python -m pip install --disable-pip-version-check -e '.[validation,quality,security]'
    python -m pip check
    ;;
  processing)
    python scripts/verify_dependency_lock.py requirements.lock --pyproject pyproject.toml
    python -m pip install --quiet --require-hashes -r requirements.lock
    python -m pip install --quiet --no-deps --no-build-isolation -e .
    python -m pip check
    ;;
  resindb)
    cp package.json /tmp/resindb-package-exact.json
    cp package-lock.json /tmp/resindb-package-lock-exact.json
    restore_manifests() {
      cp /tmp/resindb-package-exact.json package.json
      cp /tmp/resindb-package-lock-exact.json package-lock.json
    }
    trap restore_manifests EXIT
    node scripts/prepare-ci-manifest.mjs
    installed=0
    for registry in https://registry.npmjs.org https://registry.npmmirror.com; do
      for attempt in 1 2 3; do
        if npm ci --registry="$registry"; then
          installed=1
          break 2
        fi
        sleep $((attempt * 10))
      done
    done
    test "$installed" -eq 1
    restore_manifests
    trap - EXIT
    ;;
  dft)
    python -m pip install --disable-pip-version-check --upgrade pip
    python -m pip install -c constraints/py312.txt -r requirements-dev.txt
    python -m pip check
    ;;
  researcher)
    python -m pip install --disable-pip-version-check -r requirements-ci.lock
    python -m pip install --disable-pip-version-check -e . --no-deps
    python -m pip check
    ;;
  *)
    echo "unknown repository kind: $kind" >&2
    exit 2
    ;;
esac
