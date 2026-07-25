<div align="center">

# AspenOps 2.0

## Aspen Plus、Aspen HYSYS 与 AI Agent 之间的确定性执行控制平面

**Agent / CLI / Python → 统一流程意图 → 隔离执行 → 非线性求解 → 工程判定 → 可复现实验证据**

[English](README.en.md) · [Architecture](docs/architecture.md) · [Process Intent IR](docs/process-intent-ir.md) · [Windows Setup](docs/windows-setup.md) · [Certification](docs/certification.md) · [Quality Report](docs/quality-report.md) · [Security](SECURITY.md) · [Contributing](CONTRIBUTING.md)

[![CI main push](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/ci.yml/badge.svg?branch=main&event=push)](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/ci.yml?query=branch%3Amain+event%3Apush)
[![Windows main push](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/windows-control-plane.yml/badge.svg?branch=main&event=push)](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/windows-control-plane.yml?query=branch%3Amain+event%3Apush)
![Python](https://img.shields.io/badge/Python-3.11--3.13-3776AB)
![Version](https://img.shields.io/badge/version-2.0.0-111827)
![License](https://img.shields.io/badge/license-Apache--2.0-0F766E)

</div>

![AspenOps 总体架构](docs/assets/readme/hero-architecture.svg)

> 本 README 使用十二张为 AspenOps 原创生成的 AI SVG 功能图。图像仅表达仓库中已经实现的合同与明确标注的 planned 路线，不把软件测试、Mock 或签名材料包装成真实 Aspen 工程认证。

---

## 当前权威状态

| 项目 | 状态 |
|---|---|
| 默认及唯一长期分支 | `main` |
| 软件包 | `aspenops-nexus 2.0.0` |
| 公共测试矩阵 | Python 3.11、3.12、3.13 |
| 已验证归档基线 | Actions run `29814739487` |
| Python 3.12 归档结果 | 72 个测试模块，563 passed，0 failed，0 skipped，16.73 s |
| 综合分支感知覆盖率 | 94.9719800747198% |
| 覆盖率门槛 | 94.5% |
| 已归档 Windows 公共门 | Actions run `29814739334`，104 passed，2.06 s |
| MCP 工具数 | 14 |
| 真实 Aspen 认证 | `PENDING_REAL_ASPEN_CERTIFICATION` |

上述数字来自已检查的 JUnit、coverage JSON 和日志，**不是对任意后续提交的自动声明**。顶部徽章反映当前 `main` push 工作流状态；历史数字不能替代当前提交的新 Actions 证据。

公共 CI 可以证明控制平面、路径策略、进程隔离、调度、归档、接口、Process Intent 和文档合同，不证明商业 Aspen 安装、许可证、物性方法、反应模型或工程模型已经合格。

---

## 产品定位

AspenOps 不是“让大模型自由生成 COM 脚本”的包装器。它把 Aspen Plus、Aspen HYSYS、CLI、Python 和 AI Agent 接入同一套确定性控制面：

- Agent 只能提交语义变量或验证后的 `aspenops.flowsheet/v1`；
- 每个真实 Automation Server 位于独立 Windows 子进程和 STA apartment；
- 每个 Worker 使用私有模型副本，主模型不被覆盖；
- 调度并发受许可证槽、资源预算和生命周期策略共同限制；
- 通信、引擎返回、收敛、约束、物料/能量衡算和人工批准分别判定；
- 每次可接受结果都绑定请求、模型、注册表、代码提交和证据哈希；
- DWSIM、IDAES、Modelica/FMI 与自动 flowsheet 编译器保持 `planned`，未实现时无 adapter、必须 fail closed。

---

## 快速开始

要求：Python 3.11–3.13，`uv >= 0.11.16`。

```bash
git clone https://github.com/SUNHAOJUN22/AspenOps-Agent.git
cd AspenOps-Agent

uv lock --check
uv sync --frozen --extra dev --extra agent --extra signing

uv run aspenops --version
uv run aspenops demo
uv run aspenops dry-run examples/batch-request.example.json
```

Windows 真实后端安装时增加 `--extra windows`：

```powershell
uv sync --frozen --extra windows --extra dev --extra agent --extra signing
uv run aspenops doctor --probe
```

首次运行默认使用 Mock。Mock 用于跨平台软件验证，不代表 Aspen Plus/HYSYS 的物理结果。

---

## 配置边界

便携式默认配置来自 `.env.example`：

```dotenv
ASPENOPS_BACKEND=mock
ASPENOPS_MODE=default
ASPENOPS_ALLOWED_ROOTS=
ASPENOPS_STATE_DIR=var/aspenops-state
ASPENOPS_LICENSE_SLOTS=1
ASPENOPS_MAX_WORKERS=1
ASPENOPS_MAX_RESIDENT_CASES=2
```

真实 Aspen 示例必须使用绝对允许根目录，且状态目录必须位于允许根目录内：

```dotenv
ASPENOPS_BACKEND=aspen_plus
ASPENOPS_ALLOWED_ROOTS=C:/AspenModels;C:/AspenResults
ASPENOPS_STATE_DIR=C:/AspenResults/aspenops-state
```

关键规则：

1. Mock 可以使用空允许目录；真实 Aspen/HYSYS 不可以。
2. `..`、符号链接、Windows junction 和 realpath 逃逸会被拒绝。
3. `ASPENOPS_LICENSE_SLOTS` 与 `ASPENOPS_MAX_WORKERS` 共同限制并发。
4. `.env` 中重复变量、未闭合引号和潜在密钥回显会被拒绝。
5. 私钥、Token、许可证秘密、客户模型路径和生产数据不得进入仓库。

完整 Windows 设置见 [Windows Setup](docs/windows-setup.md)。

---

## 核心工业安全不变量

![Windows COM 进程隔离](docs/assets/readme/com-isolation.svg)

1. 一个 COM 对象只属于一个 Windows 子进程和一个 STA apartment。
2. Agent 不构造任意 Aspen Tree Path，不执行任意 Python、Shell 或 VBA。
3. Worker 使用私有模型副本；硬超时只终止 AspenOps 创建并核验归属的进程。
4. 缓存身份绑定运行时、后端、模型、注册表和物理请求。
5. 失败写入必须回滚；污染 Worker 必须回收。
6. Mock、Fake COM、公共 Windows 测试和签名均不能自行授予真实工程认证。

结果只有在以下条件全部成立时才是 `ok=true`：

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
- 重复 ID、未知引用、端口方向、自连接、悬空端口和隐式多连接检查；
- recycle cycle 警告或严格拒绝策略；
- JSON 深度、对象数量、元数据和标识符预算；
- 对 `code`、`script`、`shell`、`python`、`vba`、`command` 和原始 Tree Path 的拒绝；
- 拓扑、编译器、执行、收敛、守恒、修复轮次和人工介入的独立 benchmark 字段。

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

`process-ir-dashboard.html` 提供问题、后端声明和 Agent pipeline 视图。详细规则见 [Process Intent IR](docs/process-intent-ir.md)。

---

## CLI、Python 与 MCP

![CLI、Python 与 MCP 统一入口](docs/assets/readme/cli-mcp-workflow.svg)

三个入口复用同一 Settings、Policy、Scheduler、Worker 和 Evidence 实现，不创建平行的模拟器驱动。

| 入口 | 主要用途 | 安全边界 |
|---|---|---|
| CLI | 演示、诊断、批处理、调度、优化、认证与验证 | 参数化命令，无任意代码执行 |
| Python | 嵌入批处理、调度、优化和证据流程 | 使用同一策略与数据模型 |
| MCP | AI Agent 发现、规划、提交、查询和验证 | 精确 14 个窄工具，无任意 Shell/COM/Tree Path |

主要命令：

```text
demo
doctor
dry-run
run-batch
submit
job
scheduler
benchmark
optimize
certify
certification-preflight
certify-licensed
verify-licensed-bundle
verify-bundle
mcp
```

---

## 典型工作流

### 1. 先验证，再执行批处理

```bash
uv run aspenops dry-run examples/batch-request.example.json

uv run aspenops run-batch examples/batch-request.example.json \
  --output var/aspenops-state/results.json \
  --bundle var/aspenops-state/run-bundle.zip
```

### 2. 运行耐久后台任务

终端 1：启动常驻调度服务。该进程持续领取数据库中的任务，按 Ctrl+C 安全停止。

```bash
uv run aspenops scheduler
```

终端 2：严格验证并入队，然后查询同一个状态数据库中的任务。

```bash
JOB_ID=$(
  uv run aspenops submit examples/batch-request.example.json |
  python -c 'import json,sys; print(json.load(sys.stdin)["job_id"])'
)
uv run aspenops job "$JOB_ID"
```

### 3. 执行预算受限的约束优化

```bash
uv run aspenops optimize examples/optimization-request.example.json \
  --output var/aspenops-state/optimization-result.json
```

### 4. 验证证据包

```bash
uv run aspenops verify-bundle var/aspenops-state/run-bundle.zip
```

### 5. 启动本地 MCP stdio 服务

```bash
uv run aspenops mcp
```

MCP 不提供 `eval`、任意文件系统、任意 Shell、VBA、无限制 COM 方法或原始 Tree Path 写入。

---

## 调度与恢复

![耐久调度生命周期](docs/assets/readme/scheduler-lifecycle.svg)

`submit` 只验证并耐久入队；`scheduler` 是处理队列的常驻服务；`job` 只读取状态，不会隐式创建 Worker 或 PoolManager。调度器使用 SQLite WAL、幂等提交、租约、心跳、取消期限和最大尝试次数：

```text
validate
→ persist QUEUED
→ claim lease
→ heartbeat RUNNING
→ isolated Worker
→ atomic COMPLETED / FAILED / CANCELLED
```

- 租约过期或服务重启后，有剩余尝试的任务进入 `retry_wait`，耗尽尝试后进入 `dead_letter`；
- 已请求取消的任务在恢复或租约过期时进入 `cancelled`；
- 取消只终止归属已核验的 Worker；
- CasePool 复用受 backend、模型、registry、并发与可见性身份限制；
- 证据与最终状态必须原子提交，不能只记录“Run2 返回”。

---

## 工业应用场景

![工业应用场景](docs/assets/readme/industrial-scenarios.svg)

| 场景 | AspenOps 能做什么 | 不能替代什么 |
|---|---|---|
| 参数扫描 | 对温度、压力、流量、回流比等语义变量执行有界批处理 | 工程师对工况范围的批准 |
| 约束优化 | 在评价预算内输出可行性和 Pareto 证据 | 设备、控制和安全审查 |
| 回归与资格验证 | 比较 baseline/candidate、重复性和容差 | 真实 Aspen 许可证与物理认证 |
| 运行决策支持 | 对既有获批模型进行 what-if 分析 | 生产 DCS 自动控制或闭环写入 |

AspenOps 不直接连接或写入生产 DCS；它生成受治理的模拟证据供合格工程师决策。

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

Knowledge 阶段只读；Concept 与 Parameter 只能输出验证后的 IR；Execution 只能调用 declared available 的受限后端；Repair 有轮次、时间和求解预算；Review 独立检查物理、收敛、约束、守恒和人工批准。

---

## 多模拟器能力声明

![多模拟器能力矩阵](docs/assets/readme/backend-capabilities.svg)

| 后端 | 当前执行 | IR 自动建模编译器 | 当前边界 |
|---|---|---|---|
| Mock | available | planned | 跨平台软件测试，不代表 Aspen 物理 |
| Aspen Plus | available，持证 Windows | planned | 运行既有获批模型 |
| HYSYS | available，持证 Windows | planned | 运行既有获批模型 |
| DWSIM | planned | planned | **未实现，无 adapter** |
| IDAES | planned | planned | **未实现，无 adapter** |
| Modelica/FMI | planned | planned | **未实现，无 adapter** |

**planned ≠ implemented；compiler ≠ executor；签名 ≠ 工程批准。**

---

## 自动测试与质量门

![自动测试矩阵](docs/assets/readme/test-matrix.svg)

四个权威 workflow：

| 工作流 | 固定环境 | 作用 |
|---|---|---|
| `ci.yml` | `ubuntu-24.04`；Python 3.11/3.12/3.13 | Ruff、格式、strict mypy、六组合依赖审计、全量测试、分支覆盖率、构建、Wheel、Mock、MCP、Process Intent IR 和 dashboard |
| `windows-control-plane.yml` | `windows-2025`；Python 3.12 | Windows Job、IPC、Fake Aspen/HYSYS、PowerShell、路径、IR 和治理合同 |
| `generate-performance-evidence.yml` | `ubuntu-24.04`；Python 3.12 | 受信 baseline/candidate、双冻结环境和稳定回归证据 |
| `licensed-aspen-certification.yml` | `ubuntu-24.04` guard → 持证 Windows | 主干守卫、SHA 绑定、Mock/IR 软件门、证据隔离和真实 COM |

冻结依赖审计覆盖 `Linux 与 Windows × Python 3.11、3.12、3.13`，即六组合。托管 runner、第三方 Actions 和 `uv 0.11.16` 固定版本；工作流权限保持 `contents: read`。

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
uv run aspenops demo
```

artifact 名称同时包含 `github.run_id` 与 `github.run_attempt`。当前 job 的证据写入 `$RUNNER_TEMP`，上传通过 `${{ runner.temp }}` 读取，并统一使用 `if-no-files-found: error`。缺失 JUnit 或提前失败显示 `INCOMPLETE`；出现 failure/error 显示 `FAIL`。

---

## 可复现实验证据

![证据链](docs/assets/readme/evidence-chain.svg)

```text
validated intent
→ exact trusted main SHA
→ isolated Worker execution
→ convergence / feasibility / balances
→ run_id + run_attempt artifact
→ hashes and optional signature
→ qualified human acceptance
```

性能任务先验证 `GITHUB_REF == refs/heads/main`。非主干调度写入 `dispatch-ref.txt` 与 `dispatch-guard.log`，再以退出码 2 **显式失败**，而不是 all-skipped。`actions/checkout` 读取受信工作流版本，candidate 与 baseline 经 `--end-of-options` 和 ancestor 检查后使用已验证 SHA 的 detached checkout。

默认性能 baseline：

```text
ebef32ee1f2be74df5d5c5489e7ca86d35ac7bb2
```

Mock 性能只代表编排性能，不代表真实 Aspen 求解速度。

---

## 持证 Aspen 认证

![持证认证流程](docs/assets/readme/licensed-certification.svg)

持证工作流的关键合同：

1. 固定 `ubuntu-24.04` guard 验证 `refs/heads/main`。
2. `expected_head_sha` 必须等于本次调度的 `GITHUB_SHA`。
3. 初始 `actions/checkout` 必须匹配该 SHA，随后执行已验证的 detached checkout。
4. 自托管 job 在 checkout 前创建 `$RUNNER_TEMP/aspenops-licensed-artifact-<GITHUB_RUN_ID>-<GITHUB_RUN_ATTEMPT>`。
5. `run-metadata.txt` 记录 run、ref、SHA 和批准身份。
6. Mock JUnit、dashboard、成功证据副本和最终 `job_status` 进入本次 runner-temp 目录。
7. 真实运行使用 `LICENSED_EVIDENCE_DIR=ASPENOPS_STATE_DIR/licensed-certification/<GITHUB_RUN_ID>-<GITHUB_RUN_ATTEMPT>`。
8. 固定 concurrency group `licensed-aspen-certification` 串行执行。
9. 上传只读取本次 `${{ runner.temp }}`，名称含 `github.run_attempt`，并使用 `if-no-files-found: error`。

软件只能生成：

```text
PENDING_REAL_ASPEN_CERTIFICATION
```

真实认证仍需持证 Windows、有效许可证、获批模型、签名材料和流程工程师验收。开放认证门见 issue `#16`。

---

## 项目结构

```text
.github/workflows/       四个权威自动化工作流
docs/                    架构、Windows、性能、认证与质量文档
docs/assets/readme/      十二张受测试治理的 README SVG
examples/                批处理、优化与 Process Intent 示例
scripts/                 校验器、dashboard、benchmark 与 Windows 设置
src/aspenops_nexus/      控制平面、后端、Worker、调度、优化、证据与 MCP
tests/                   Linux、Windows、工作流、文档和安全合同测试
var/                     可复现基线、审计清单和本地运行状态
```

---

## 故障排查

| 现象 | 首先检查 | 处理原则 |
|---|---|---|
| `doctor --probe` 显示未就绪 | Python 位数、COM ProgID、许可证、允许目录 | 不要绕过 preflight 或硬编码裸 COM |
| 路径被拒绝 | `ASPENOPS_ALLOWED_ROOTS` 与 realpath | 将模型、registry、状态和输出放入获批绝对根目录 |
| 批处理返回 `ok=false` | communication、engine、converged、feasible、balances | 分别修复，不把 Run2 返回当作收敛 |
| 任务一直是 `pending` | 是否有 `aspenops scheduler` 常驻服务，状态目录是否一致 | 启动调度服务；不要期待 `submit` 自己在退出后继续运行 |
| 后台任务停留在 running | lease、heartbeat、Worker PID、取消期限 | 让调度器回收过期租约，不手工杀不明 Aspen 进程 |
| dashboard 显示 `INCOMPLETE` | JUnit/coverage 是否在当前 job 生成 | 不复用旧制品，不把缺证据当 PASS |
| README SVG 不显示 | 文件名大小写、XML、字体与资源安全测试 | 使用仓库本地、自包含、无 CJK 内嵌文字的 SVG |
| 持证工作流不运行 | ref、`expected_head_sha`、环境批准、自托管标签 | 仅在受保护 `main` 与持证主机执行 |

---

## 路线图

![AspenOps 路线图](docs/assets/readme/roadmap.svg)

### 已实现

- Process Intent IR、严格验证、canonical JSON 和 SHA-256 图身份；
- Aspen Plus/HYSYS 既有模型控制面；
- Mock、Fake COM、Windows Job Object、耐久调度、优化和 MCP；
- 冻结 CI、dashboard、证据 bundle 和持证认证边界。

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
- 工业模型与版本资格认证。

任何能力都不能在缺少**代码 + 测试 + 证据**时从 planned 改为 available。

---

## AI 生成视觉资产清单

以下十二张原创、自包含 SVG 存放在 `docs/assets/readme/`，没有外部图片或字体依赖：

1. `hero-architecture.svg`
2. `process-intent-ir.svg`
3. `agent-pipeline.svg`
4. `backend-capabilities.svg`
5. `com-isolation.svg`
6. `cli-mcp-workflow.svg`
7. `scheduler-lifecycle.svg`
8. `industrial-scenarios.svg`
9. `test-matrix.svg`
10. `evidence-chain.svg`
11. `licensed-certification.svg`
12. `roadmap.svg`

`tests/test_readme_visual_assets.py` 检查双语引用、完整清单、XML、大小、路径、无障碍、渲染可移植性、脚本、事件、远程资源、Data URI 和工作流接入。

---

## 文档、贡献与安全边界

- [Architecture](docs/architecture.md)
- [Process Intent IR](docs/process-intent-ir.md)
- [External Agent Integration](docs/external-agent-integration.md)
- [Windows Setup](docs/windows-setup.md)
- [Performance](docs/performance.md)
- [Certification](docs/certification.md)
- [Test Audit](docs/automated-test-audit-2026-07-22.md)
- [Quality Report](docs/quality-report.md)
- [Contributing](CONTRIBUTING.md)
- [Security](SECURITY.md)

自动化不证明任意 Aspen 版本都能启动、任意模型都收敛，也不证明物性、反应、设备或控制假设工程上正确。代码采用 Apache-2.0；不得提交客户模型、专有物性/动力学、生产 DCS 数据、许可证、私钥、Token、内部主机或商业证据包。
