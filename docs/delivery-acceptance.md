# AspenOps Delivery Acceptance / 交付验收

This document defines the software-delivery boundary for AspenOps 2.0. It is bilingual by structure: each section states the operational rule in English and Chinese.

本文件定义 AspenOps 2.0 的**软件交付边界**。它不把公共 CI、Mock、离线编译、哈希或签名误写成真实商业 Aspen 工程认证。

## 1. Deliverable / 交付物

The software handover contains:

- Python package `aspenops-nexus 2.0.0`;
- CLI, Python, and MCP control-plane surfaces;
- ProcessRequirement and ProcessDesignIR contracts;
- engineering-rule, unit, recycle/tear, and capability checks;
- process-isolated Worker/CasePool runtime;
- scheduler, cache, optimization, evidence, signature, and revocation controls;
- Mock backend for portable software qualification;
- Aspen Plus/HYSYS control-plane adapters for approved existing models on licensed Windows;
- bilingual `README.md` / `README.en.md`;
- twenty-three governed README SVGs and four AI-assisted acceptance diagrams;
- machine delivery verifier `scripts/verify_delivery.py`;
- deterministic handover builder `scripts/build_delivery_bundle.py`;
- delivery qualification writer `scripts/write_delivery_qualification.py`;
- SPDX SBOM, manifest, SHA-256 list, and deterministic handover archive.

The repository does **not** claim a production-grade arbitrary native flowsheet builder or licensed Aspen engineering certification.

本仓库交付控制面、数据合同、隔离运行、调度、缓存、优化、证据链和确定性交付，不承诺“任意自然语言自动生成正确流程图”，也不把软件测试当作真实 Aspen 工程资格。

## 2. Two acceptance levels / 两级验收

### Level A — delivery-surface completeness / 交付面完整

```bash
python scripts/verify_delivery.py \
  --output var/ci/delivery-acceptance.json
```

This verifies the repository structure, bilingual README contracts, visual inventory, delivery builder, qualification writer, documentation, permanent workflow inventory, historical qualification baseline, and the external Aspen boundary.

该模式验证仓库交付面完整，但允许“当前树完整资格证据”尚未生成。

### Level B — exact-tree qualification / 当前树严格资格

```bash
python scripts/verify_delivery.py \
  --require-current-qualification \
  --output var/ci/delivery-acceptance-current.json
```

This additionally requires:

```text
docs/DELIVERY_QUALIFICATION.json
```

with schema:

```text
aspenops.delivery-qualification/v2
```

and a PASS result for the qualified tree.

该模式用于真正的当前树验收，要求存在绑定当前资格树的机器证据。

## 3. Recommended software gates / 推荐软件门禁

```bash
uv lock --check
uv sync --frozen --extra dev --extra agent --extra signing

uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run python -m compileall -q src scripts tests

uv run python scripts/audit_source_tree.py \
  --output var/ci/source-tree-audit.json

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
```

A software qualification is acceptable only when every required command succeeds.

只有全部要求的命令通过，软件资格才成立。

## 4. Qualification writer / 资格证据写入器

`scripts/write_delivery_qualification.py` converts existing machine evidence into `docs/DELIVERY_QUALIFICATION.json`.

It is deliberately fail closed. A PASS record requires:

- delivery report schema `aspenops.delivery-acceptance/v1`;
- delivery report `status=PASS`;
- delivery report `issues=[]`;
- external Aspen status still `PENDING_REAL_ASPEN_CERTIFICATION`;
- branch coverage finite and at least 95%;
- JUnit failures = 0;
- JUnit errors = 0;
- JUnit skipped = 0;
- at least 1200 passed tests;
- 40-character lowercase hexadecimal source/tree Git identities;
- a positive integer run ID.

资格写入器禁止用小规模定向测试、skipped 测试、伪造 SHA 或伪造真实 Aspen 状态生成最终 PASS。

Example:

```bash
uv run python scripts/write_delivery_qualification.py \
  --coverage var/ci/coverage.json \
  --junit var/ci/junit.xml \
  --delivery-report var/ci/delivery-acceptance.json \
  --output docs/DELIVERY_QUALIFICATION.json \
  --source-sha "$GITHUB_SHA" \
  --qualified-tree-sha "$QUALIFIED_TREE_SHA" \
  --run-id "$GITHUB_RUN_ID"
```

## 5. Deterministic handover / 确定性交付

Build the distributions first:

```bash
uv build
```

Then build the final handover:

```bash
rm -rf var/delivery

uv run python scripts/build_delivery_bundle.py \
  --source-sha "$(git rev-parse HEAD)" \
  --source-date-epoch 0 \
  --include-dist \
  --output-dir var/delivery
```

Produced artifacts include:

```text
aspenops-source-<sha12>.zip
aspenops-sbom-<sha12>.spdx.json
aspenops-evidence-index-<sha12>.json
aspenops-delivery-manifest-<sha12>.json
SHA256SUMS
aspenops-handover-<sha12>.zip
aspenops-handover-<sha12>.zip.sha256
wheel
source distribution
```

Verify byte integrity:

```bash
cd var/delivery
sha256sum -c SHA256SUMS
sha256sum -c aspenops-handover-*.zip.sha256
```

The SBOM is SPDX 2.3. JSON generation is strict and uses `allow_nan=False`.

交付包包含源码、SBOM、资格证据索引、manifest、SHA-256 清单和最终 handover ZIP。

## 6. Acceptance invariants / 验收不变量

1. The repository has exactly four permanent authoritative workflows.
2. Permanent workflows are read-only with respect to repository contents.
3. No one-time/finalizer/running/temporary workflow residue is allowed.
4. Both README files reference the complete governed visual inventory.
5. Qualification evidence uses strict JSON with no duplicate keys or non-standard constants.
6. Baseline branch coverage is at least 95%.
7. Reverse and fixed-seed order gates pass.
8. `PENDING_REAL_ASPEN_CERTIFICATION` remains explicit.
9. No README may claim `REAL_ASPEN_CERTIFIED`.
10. Warm-start is single-Worker and path-dependent; optimization is reinitialized.
11. Native failure isolation is private-case discard or transactional rollback.
12. Deterministic handover binds source identity, SBOM, evidence, manifest, SHA-256, and distributions.
13. Current-tree PASS cannot be written from a tiny or skipped test suite.

## 7. External qualification HOLD / 外部资格暂停

Real Aspen Plus/HYSYS qualification remains blocked until the operator supplies:

- exact product, version, bitness, and ProgID;
- licensed feature names and permitted seats;
- fixed approved model, registry, input document, and output list;
- Windows, Python, CPU, memory, and runner fingerprint;
- Golden Case reference values;
- absolute and relative tolerances;
- repeat count and pass/fail rule;
- topology, layout, save/reopen, and readback evidence;
- process, property, equipment, and safety approval.

Without these items, the software can pass its own qualification but the real-environment status must remain:

```text
PENDING_REAL_ASPEN_CERTIFICATION
```

缺少这些证据时，禁止宣称真实 Aspen 工程认证完成。

## 8. Handover record / 最终移交记录

Archive at least:

```text
exact source commit SHA
qualified content/tree SHA
GitHub Actions run IDs, when available
uv.lock
wheel and source distribution
SPDX SBOM
delivery manifest
SHA256SUMS
handover ZIP + external SHA-256
delivery-acceptance.json
DELIVERY_QUALIFICATION.json, when exact-tree qualification exists
coverage JSON
JUnit XML
source-tree-audit.json
Bandit JSON
test-order-gate evidence
ACCEPTANCE_HARDENING_QUALIFICATION.json
licensed external evidence, when available
```

The archive should be immutable, access-controlled, and associated with the exact acceptance decision.

最终移交包应与明确的源码身份和验收决策绑定，不允许用“最新 main”替代不可变 SHA。
