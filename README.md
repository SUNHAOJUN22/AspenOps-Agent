<div align="center">

# AspenOps 2.0

## Aspen Plus、Aspen HYSYS 与 AI Agent 之间的确定性工程控制平面

**自然语言意图 → 受控工程文档 → 强类型流程图 → 离线编译计划 → 隔离执行 → 工程判定 → 可验证证据**

[English](README.en.md) · [Architecture](docs/architecture.md) · [Process Intent IR](docs/process-intent-ir.md) · [Windows Setup](docs/windows-setup.md) · [Performance](docs/performance.md) · [Performance Audit V2](docs/performance-audit-2026-07-27-v2.md) · [Certification](docs/certification.md) · [Quality Report](docs/quality-report.md) · [Security](SECURITY.md) · [Contributing](CONTRIBUTING.md)

[![CI main push](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/ci.yml/badge.svg?branch=main&event=push)](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/ci.yml?query=branch%3Amain+event%3Apush)
[![Windows main push](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/windows-control-plane.yml/badge.svg?branch=main&event=push)](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/windows-control-plane.yml?query=branch%3Amain+event%3Apush)
![Python](https://img.shields.io/badge/Python-3.11--3.13-3776AB)
![Version](https://img.shields.io/badge/version-2.0.0-111827)
![License](https://img.shields.io/badge/license-Apache--2.0-0F766E)

</div>

![AspenOps 总体架构](docs/assets/readme/hero-architecture.svg)

> 本 README 使用二十二张 AspenOps 原创、AI 辅助设计的自包含 SVG 示意图。图像只表达仓库中已经实现的合同或明确标注的 planned 路线；它们不把 Mock、Fake COM、签名、哈希、离线编译或公共 Windows 测试包装成真实 Aspen 工程认证。

---

## 当前权威状态

| 项目 | 权威状态 |
|---|---|
| 默认及唯一长期分支 | `main` |
| 软件包 | `aspenops-nexus 2.0.0` |
| 公共测试矩阵 | Python 3.11、3.12、3.13；Linux 与 Windows 六组合依赖审计 |
| Phase 0 | 不可变执行快照、缓存/证据身份、读写合同：已实现 |
| Phase 1 | `aspenops.process-requirement/v1`、`aspenops.flowsheet/v2`、工程规则、模板与 SVG 预览：已实现 |
| Phase 2 | Aspen Plus/HYSYS 14/15 离线能力配置与确定性编译合同：已实现，`OFFLINE_CONTRACT_ONLY` |
| Phase 3–7 | 签名运行时资格、licensed link、执行前新鲜授权、签名撤销链与独立见证收据：已实现的软件授权合同 |
| 已有模型执行控制面 | Mock 可移植；Aspen Plus/HYSYS 需要持证 Windows 与已批准模型 |
| 原生新建 Aspen/HYSYS 流程图 | **未实现生产适配器；不得声称可自动创建任意装置** |
| 自然语言到原生 COM | **planned；自然语言不得直接操作 COM、Tree Path、Shell、Python 或 VBA** |
| MCP 工具数 | 14 个窄工具 |
| MCP SDK | 冻结环境 `1.28.1`；Wheel 合同 `mcp>=1.9,<2` |
| 真实 Aspen 认证 | `PENDING_REAL_ASPEN_CERTIFICATION` |

**已验证归档基线**只证明对应提交和对应 Actions 运行。历史 JUnit、coverage JSON、Windows 日志和签名证据**不是对任意后续提交的自动声明**；当前 `main` 是否通过，以顶部徽章和该提交最新 Actions 为准。

公共 CI 可以证明软件控制面、数据合同、配置与路径策略、IPC、进程隔离、调度、缓存、优化、非有限数 fail-closed、证据归档、离线编译合同、签名与撤销验证。它不能证明商业 Aspen 安装、许可证席位、物性方法、反应动力学、设备选型、流程拓扑或工程结果已经合格。

---

## 能力分层：什么已经实现，什么仍然受阻

![AspenOps 分层化工 Agent](docs/assets/readme/agent-pipeline.svg)

```text
Natural-language request
        ↓  planned parser / guided approval
ProcessRequirementDocument v1
        ↓  implemented validation
ProcessDesignIR v2
        ↓  implemented engineering rules
Versioned offline compilation plan
        ↓  signed runtime qualification + fresh authorization
Native adapter boundary
        ↓  production Aspen/HYSYS builder not yet implemented
Licensed simulator + human engineering acceptance
```

### 已实现

- 对已有批准模型执行语义化读写、批处理、调度、缓存、约束优化和重复性门；
- 将关键需求值标注为 `USER_PROVIDED`、`APPROVED_DEFAULT`、`INFERRED_PENDING_APPROVAL` 或 `UNKNOWN`；
- 对组件、物性方法、设备、端口、流股、反应和 recycle 形成强类型 ProcessDesignIR v2；
- 对端口方向、物料/能量域、必需连接、设备规格、自由度、循环与审批状态执行确定性规则；
- 生成规范化图身份、布局身份和外部 SVG 预览；
- 为 Aspen Plus/HYSYS 14/15 生成不可执行的离线编译合同；
- 通过 Ed25519 资格、撤销策略、检查点和短期 witness receipt 控制原生执行授权边界；
- 对模型、注册表、运行时、请求、结果和证据成员执行 SHA-256 绑定。

### 未实现或尚未通过外部门

- 从任意中文/英文自然语言自动补齐所有工程条件；
- 在 Aspen Plus/HYSYS 原生界面中可靠新建设备、连接端口、布置流程图并保存重开；
- 对任意流程自动选择正确物性方法、反应模型、塔器规格和收敛策略；
- 商业 Aspen V15 Golden Cases、原生 topology/layout roundtrip、真实求解重复性；
- 人工工艺、安全、物性和设备验收。

因此，系统的保证不是“任何一句话都能自动得到正确装置”，而是：**缺少工程输入、拓扑不一致、资格过期、写入未生效、未收敛、约束失败、衡算失败或证据身份不一致时，不得冒充成功。**

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

Windows 真实后端需要额外安装 pywin32，并先进行只读探测：

```powershell
uv sync --frozen --extra windows --extra dev --extra agent --extra signing
uv run aspenops doctor --probe
```

首次运行默认使用 Mock。Mock 只验证跨平台软件行为，不代表 Aspen Plus/HYSYS 的热力学或设备结果。

仓库外安装 Agent extra：

```bash
python -m pip install "aspenops-nexus[agent]"
python -m pip show mcp
```

有效范围：

```text
mcp>=1.9,<2
```

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

真实 Aspen 示例必须使用绝对允许根目录，状态目录也必须位于允许根目录内：

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
5. 环境变量入口与 Python `Settings(...)` 直接构造使用同一 fail-closed 校验。
6. 未知 backend/mode、字符串伪布尔值、非有限数、零/负预算和非 `Path` 参数会在对象创建时被拒绝。
7. 私钥、Token、许可证秘密、客户模型路径和生产数据不得进入仓库。

完整设置见 [Windows Setup](docs/windows-setup.md)。

---

## 配置与路径安全策略

![配置与路径安全策略](docs/assets/readme/policy-path-safety.svg)

```text
environment or Python API
→ backend / mode / Boolean / budget validation
→ real backend absolute-root validation
→ expanduser + resolve
→ relative_to approved root
→ readonly / default / enhanced operation gate
```

`visible="false"` 和 `cache_failures="false"` 这类字符串不会被 Python truthiness 当作真值接受。真实后端缺少允许根目录、状态目录越界或输出路径逃逸时，执行在 Worker、COM 和证据创建之前 fail closed。

---

## 核心工业安全不变量

![Windows COM 进程隔离](docs/assets/readme/com-isolation.svg)

1. 一个 COM 对象只属于一个 Windows 子进程和一个 STA apartment。
2. Agent 不构造任意 Aspen Tree Path，不执行任意 Python、Shell 或 VBA。
3. Worker 使用私有模型与注册表快照；源模型不被覆盖。
4. 父进程和 Worker 共同核对模型、注册表和运行时身份。
5. 写入后必须回读；验证失败必须回滚，回滚失败则 Worker tainted 并回收。
6. 缓存只接受与当前执行身份一致的结果。
7. Mock、Fake COM、公共 Windows 测试、离线编译和签名均不能自行授予真实工程认证。

---

## 独立有效性门

![独立模拟有效性门](docs/assets/readme/validity-gates.svg)

```text
communication_ok
AND engine_ok
AND converged
AND feasible
AND constraints_passed
AND balances_passed
AND finite_json_evidence
```

约束和衡算中的 `NaN`、正负 Infinity、非数字值以及派生算术溢出都会 fail closed，并写入 `constraint_non_finite`、`balance_non_finite` 等结构化违规代码。所有结果和证据使用 `allow_nan=False`。Aspen Plus 与 HYSYS 的运行标志只接受明确布尔、COM `-1/0/1` 或支持的字符串，不使用 `bool("False")` 猜测。

---

## 统一流程意图 IR

![Process Intent IR](docs/assets/readme/process-intent-ir.svg)

基础兼容表示：

```text
aspenops.flowsheet/v1
```

它描述组件、物性方法、设备、端口、流股、参数和安全元数据，并提供确定性排序、canonical JSON、SHA-256 图身份、连接检查、循环策略和数量预算，同时拒绝 `code`、`script`、`shell`、`python`、`vba`、`command` 和原始 Tree Path。

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

`process-ir-dashboard.html` 展示问题、后端能力和 Agent pipeline。DWSIM、IDAES、Modelica/FMI 仍为 planned，当前未实现生产 adapter。

---

## ProcessRequirement 与 ProcessDesignIR v2

![多模拟器能力声明](docs/assets/readme/backend-capabilities.svg)

V2 设计层把自然语言与 COM 隔开：

```text
aspenops.process-requirement/v1
→ readiness: READY_FOR_DESIGN / NEEDS_ENGINEERING_INPUT
→ aspenops.flowsheet/v2
→ deterministic engineering rules
→ canonical design hash + layout hash
```

内部对象 ID 使用稳定 ASCII；Unicode 只作为显示名称，并拒绝 NUL、替换字符和双向控制字符。工程关键值未获批准时，设计状态必须保持 `NEEDS_ENGINEERING_INPUT` 或 `PLAN_ONLY`。

内置模板覆盖 Heater–Flash、Mixer–Heater–Separator、压缩冷却分离、反应分离循环、精馏序列、吸收再生、气体脱水和 HYSYS 天然气预处理等概念骨架。模板只减少重复建模工作，不能代替用户条件、物性选择或工程批准。

---

## 离线编译、运行时资格与撤销链

![AspenOps 路线图](docs/assets/readme/roadmap.svg)

```text
validated ProcessDesignIR v2
→ versioned Aspen Plus/HYSYS capability profile
→ deterministic CompilationPlan
→ signed RuntimeQualification
→ qualified licensed link
→ fresh runtime authorization
→ signed chained revocation policy
→ independent short-lived witness receipt
→ native adapter boundary
```

当前内置 Aspen Plus/HYSYS 14/15 profile 均为 `OFFLINE_CONTRACT_ONLY`。它们可以证明编译计划结构、预期 topology、布局身份、保存/重开和读回步骤合同，但**不能授权实际 COM 建模**。

原生执行边界要求：

- 当前可信 Ed25519 资格密钥；
- 当前 profile ID/hash；
- 当前 adapter code SHA-256 与 runtime identity SHA-256；
- 通过的 Golden Case ID；
- 未过期的签名撤销策略与受保护检查点；
- 独立于策略 authority 的短期 witness receipt；
- 在第一次 adapter 访问前重新验证全部材料。

这些机制解决软件授权与证据漂移，不证明工艺设计正确。

---

## CLI、Python 与 MCP

![CLI、Python 与 MCP 统一入口](docs/assets/readme/cli-mcp-workflow.svg)

| 入口 | 主要用途 | 安全边界 |
|---|---|---|
| CLI | 演示、诊断、批处理、调度、优化、认证与验证 | 参数化命令，无任意代码执行 |
| Python | 嵌入批处理、调度、优化、IR 和证据流程 | 使用同一策略与数据模型 |
| MCP | AI Agent 发现、规划、提交、查询和验证 | 精确 14 个窄工具，无任意 Shell/COM/Tree Path |

主要命令：

```text
demo
doctor
dry-run
run-batch
submit
job
cancel
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

自然语言 Agent 只能形成受控需求或计划。仓库当前没有把“任意自然语言 → 任意 Aspen 原生对象操作”作为可用工具暴露。

---

## MCP 兼容性与服务生命周期

![MCP 兼容性与 Scheduler 生命周期](docs/assets/readme/mcp-runtime-lifecycle.svg)

项目元数据和构建后的 Wheel `Requires-Dist` 都要求 `mcp>=1.9,<2`，冻结环境锁定 `mcp 1.28.1`。运行时在导入 FastMCP 前检查版本范围。

```text
server startup
→ scheduler.start()
→ serve 14 constrained tools
→ server shutdown
→ scheduler.stop()
→ Worker / PoolManager cleanup
```

MCP 的证据验证只允许管理员 trust store 中的 key ID，不允许 Agent 传入任意公钥文件路径。

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

终端 1：

```bash
uv run aspenops scheduler
```

终端 2：

```bash
JOB_ID=$(
  uv run aspenops submit examples/batch-request.example.json |
  python -c 'import json,sys; print(json.load(sys.stdin)["job_id"])'
)
uv run aspenops job "$JOB_ID"
uv run aspenops cancel "$JOB_ID" --grace-s 2
```

提交结果包含：

```text
paths_pinned = true
submission_cwd = absolute submission directory
```

### 3. 执行预算受限的约束优化

```bash
uv run aspenops optimize examples/optimization-request.example.json \
  --output var/aspenops-state/optimization-result.json
```

### 4. 验证普通证据包

```bash
uv run aspenops verify-bundle var/aspenops-state/run-bundle.zip
```

### 5. 启动本地 MCP stdio 服务

```bash
uv run aspenops mcp
```

---

## 约束优化闭环

![约束优化闭环](docs/assets/readme/optimization-lifecycle.svg)

```text
validate mixed variables and objectives
→ enforce finite optimization budget
→ seeded differential-evolution batches
→ CasePool / Worker evaluation
→ communication + convergence + constraints + balances
→ atomic checkpoint + cancellation
→ best candidate + Pareto evidence
```

优化器保持有限评价预算、批量求解、可行性优先和 Pareto 证据。Mock 结果标记为 control-plane-only；真实 Aspen 结果仍是 `licensed-runtime-pending-engineering-review` 与 `PENDING_REAL_ASPEN_CERTIFICATION`。

---

## 跨进程路径固定

![耐久队列跨工作目录路径固定](docs/assets/readme/durable-path-portability.svg)

```text
submission_cwd
→ resolve model_path and registry_path
→ pin absolute paths
→ persist SQLite job
→ scheduler may run from another working directory
→ recheck allowed roots before real execution
```

直接调用低层 `BackgroundScheduler.submit()` 的 Python 代码应传入绝对路径，或先调用 `pin_durable_request_paths()`。

---

## 调度与恢复

![耐久调度生命周期](docs/assets/readme/scheduler-lifecycle.svg)

```text
validate
→ persist pending
→ claim lease
→ heartbeat running
→ isolated Worker
→ atomic completed / failed / cancelled
```

- 租约过期或服务重启后，有剩余尝试的任务进入 `retry_wait`；
- 尝试耗尽后进入 `dead_letter`；
- 已请求取消的任务在恢复或租约过期时进入 `cancelled`；
- 失去 lease ownership 后必须回收 Worker，旧 owner 不能提交成功结果；
- 证据与最终状态必须原子采用，不能只记录“Run2 returned”。

---

## 缓存、批内去重与单航班

![缓存、批内去重与单航班](docs/assets/readme/cache-singleflight.svg)

```text
canonical physical identity
→ memory LRU / SQLite WAL lookup
→ same-batch duplicate collapse
→ concurrent single-point leader + followers
→ one governed solver call
→ computed / persistent_cache / inflight_singleflight provenance
```

缓存键绑定运行时 schema、软件版本、backend、稳定运行时身份、模型 SHA-256、注册表 SHA-256 和物理请求。相同 batch 与 singleflight 副本使用深拷贝保持嵌套隔离。

---

## Worker 所有权与回收

![Worker 所有权与回收](docs/assets/readme/worker-ownership-recycle.svg)

```text
source artifacts
→ private model + registry stage
→ parent/child digest handshake
→ spawned child + one simulator owner
→ correlated IPC request
→ hard deadline + Windows Job Object
→ graceful close or verified recycle
```

回收原因包括 timeout、crash、protocol error、tainted write、point budget、worker age、cancellation 和 lease ownership loss。回收只作用于 AspenOps 明确拥有并核验的 Worker 或受监督后代。

---

## 性能工程与证据

![性能热点与证据地图](docs/assets/readme/performance-hotspot-map.svg)

![冷启动与热启动证据](docs/assets/readme/cold-warm-startup.svg)

AspenOps 将性能结论分为：

1. **低噪声硬合同**：cache-key、solver、序列化、dedup、SQLite connection/SELECT 和 Pareto dominance 次数；
2. **环境敏感诊断**：wall time、median、P95、CV、Python importtime、cProfile、tracemalloc 与 RSS。

```bash
uv run python scripts/measure_cli_startup.py \
  --output var/ci/cli-startup.json \
  --trials 7 \
  --warmups 2

uv run python scripts/measure_operation_counts.py \
  --output var/ci/operation-counts.json

uv run python scripts/measure_job_store_queries.py \
  --output var/ci/job-store-query-plan.json \
  --records 1000 \
  --limit 20
```

证据文件：

```text
cli-startup.json
operation-counts.json
job-store-query-plan.json
```

共享 runner 上的 wall time 只作为证据，不使用过窄阈值。Mock 编排性能不代表真实 Aspen `Run2()` 速度。详见 [Performance Audit V2](docs/performance-audit-2026-07-27-v2.md)。

---

## 工业应用场景

![工业应用场景](docs/assets/readme/industrial-scenarios.svg)

| 场景 | AspenOps 当前能做什么 | 不能替代什么 |
|---|---|---|
| 参数扫描 | 对已有获批模型的温度、压力、流量、回流比执行有界批处理 | 工程师对工况范围的批准 |
| 约束优化 | 在评价预算内输出可行性、残差和 Pareto 证据 | 设备、控制和安全审查 |
| 概念流程设计 | 验证 ProcessRequirement、IR v2、模板与离线编译合同 | 真实 Aspen 原生建模与工艺定型 |
| 回归与资格 | 比较 baseline/candidate、重复性、身份和签名 | 商业许可证、真实物理认证与人工签字 |
| 决策支持 | 对既有模型进行 what-if 分析 | 生产 DCS 自动控制或无监督闭环写入 |

AspenOps 不直接连接或写入生产 DCS。

---

## 自动测试与质量门

![自动测试矩阵](docs/assets/readme/test-matrix.svg)

四个权威 workflow：

| 工作流 | 固定环境 | 作用 |
|---|---|---|
| `ci.yml` | `ubuntu-24.04`；Python 3.11/3.12/3.13 | Ruff、格式、strict mypy、六组合依赖审计、全量测试、分支覆盖率、构建、Wheel、Mock、MCP、IR、签名、撤销和耐久队列 smoke |
| `windows-control-plane.yml` | `windows-2025`；Python 3.12 | Windows Job、IPC、Fake Aspen/HYSYS、PowerShell、路径、长路径、授权和治理合同 |
| `generate-performance-evidence.yml` | `ubuntu-24.04`；Python 3.12 | 受信 baseline/candidate、双冻结环境和稳定回归证据 |
| `licensed-aspen-certification.yml` | `ubuntu-24.04` guard → 持证 Windows | SHA、环境、模型、注册表、许可证、真实 COM 和签名证据外部门 |

标准本地门：

```bash
uv lock --check
uv sync --frozen --extra dev --extra agent --extra signing
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run python -m compileall -q src scripts
uv run python scripts/audit_source_tree.py
uv run pytest -W error::ResourceWarning \
  --cov=aspenops_nexus \
  --cov-branch \
  --cov-fail-under=95.0
uv build
uv run python scripts/check_mcp.py
uv run python scripts/validate_process_ir.py examples/process-intent.example.json
uv run aspenops demo
```

手动 workflow 必须先验证 `refs/heads/main`；非主干 dispatch 必须**显式失败**并返回 status 2，而不是 all-skipped。`actions/checkout` 使用受信工作流版本，candidate 以 detached checkout 执行。有关工作流依赖必须保留 `needs: dispatch-guard`。

证据写入 `RUNNER_TEMP`，上传通过 `${{ runner.temp }}`；artifact 名称绑定 `GITHUB_RUN_ID`、`GITHUB_RUN_ATTEMPT` 和 `github.run_attempt`，并设置 `if-no-files-found: error`。

持证流程还绑定：

```text
licensed-aspen-certification
expected_head_sha
GITHUB_SHA
LICENSED_EVIDENCE_DIR
aspenops-licensed-artifact
run-metadata.txt
job_status
serial execution
```

这防止不同 attempt、不同 runner 或并发 license 任务混用证据。

---

## 可复现实验证据

![证据链](docs/assets/readme/evidence-chain.svg)

```text
validated intent
→ exact trusted main SHA
→ private artifact snapshot
→ isolated Worker execution
→ convergence / constraints / balances
→ signed qualification + current revocation + witness
→ run_id + run_attempt artifact
→ qualified human acceptance
```

软件证据链解决“运行了哪一份代码、模型、注册表和授权材料”。它不自动回答“流程是否符合工艺安全与工业设计规范”。

---

## 证据包完整性与真实性

![证据包完整性与真实性](docs/assets/readme/evidence-integrity.svg)

```text
bounded ZIP structure
→ exact required members
→ duplicate-key / non-finite JSON rejection
→ member size + SHA-256 declarations
→ request / result / model / registry / runtime binding
→ optional Ed25519 manifest signature
→ trusted-key verification
```

未签名包只提供内部完整性检查；只有可信 Ed25519 公钥才能提供来源真实性。V3 普通运行包把 Worker 已核验的模型、注册表和稳定运行时身份与结果绑定，不在运行结束后重新把源路径当作执行事实。

哈希、签名和软件 PASS 均不证明物性、动力学或流程模型工程上正确。

---

## 持证 Aspen 资格流程

![持证 Aspen 资格流程](docs/assets/readme/licensed-certification.svg)

`licensed-aspen-certification.yml` 要求：

- self-hosted Windows x64 runner；
- 已安装并持证的 Aspen Plus 或 HYSYS；
- 精确批准的 40 字符 Git SHA；
- 批准模型、注册表和 certification plan SHA-256；
- 真实 ProgID、运行时版本、求解与收敛证据；
- 至少一个有意义约束和可用质量/能量/元素衡算；
- 新模型副本和独立 COM 实例的重复性；
- 可信 Ed25519 签名；
- 工程师对物性、反应、设备、工况和使用范围的人工验收。

在上述流程真实完成之前，状态必须保持：

```text
PENDING_REAL_ASPEN_CERTIFICATION
```

软件不得自授 `REAL_ASPEN_CERTIFIED`。

---

## 项目结构

```text
src/aspenops_nexus/
├── backends/                         # Mock、Aspen Plus、HYSYS 已有模型执行适配器
├── process_requirement.py            # ProcessRequirementDocument v1
├── process_ir.py                     # Process Intent v1
├── process_ir_v2.py                  # ProcessDesignIR v2
├── engineering_rules.py              # 确定性工程规则
├── plant_templates.py                # 受治理装置模板
├── flowsheet_preview.py              # 规范化图和 SVG 预览
├── simulator_capabilities.py         # 版本化离线能力 profile
├── compilation_plan.py               # 确定性离线编译计划
├── native_topology.py                # 原生 topology readback 合同
├── native_builder.py                 # 原生执行安全边界；无生产 Aspen/HYSYS builder
├── runtime_qualification.py           # 签名运行时资格
├── qualified_compilation.py           # 资格化编译包装
├── qualified_licensed_link.py         # licensed plan 精确绑定
├── runtime_execution_authorization.py # 执行前新鲜授权
├── signed_revocation_policy.py        # 签名撤销链与检查点
├── revocation_witness.py              # 独立短期 witness receipt
├── worker.py / pool.py                # 进程隔离、快照、缓存和回收
├── scheduler.py                       # SQLite 租约、取消、重试和原子提交
└── provenance.py                      # V2/V3 证据包与 Ed25519 验证
```

---

## 路线图

当前长期方向按证据门推进，而不是按功能数量推进：

1. 保持单一 `main`，清除临时分支和一次性 workflow；
2. 完成主干 Phase 0–7 软件合同重新资格；
3. 为 Aspen Plus V15 建立有限设备集的真实原生 builder；
4. 为 HYSYS V15 建立独立端口与 Spreadsheet Contract；
5. 对 Heater–Flash、Mixer–Separator、Reactor–Recycle、Column 和 Compression Train 执行真实 Golden Cases；
6. 保存、关闭、重开并比较原生 topology/layout hash；
7. 增加组分、元素和能量衡算；
8. 最后才接入 guided natural-language parser。

**planned ≠ implemented；compiler ≠ executor；签名 ≠ 工程批准。**

---

## 故障排查

### `doctor --probe` 找不到 Aspen

```powershell
uv run aspenops doctor --probe
```

确认使用 64 位原生 Windows Python、安装 `windows` extra、COM ProgID 已注册、许可证可用。不要根据营销版本号猜测 ProgID。

### 请求在 COM 前被拒绝

检查：

- `ASPENOPS_ALLOWED_ROOTS` 是否为绝对路径；
- `ASPENOPS_STATE_DIR` 是否位于允许根目录；
- backend 是否与 `ASPENOPS_BACKEND` 一致；
- 语义注册表 access 是否允许读/写；
- 模型和注册表摘要是否在计划之后发生变化；
- 签名资格、撤销策略、checkpoint 或 witness 是否过期。

### 流程图预览存在，但 Aspen 中没有装置

这是预期边界。SVG 预览和离线编译计划不是原生 Aspen/HYSYS builder。只有真实 adapter 完成创建、回读、保存、关闭、重开并通过 topology/layout 比较后，才能声明原生装置已建立。

### CI 覆盖率显示接近阈值

仓库使用两位精度 coverage 报告，避免 94.98% 被零位精度显示为 95%。不得降低阈值、跳过测试或用文档数字代替当前提交结果。

### 分支治理

仓库只保留一个长期分支 `main`。所有生产结论必须绑定当前 `main` 的精确 SHA 和该 SHA 的 Actions 证据。

---

## 贡献与许可证

- 许可证：Apache-2.0；
- 贡献规则见 [CONTRIBUTING.md](CONTRIBUTING.md)；
- 安全报告见 [SECURITY.md](SECURITY.md)；
- 真实 Aspen 认证跟踪见 [Issue #16](https://github.com/SUNHAOJUN22/AspenOps-Agent/issues/16)。

AspenOps 的目标不是让 AI 自由点击 Aspen，而是建立一个可约束、可回读、可证伪、可撤销、可复现且必须由工程证据放行的执行系统。
