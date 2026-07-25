<div align="center">

# AspenOps 2.0

## Aspen Plus、Aspen HYSYS 与 AI Agent 之间的确定性执行控制平面

**Agent / CLI / Python → 统一流程意图 → 隔离执行 → 非线性求解 → 工程判定 → 可复现实验证据**

[English](README.en.md) · [Architecture](docs/architecture.md) · [Process Intent IR](docs/process-intent-ir.md) · [External Agent Integration](docs/external-agent-integration.md) · [Windows Setup](docs/windows-setup.md) · [Performance](docs/performance.md) · [Certification](docs/certification.md) · [Test Audit](docs/automated-test-audit-2026-07-22.md) · [Quality Report](docs/quality-report.md) · [Security](SECURITY.md) · [Contributing](CONTRIBUTING.md)

[![CI main push](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/ci.yml/badge.svg?branch=main&event=push)](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/ci.yml?query=branch%3Amain+event%3Apush)
[![Windows main push](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/windows-control-plane.yml/badge.svg?branch=main&event=push)](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/windows-control-plane.yml?query=branch%3Amain+event%3Apush)
![Python](https://img.shields.io/badge/Python-3.11--3.13-3776AB)
![Version](https://img.shields.io/badge/version-2.0.0-111827)
![License](https://img.shields.io/badge/license-Apache--2.0-0F766E)

</div>

![AspenOps 总体架构](docs/assets/readme/hero-architecture.svg)

> 上图及本 README 中的九张功能图均为本轮为 AspenOps 原创生成的 AI SVG 视觉资产；图示只表达代码中已有架构与明确标注的路线图，不把 planned 能力画成已实现功能。

---

## 当前权威状态

| 项目 | 状态 |
|---|---|
| 默认及唯一长期分支 | `main` |
| 软件包 | `aspenops-nexus 2.0.0` |
| 公共测试矩阵 | Python 3.11、3.12、3.13 |
| 已归档便携式基线 | Actions run `29814739487` |
| Python 3.12 归档结果 | 72 个测试模块，563 passed，0 failed，0 skipped，16.73 s |
| 综合分支感知覆盖率 | 94.9719800747198% |
| 语句 / 分支覆盖率 | 96.23677786818551% / 90.84880636604774% |
| 覆盖率门槛 | 94.5% |
| 已归档 Windows 公共门 | Actions run `29814739334`，104 passed，2.06 s |
| MCP 工具数 | 14 |
| 真实 Aspen 认证 | `PENDING_REAL_ASPEN_CERTIFICATION` |

以上是**已验证归档基线**，来自已检查的 JUnit、coverage JSON 和日志，**不是对任意后续提交的自动声明**。顶部徽章反映当前 `main` push 状态；历史数字不会替代最新 Actions 证据。

公共 CI 证明控制平面、路径策略、进程隔离、调度、归档、接口与 Process Intent 合同，不证明商业 Aspen、许可证、物性方法或工程模型已经完成认证。

---

## 产品定位

AspenOps 不是一个“让大模型随意写 COM 脚本”的包装器，而是面向 Aspen Plus、Aspen HYSYS 和化工仿真 Agent 的确定性执行基础设施：

- 以语义变量、统一流程 IR 和受限 MCP 工具替代任意 Tree Path、Shell、VBA 和裸 COM；
- 以进程隔离、STA 所有权、私有模型副本和许可槽限制控制 Windows 自动化；
- 以收敛、约束、物料/能量衡算和工程审批区分“软件执行完成”与“工艺结果有效”；
- 以冻结依赖、主干 SHA、运行尝试、哈希、签名与可视化制品形成证据闭环；
- 吸收 Text-to-Flowsheet、Sketch2Simulation、DWSIM、IDAES、Modelica 和流程 Agent 的适合思想，但不复制外部专有代码或提示词。

---

## 核心工业安全不变量

![Windows COM 进程隔离](docs/assets/readme/com-isolation.svg)

1. 一个 COM 对象只属于一个 Windows 子进程和一个 STA apartment。
2. Agent 只使用语义变量或 `aspenops.flowsheet/v1`，不构造任意 Aspen Tree Path。
3. 每个 Worker 使用私有模型副本，不覆盖主模型。
4. 硬超时只终止 AspenOps 创建并核验归属的进程。
5. 并发上限受有效许可证证据和 `ASPENOPS_LICENSE_SLOTS` 限制。
6. 通信、引擎返回、收敛、可行性和守恒闭合分别判定。
7. Mock、Fake COM 和公共 CI 不冒充真实 Aspen 物理认证。
8. DWSIM、IDAES、Modelica 和自动 flowsheet 编译器未实现时必须 fail closed。

结果仅在以下条件全部成立时为 `ok=true`：

```text
communication_ok
AND engine_ok
AND converged
AND feasible
AND balances_passed
```

---

## 统一流程意图 IR

![Process Intent IR](docs/assets/readme/process-intent-ir.svg)

统一中间表示：

```text
aspenops.flowsheet/v1
```

IR 描述组件、物性方法、设备、输入/输出端口、流股、参数和安全元数据，并提供：

- 确定性排序、canonical JSON 和 SHA-256 图身份；
- 重复 ID、未知引用、端口方向、自连接、悬空必需端口和隐式多连接检查；
- recycle cycle 警告或严格拒绝策略；
- JSON 深度、数量、元数据大小和标识符预算；
- 禁止 `code`、`script`、`shell`、`python`、`vba`、`command`、原始 Tree Path 等注入；
- 拓扑有效性、编译器可用性、执行、收敛、守恒、修复轮次和人工介入 benchmark 字段。

本地验证和图形化：

```bash
uv run python scripts/validate_process_ir.py \
  examples/process-intent.example.json \
  --canonical-output var/ci/process-intent-canonical.json \
  --report-output var/ci/process-intent-report.json

uv run python scripts/render_process_ir_dashboard.py \
  --input var/ci/process-intent-report.json \
  --output-html var/ci/process-ir-dashboard.html \
  --output-svg var/ci/process-ir-dashboard.svg
```

`process-ir-dashboard.html` 可切换验证问题、后端能力和 Agent pipeline；`process-ir-dashboard.svg` 用于报告和 artifact 预览。详细规则见 [Process Intent IR](docs/process-intent-ir.md)。

---

## 分层化工 Agent

![分层化工 Agent](docs/assets/readme/agent-pipeline.svg)

```text
Knowledge
→ Concept
→ Parameter
→ Execution
→ Repair
→ Physics / Engineering Review
```

- Knowledge 阶段只读取资料和约束；
- Concept 与 Parameter 阶段只能输出验证后的 `aspenops.flowsheet/v1`；
- Execution 阶段只能通过已声明 available 的后端和受限工具；
- Repair 阶段必须有轮次、时间和求解预算；
- Review 阶段独立检查物理、收敛、约束、守恒和人工批准；
- 任一阶段都不得输出任意 Python、Shell、VBA、裸 COM 或原始 Tree Path。

---

## 多模拟器能力声明

![多模拟器能力矩阵](docs/assets/readme/backend-capabilities.svg)

执行能力和 IR 自动建模编译能力是两个独立声明：

| 后端 | 当前执行 | IR 自动建模编译器 | 当前边界 |
|---|---|---|---|
| Mock | available | planned | 跨平台确定性软件测试，不代表 Aspen 物理 |
| Aspen Plus | available，持证 Windows | planned | 运行既有获批模型 |
| HYSYS | available，持证 Windows | planned | 运行既有获批模型 |
| DWSIM | planned | planned | **未实现，无 adapter** |
| IDAES | planned | planned | **未实现，无 adapter** |
| Modelica/FMI | planned | planned | **未实现，无 adapter** |

**planned ≠ implemented；compiler ≠ executor；签名 ≠ 工程批准。**

---

## CLI、调度、优化和 MCP

主要 CLI：

```text
demo
doctor
dry-run
run-batch
submit
job
benchmark
optimize
certify
certification-preflight
certify-licensed
verify-licensed-bundle
verify-bundle
mcp
```

MCP 精确暴露 14 个窄接口工具，用于发现、规划、提交、查询、优化和证据验证；不提供任意 Shell、Python、VBA、`eval`、无限制 COM 方法或原始 Tree Path 写入。

调度器使用 SQLite WAL、租约、心跳、取消期限和幂等提交；CasePool 按 backend、模型、registry、并发和可见性复用，缓存身份绑定运行时、模型、registry 与物理请求。

---

## 自动测试与视觉证据

![自动测试矩阵](docs/assets/readme/test-matrix.svg)

四个权威 workflow：

| 工作流 | 固定环境 | 作用 |
|---|---|---|
| `ci.yml` | `ubuntu-24.04`；Python 3.11/3.12/3.13 | Ruff、格式、strict mypy、六组合依赖审计、全量测试、分支覆盖率、构建、Wheel、Mock、MCP、Process IR 和 dashboard |
| `windows-control-plane.yml` | `windows-2025`；Python 3.12 | Windows Job、IPC、Fake Aspen/HYSYS、PowerShell、路径、IR 和治理合同 |
| `generate-performance-evidence.yml` | `ubuntu-24.04`；Python 3.12 | 受信 baseline/candidate、双冻结环境和稳定回归证据 |
| `licensed-aspen-certification.yml` | `ubuntu-24.04` guard → 持证 Windows | 主干守卫、SHA 绑定、Mock/IR 软件门、证据隔离和真实 COM |

冻结依赖审计覆盖：

```text
Linux 与 Windows × Python 3.11、3.12、3.13
```

也就是六组合审计。所有托管 runner、第三方 Actions 和 `uv 0.11.16` 固定版本；workflow 权限保持 `contents: read`。

artifact 规则：

```text
ci-evidence-quality-<run_id>-<run_attempt>
ci-evidence-python-<python>-<run_id>-<run_attempt>
windows-control-plane-diagnostics-<run_id>-<run_attempt>
performance-evidence-<run_id>-<run_attempt>
licensed-<backend>-<run_id>-<run_attempt>
```

每个名称同时包含 `github.run_id` 与 `github.run_attempt`；所有上传统一使用 `if-no-files-found: error`。当前 job 的临时证据写入 `$RUNNER_TEMP`，上传通过 `${{ runner.temp }}` 读取。没有 JUnit 或早期失败时 dashboard 显示 `INCOMPLETE`；任意 failure/error 显示 `FAIL`，不得出现假 PASS。

完整本地质量门：

```bash
uv lock --check
uv sync --frozen --extra dev --extra agent --extra signing
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -W error::ResourceWarning \
  --cov=aspenops_nexus \
  --cov-branch \
  --cov-fail-under=94.5
uv build
uv run python scripts/check_mcp.py
uv run python scripts/validate_process_ir.py examples/process-intent.example.json
uv run aspenops --version
uv run aspenops demo
uv run aspenops dry-run examples/batch-request.example.json
```

Windows 增加 `--extra windows`。`.env.example` 默认使用 Mock、空允许根目录和仓库内状态目录，首次运行保持跨平台。

---

## 可复现实验证据

![证据链](docs/assets/readme/evidence-chain.svg)

每个可接受结果应能追溯到：

```text
validated intent
→ exact trusted main SHA
→ isolated Worker execution
→ convergence / feasibility / balances
→ run_id + run_attempt artifact
→ hashes and optional signature
→ qualified human acceptance
```

性能任务首先验证 `GITHUB_REF == refs/heads/main`。非主干调度会写入 `dispatch-ref.txt` 和 `dispatch-guard.log`，然后以退出码 2 **显式失败**，而不是 all-skipped。`actions/checkout` 使用受信工作流版本，candidate 与 baseline 通过 `--end-of-options` 解析并进行 ancestor 检查，之后 detached checkout 已验证 SHA。

当前性能默认 baseline：

```text
ebef32ee1f2be74df5d5c5489e7ca86d35ac7bb2
```

Mock 性能只表示编排性能，不代表真实 Aspen 求解速度。

---

## 持证 Aspen 认证

![持证认证流程](docs/assets/readme/licensed-certification.svg)

持证 workflow 的关键合同：

1. 固定 `ubuntu-24.04` guard 验证 `refs/heads/main`，错误 ref 显式失败且不占用许可证主机。
2. `expected_head_sha` 必须等于本次调度的 `GITHUB_SHA`。
3. 初始 `actions/checkout` 必须匹配该 SHA，并确认其属于可信 `origin/main`，再 detached checkout。
4. 自托管 job 在 checkout 前创建：
   `$RUNNER_TEMP/aspenops-licensed-artifact-<GITHUB_RUN_ID>-<GITHUB_RUN_ATTEMPT>`。
5. `run-metadata.txt` 记录 run、ref、SHA 和 `expected_head_sha`。
6. Mock JUnit、测试 dashboard、Process IR dashboard、成功证据副本和最终 `job_status` 进入本次 runner-temp 目录。
7. 真实运行使用 `LICENSED_EVIDENCE_DIR`：
   `ASPENOPS_STATE_DIR/licensed-certification/<GITHUB_RUN_ID>-<GITHUB_RUN_ATTEMPT>`。
8. 固定 concurrency group `licensed-aspen-certification` **串行**执行。
9. `if: always()` 上传只读取本次目录，并使用 `if-no-files-found: error`。

软件只能生成：

```text
PENDING_REAL_ASPEN_CERTIFICATION
```

真实认证仍需持证 Windows、有效许可证、获批模型、签名材料和流程工程师验收。

---

## 路线图

![AspenOps 路线图](docs/assets/readme/roadmap.svg)

### 已实现

- Process Intent IR、严格验证、canonical JSON、SHA-256 图身份；
- Aspen Plus/HYSYS 既有模型控制面；
- Mock、Fake COM、Windows Job Object、调度、优化、MCP；
- 冻结 CI、可视化 dashboard、证据 bundle 和持证认证边界。

### 下一阶段

- IR → Mock 非执行计划编译器；
- DWSIM 开源真实流程后端；
- Text/Image → IR benchmark 与数据合同；
- 有预算的模拟反馈 Repair loop；
- 人工审查和差异可视化界面。

### 证据成熟后推进

- Aspen/HYSYS 自动 flowsheet 编译器；
- IDAES 符号后端；
- Modelica/FMI 联合仿真；
- PFD/草图理解；
- 工业模型和版本资格认证。

任何能力都不能在缺少**代码 + 测试 + 证据**时从 planned 改为 available。

---

## AI 生成视觉资产清单

本 README 使用以下原创 SVG，全部存放在 `docs/assets/readme/`，无外部图片依赖：

1. `hero-architecture.svg`
2. `process-intent-ir.svg`
3. `agent-pipeline.svg`
4. `backend-capabilities.svg`
5. `com-isolation.svg`
6. `test-matrix.svg`
7. `evidence-chain.svg`
8. `licensed-certification.svg`
9. `roadmap.svg`

图像只描述仓库中的现行合同与明确路线图，不包含虚构测试结果、未公开客户模型或商业模拟器资料。

---

## 文档与安全边界

`tests/test_documentation_contracts.py` 从 `pyproject.toml` 动态读取版本，核对 README、`__version__`、CHANGELOG、AGENTS、CLAUDE、CONTRIBUTING 和核心文档；本地链接不得逃出仓库，聊天内部引用或会话专用下载标记不得进入仓库 Markdown。

详细设计：

- [Architecture](docs/architecture.md)
- [Process Intent IR](docs/process-intent-ir.md)
- [External Agent Integration](docs/external-agent-integration.md)
- [Windows Setup](docs/windows-setup.md)
- [Performance](docs/performance.md)
- [Certification](docs/certification.md)
- [Test Audit](docs/automated-test-audit-2026-07-22.md)
- [Quality Report](docs/quality-report.md)

自动化不证明任意 Aspen 版本都能启动、任意模型都收敛、物性/反应/设备假设工程上正确，也不能替代流程工程师或自行授予真实认证。

代码采用 Apache-2.0。不得提交客户模型、专有物性/动力学、生产 DCS 数据、许可证、私钥、Token、内部主机或商业证据包。
