# AspenOps Delivery Acceptance / 交付验收

This document defines the software-delivery boundary for AspenOps 2.0. It is bilingual by structure: each section states the operational rule in English and Chinese.

## 1. Deliverable / 交付物

- Python package `aspenops-nexus 2.0.0`.
- CLI, Python and MCP control-plane surfaces.
- ProcessRequirement and ProcessDesignIR contracts.
- Mock backend for portable software qualification.
- Aspen Plus/HYSYS control-plane adapters for approved existing models on licensed Windows.
- Scheduler, cache, optimization, evidence, signature and revocation controls.
- Bilingual README files, twenty-three governed SVGs and four AI-assisted acceptance diagrams.
- Machine delivery verifier: `scripts/verify_delivery.py`.
- Deterministic handover builder: `scripts/build_delivery_bundle.py`; see `docs/delivery-bundle.md`.

The repository does **not** deliver a production-grade arbitrary native flowsheet builder or licensed Aspen engineering certification.

本仓库交付软件控制面、数据合同、隔离运行、调度、缓存、优化和证据链；不交付“任意自然语言自动生成正确流程图”的承诺，也不把公共 CI 当作商业 Aspen 工程认证。

## 2. Software acceptance command / 软件验收命令

```bash
uv lock --check
uv sync --frozen --extra dev --extra agent --extra signing
python scripts/verify_delivery.py --output var/ci/delivery-acceptance.json
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run python -m compileall -q src scripts tests
uv run python scripts/audit_source_tree.py --output var/ci/source-tree-audit.json
uv tool run --isolated --from 'bandit==1.9.4' bandit \
  --recursive src scripts \
  --severity-level high \
  --confidence-level high
uv run pytest -W error::ResourceWarning \
  --cov=aspenops_nexus \
  --cov-branch \
  --cov-report=term-missing \
  --cov-report=json:var/ci/coverage.json \
  --junitxml=var/ci/junit.xml \
  --cov-fail-under=95
uv run python scripts/run_test_order_gate.py \
  --seed 20260728 \
  --output-dir var/ci
uv build
rm -rf var/delivery
uv run python scripts/build_delivery_bundle.py \
  --source-sha "$(git rev-parse HEAD)" \
  --source-date-epoch 0 \
  --include-dist \
  --output-dir var/delivery
sha256sum -c var/delivery/SHA256SUMS
sha256sum -c var/delivery/aspenops-handover-*.zip.sha256
```

A software delivery is acceptable only when every command succeeds and the delivery report has `status=PASS`.

只有全部命令通过且交付报告为 `PASS`，软件交付才成立。

## 3. Acceptance invariants / 验收不变量

1. The repository has exactly four authoritative workflows and no one-time/finalizer workflow residue.
2. Both README files reference the complete governed visual inventory.
3. Qualification evidence is strict JSON with no duplicate keys or non-standard constants.
4. Branch coverage is at least 95% on the Python 3.12 acceptance gate.
5. Reverse and fixed-seed order gates pass.
6. `PENDING_REAL_ASPEN_CERTIFICATION` remains explicit.
7. No README may claim `REAL_ASPEN_CERTIFIED`.
8. Package metadata, README version and licence remain consistent.
9. Warm-start is single-Worker and path-dependent; optimization is reinitialized.
10. Native failure isolation is implemented by private-case discard or transactional rollback.
11. Delivery ZIP members are sorted, timestamps and file modes are normalized, and every artifact is SHA-256 bound.
12. The SPDX SBOM is generated from the frozen `uv.lock` inventory.

## 4. External qualification HOLD / 外部资格暂停

Real Aspen Plus/HYSYS qualification remains blocked until the operator supplies:

- exact product, version, bitness and ProgID;
- licensed feature names and permitted seats;
- fixed approved model, registry, input document and output list;
- Windows, Python, CPU, memory and runner fingerprint;
- Golden Case reference values;
- absolute and relative tolerances;
- repeat count and pass/fail rule;
- topology, layout, save/reopen and readback evidence;
- process, property, equipment and safety approval.

Without these items, software tests may pass, but the result must remain `PENDING_REAL_ASPEN_CERTIFICATION`.

缺少上述证据时，允许软件资格通过，但禁止宣称真实 Aspen 工程资格完成。

## 5. Handover package / 移交包

The acceptance operator should archive:

```text
source commit SHA
GitHub Actions run IDs
uv.lock
wheel and source distribution hashes
delivery-acceptance.json
coverage JSON
JUnit XML
source-tree-audit.json
Bandit JSON
test-order-gate evidence
ACCEPTANCE_HARDENING_QUALIFICATION.json
aspenops-source-<sha12>.zip
aspenops-sbom-<sha12>.spdx.json
aspenops-evidence-index-<sha12>.json
aspenops-delivery-manifest-<sha12>.json
SHA256SUMS
aspenops-handover-<sha12>.zip
aspenops-handover-<sha12>.zip.sha256
licensed external evidence, when available
```

The archive should be immutable, access-controlled and associated with the exact acceptance decision.

移交包应保持不可变、受控访问，并与明确的验收决定和源码身份绑定。
