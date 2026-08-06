# AspenOps 2.0 Quality Report

## Scope

This report records automated-test, workflow-trust, runtime-policy, dependency-audit, security-analysis, source-tree-audit, test-order-isolation, Windows-bootstrap, performance-evidence, licensed-evidence and documentation hardening applied directly to `main`. It does not certify Aspen physics or approve an engineering model.

Historical detail is retained in [`automated-test-audit-2026-07-22.md`](automated-test-audit-2026-07-22.md).

## Verified archived baseline

Portable Actions run `29814739487`, at SHA `670e9523e915af309f16d959150cfadcd84219a6`, passed Python 3.11, 3.12 and 3.13 plus quality/build/smoke. Python 3.12 recorded 563 passed with combined branch-aware coverage 94.9719800747198% against the then-current 94.5% floor.

Public Windows run `29814739334` recorded 104 passed in 2.06 seconds. These are archived validated baselines, not fresh current-head results.

## Public gates

`ci.yml` uses `ubuntu-24.04`, immutable Actions and `uv 0.11.16`. It enforces frozen dependencies, six Linux/Windows/Python audits, Ruff/format/mypy, full-source bytecode compilation, deterministic AST source-tree analysis, exact isolated Bandit `1.9.4` analysis over `src` and `scripts`, documentation contracts, source/Wheel build, Mock/README/MCP smoke and the full Python matrix.

Python 3.12 is the evidence-backed reference coverage gate at 95.0%. Python 3.11 and 3.13 retain 94.5% compatibility floors until fresh per-version coverage evidence supports raising them. Python 3.12 additionally collects every pytest node ID and reruns the complete suite twice: once in reverse order and once in deterministic random order with seed `20260728`. Collection failure, duplicate node IDs, an empty collection or either failing rerun closes the gate.

The source-tree audit parses every Python file under `src` and `scripts`, fails on syntax errors, dynamic `eval`/`exec`, unsafe pickle or marshal loading, `os.system`, unsafe `tempfile.mktemp`, unsafe YAML loading and subprocess calls that enable a shell. Broad boundary exception handlers remain machine-readable advisory findings rather than being silently ignored.

The Bandit step reports only high-severity, high-confidence findings, writes machine-readable JSON, validates that JSON and fails with the original Bandit exit code. It is exact-version isolated and never uses `--exit-zero`.

Frozen dependency metadata is also closed: `pyproject.toml` and `uv.lock` both record `mcp>=1.9,<2`. [`lock-sync-evidence.json`](lock-sync-evidence.json) records a real `uv 0.11.16` `uv lock --check` pass and binds normalized SHA-256 digests for both files; a regression test fails if either digest or requirement drifts.

`windows-control-plane.yml` uses `windows-2025`, Python 3.12 and `uv 0.11.16`. It validates PowerShell AST/helper behavior, dotenv safety, full Python source compilation, the same source-tree audit, Job Objects, IPC/recovery, Fake Aspen Plus/HYSYS, archives, paths, Wheel metadata edges, documentation, CLI and Doctor.

## Workflow governance

Automated tests lock:

- exactly four authoritative workflows;
- pinned runners, Actions and uv;
- read-only permissions and frozen dependency installation;
- complete dependency-audit evidence;
- full Python source compilation and deterministic source-tree AST auditing;
- exact Bandit version, scope, severity/confidence thresholds, JSON evidence and fail-closed behavior;
- a 95.0% Python 3.12 reference coverage floor and 94.5% Python 3.11/3.13 compatibility floors;
- complete reverse and seeded-random suite reruns on Python 3.12;
- explicit failed guards for non-main manual dispatches;
- performance evidence isolated in runner temporary storage;
- `expected_head_sha == GITHUB_SHA` for real certification;
- initial checkout, workflow definition, runtime code, tests and path validator on one commit;
- one serialized licensed concurrency group;
- checkout-before artifact contamination prevention;
- run-attempt-scoped runner-temp and external evidence directories;
- Mock JUnit, licensed evidence and `job_status` written only to runner temp;
- run-attempt-qualified artifact names and `if-no-files-found: error`.

## README visual governance

Both READMEs reference twenty-three original, self-contained SVG capability diagrams in `docs/assets/readme/`. The automated test-matrix visual exposes the Bandit `1.9.4` gate, full-source compilation, deterministic AST auditing, reverse and seeded-random full-suite reruns, the evidence-backed Python 3.12 95.0% floor, the 3.11/3.13 compatibility floors and the rule that missing current evidence is not a pass.

The visual suite remains bound to implemented source markers and is checked for exact inventory, local paths, XML validity, a fixed `1440 × 720` view box, titles/descriptions, safe elements and attributes, portable fonts, size limits and absence of scripts, event handlers, remote resources and data URIs.

## Distribution boundary testing

The built Wheel must contain exactly one bounded `METADATA` member and exactly one MCP requirement scoped to the `agent` extra. Regression tests cover missing or duplicate Wheels, missing or duplicate metadata, oversized metadata, incorrect package names, missing version bounds, incorrect extra markers and CLI report persistence. The isolated Wheel smoke continues to use hashed locked runtime dependencies, offline project installation and `pip check`.

## Performance evidence

The default baseline is `ebef32ee1f2be74df5d5c5489e7ca86d35ac7bb2`. A non-main ref exits with status 2. Candidate and baseline are validated main-history SHAs, each using its own lockfile, environment and script.

All current-run evidence is written to `$RUNNER_TEMP/aspenops-performance-evidence`; upload uses `${{ runner.temp }}/aspenops-performance-evidence`. Tracked `var/benchmarks` files cannot enter the artifact.

## Licensed evidence chain

A fixed Ubuntu `dispatch-guard` job exits with status 2 for non-main refs. The self-hosted job has `needs: dispatch-guard`.

`expected_head_sha` must equal the `GITHUB_SHA` of this `refs/heads/main` dispatch. The workflow verifies the initial `actions/checkout` HEAD, trusted-main ancestry and detached checkout all match that same SHA. It cannot use the current safety workflow to execute an arbitrary older main ancestor.

Before checkout, the self-hosted job removes and creates:

```text
$RUNNER_TEMP/aspenops-licensed-artifact-<GITHUB_RUN_ID>-<GITHUB_RUN_ATTEMPT>
```

`run-metadata.txt` is written before checkout. Mock JUnit, successful evidence copies and the final `job_status` remain in this directory. Upload reads only `${{ runner.temp }}/aspenops-licensed-artifact-${{ github.run_id }}-${{ github.run_attempt }}` and uses `if-no-files-found: error`; stale workspace `var/ci` cannot enter the artifact even when checkout fails.

All real certification jobs share the fixed concurrency group `licensed-aspen-certification`, which serializes Aspen Plus and HYSYS runs.

```text
ASPENOPS_STATE_DIR/licensed-certification/<GITHUB_RUN_ID>-<GITHUB_RUN_ATTEMPT>
```

The external directory is removed and recreated, exported as `LICENSED_EVIDENCE_DIR`, and used for preflight, real execution, bundle verification, report inspection and runner-temp staging. Artifact names include `github.run_id` and `github.run_attempt`.

These controls prevent old-code rollback, checkout-failure contamination, backend collisions, rerun contamination, stale report/bundle reuse and persistent self-hosted workspace diagnostics. Software cannot self-grant `REAL_ASPEN_CERTIFIED`.

## Documentation contracts

Documentation tests verify version/title consistency, safe links, frozen instructions, six audits, explicit guard failure behavior, `GITHUB_SHA` binding, pre-checkout runner-temp artifacts, per-attempt licensed evidence, certification boundaries, and absence of ChatGPT-internal citation or sandbox-link markup.

The closure-gate tests additionally bind the exact Bandit command, source-tree audit and full-suite order script into `ci.yml`, preventing later documentation-only claims or silent removal of those gates.

## Evidence boundary

The committed Linux and Windows qualification JSON files record the last completed cross-platform full-suite result. New permanent gates are not called green merely because their source is committed: the exact current `main` SHA must complete the hosted Linux and Windows workflows and publish current artifacts. Real certification still requires licensed Windows, an approved model, verified semantics, signing material and human engineering review.
