<div align="center">

# AspenOps 2.0

## Aspen Plus、Aspen HYSYS 与 AI Agent 之间的确定性执行控制平面

**Agent / CLI / Python → 统一流程意图 → 隔离执行 → 非线性求解 → 工程判定 → 可复现实验证据**

[English](README.en.md) · [Architecture](docs/architecture.md) · [Process Intent IR](docs/process-intent-ir.md) · [Windows Setup](docs/windows-setup.md) · [Performance](docs/performance.md) · [Performance Audit](docs/performance-audit-2026-07-27.md) · [Certification](docs/certification.md) · [Quality Report](docs/quality-report.md) · [Security](SECURITY.md) · [Contributing](CONTRIBUTING.md)

[![CI main push](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/ci.yml/badge.svg?branch=main&event=push)](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/ci.yml?query=branch%3Amain+event%3Apush)
[![Windows main push](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/windows-control-plane.yml/badge.svg?branch=main&event=push)](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/windows-control-plane.yml?query=branch%3Amain+event%3Apush)
![Python](https://img.shields.io/badge/Python-3.11--3.13-3776AB)
![Version](https://img.shields.io/badge/version-2.0.0-111827)
![License](https://img.shields.io/badge/license-Apache--2.0-0F766E)

</div>

![AspenOps 总体架构](docs/assets/readme/hero-architecture.svg)

> 本 README 使用二十二张为 AspenOps 原创生成的 AI SVG 功能图。图像只表达仓库中已实现的合同和明确标注的 planned 路线，不把 Mock、Fake COM、软件测试、便携性能、签名材料、版本检查或哈希完整性包装成真实 Aspen 工程认证。

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
| 冻结 MCP SDK | `1.28.1`；软件包要求 `mcp>=1.9,<2` |
| 真实 Aspen 认证 | `PENDING_REAL_ASPEN_CERTIFICATION` |

上述数字来自已检查的 JUnit、coverage JSON 和日志，**不是对任意后续提交的自动声明**。顶部徽章反映当前 `main` push 工作流；历史数字不能替代当前提交的新 Actions 证据。

公共 CI 能证明控制平面、配置与路径策略、IPC、进程隔离、调度、缓存、优化、数值 fail-closed、归档、接口、Process Intent、MCP 兼容性、便携性能合同和文档合同；它不能证明商业 Aspen 安装、许可证、物性方法、反应模型或工程模型已经合格。

---

## 产品定位

AspenOps 不是让模型自由生成 COM 脚本的包装器。它把 Aspen Plus、Aspen HYSYS、CLI、Python 和 AI Agent 接入同一套确定性控制面：

- Agent 只能提交语义变量或验证后的 `aspenops.flowsheet/v1`；
- 每个真实 Automation Server 位于独立 Windows 子进程和 STA apartment；
- 每个 Worker 使用私有模型副本，主模型不被覆盖；
- 调度并发受许可证槽、资源预算和生命周期策略共同限制；
- 通信、引擎返回、收敛、约束、物料/能量衡算和人工批准分别判定；
- 非有限数值、错误布尔协议和不可序列化诊断不得悄悄成为有效证据；
- 每个可接受结果都绑定请求、模型、注册表、代码提交和证据哈希；
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

Windows 真实后端增加 `--extra windows`：

```powershell
uv sync --frozen --extra windows --extra dev --extra agent --extra signing
uv run aspenops doctor --probe
```

首次运行默认使用 Mock。Mock 只用于跨平台软件验证，不代表 Aspen Plus/HYSYS 的物理结果。

仓库外安装 `agent` extra 时，Wheel 元数据自身限制 MCP Python SDK 为受支持的 1.x：

```bash
python -m pip install "aspenops-nexus[agent]"
python -m pip show mcp
```

有效范围为：

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

完整 Windows 设置见 [Windows Setup](docs/windows-setup.md)。

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

`visible="false"` 和 `cache_failures="false"` 这类真值字符串不会被当作布尔值接受。真实后端缺少允许根目录、状态目录越界或输出路径逃逸时，执行在 Worker、COM 和证据创建之前 fail closed。

---

## 核心工业安全不变量

![Windows COM 进程隔离](docs/assets/readme/com-isolation.svg)

1. 一个 COM 对象只属于一个 Windows 子进程和一个 STA apartment。
2. Agent 不构造任意 Aspen Tree Path，不执行任意 Python、Shell 或 VBA。
3. Worker 使用私有模型副本；硬超时只终止 AspenOps 创建并核验归属的进程。
4. 缓存身份绑定运行时、后端、模型、注册表和物理请求。
5. 失败写入必须回滚；污染 Worker 必须回收。
6. Mock、Fake COM、公共 Windows 测试和签名均不能自行授予真实工程认证。

---

## 独立有效性门

![独立模拟有效性门](docs/assets/readme/validity-gates.svg)

结果不是因为模拟器方法返回就自动有效。AspenOps 分别检查：

```text
communication_ok
AND engine_ok
AND converged
AND feasible
AND constraints_passed
AND balances_passed
AND finite_json_evidence
```

约束和衡算中的 `NaN`、正负 Infinity、非数字值以及派生算术溢出都会 fail closed，并写入结构化违规代码；结果和证据使用 JSON 安全值，`allow_nan=False`。Aspen Plus 与 HYSYS 的运行状态使用明确布尔、COM `-1/0/1` 或受支持字符串解析，不使用 `bool("False")` 这类 Python truthiness 猜测。

---

## 统一流程意图 IR

![Process Intent IR](docs/assets/readme/process-intent-ir.svg)

统一中间表示：

```text
aspenops.flowsheet/v1
```

它描述组件、物性方法、设备、端口、流股、参数和安全元数据，并提供确定性排序、canonical JSON、SHA-256 图身份、端口/连接检查、循环策略、数量预算，以及对 `code`、`script`、`shell`、`python`、`vba`、`command` 和原始 Tree Path 的拒绝。

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

`process-ir-dashboard.html` 提供问题、后端能力和 Agent pipeline 视图。DWSIM、IDAES、Modelica 和 Aspen/HYSYS 自动流程编译器仍为 planned，当前**未实现**。

---

## CLI、Python 与 MCP

![CLI、Python 与 MCP 统一入口](docs/assets/readme/cli-mcp-workflow.svg)

三个入口复用同一 Settings、Policy、Scheduler、Worker 和 Evidence 实现，不创建平行模拟器驱动。

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

---

## MCP 兼容性与服务生命周期

![MCP 兼容性与 Scheduler 生命周期](docs/assets/readme/mcp-runtime-lifecycle.svg)

项目元数据和构建后的 Wheel `Requires-Dist` 都要求：

```text
mcp>=1.9,<2
```

冻结环境锁定 `mcp 1.28.1`。运行时在导入 `FastMCP` 前验证 SDK；构建后的 Wheel METADATA 由标准库解析器重新验证，`<20` 不能冒充 `<2`。

```text
server startup → scheduler.start()
serve 14 constrained tools
server shutdown → scheduler.stop() → Worker / PoolManager cleanup
```

该生命周期只证明软件资源被治理，不代表真实 Aspen 模型已经获得工程认证。

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

---

## 约束优化闭环

![约束优化闭环](docs/assets/readme/optimization-lifecycle.svg)

优化器支持 continuous、integer、categorical 和 ordinal 变量，minimize/maximize 多目标及权重，并限制变量数、目标数、种群、代数和总评价次数。

```text
validate mixed variables and objectives
→ enforce finite optimization budget
→ seeded differential-evolution batches
→ CasePool / Worker evaluation
→ communication + convergence + constraints + balances
→ atomic checkpoint + cancellation
→ best candidate + Pareto evidence
```

DE 仍保持每代一次批量评价和相同评价预算；候选索引抽样不再为每个个体构造完整列表。Pareto 计算先保持顺序地去重，并在可行点存在时先排除不可行点；全不可行时只保留最小 violation。Mock 结果标记为 `control-plane-only`；真实 Aspen 结果保持 `licensed-runtime-pending-engineering-review` 和 `PENDING_REAL_ASPEN_CERTIFICATION`，不把 Pareto 前沿当作工程批准。

---

## 跨进程路径固定

![耐久队列跨工作目录路径固定](docs/assets/readme/durable-path-portability.svg)

```text
当前提交目录
→ 解析 model_path 与 registry_path
→ 固定为绝对路径
→ 写入 SQLite 耐久记录
→ scheduler 可从任意工作目录执行
```

CLI 提交结果明确返回：

```text
paths_pinned = true
submission_cwd = absolute submission directory
```

真实后端仍会再次执行允许根目录和 realpath 检查。直接调用低层 `BackgroundScheduler.submit()` 的 Python 代码应传入绝对路径，或先调用 `pin_durable_request_paths()`。

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
- 取消只终止归属已核验的 Worker；
- 证据与最终状态必须原子提交，不能只记录 “Run2 returned”。

---

## 缓存、批内去重与单航班

![缓存、批内去重与单航班](docs/assets/readme/cache-singleflight.svg)

缓存键绑定运行时 schema、软件版本、backend、稳定运行时身份、模型 SHA-256、注册表 SHA-256 和物理请求。查找顺序为内存 LRU 与 SQLite WAL；损坏 JSON 会被删除并重新计算。

```text
canonical physical identity
→ memory LRU / SQLite WAL lookup
→ same-batch duplicate collapse
→ concurrent single-point leader + followers
→ one governed solver call
→ computed / persistent_cache / inflight_singleflight provenance
```

缓存 hit 阈值使用 O(1) 累计计数，批量键按 SQLite 参数预算迭代分块，持久化 JSON 使用紧凑编码，并在 schema 初始化后执行 `PRAGMA optimize`。同一个不可变请求对象在单个 batch 中复用 cache-key 计算；一个可缓存求解结果只生成一次规范字典。same-batch 与 singleflight 副本使用深拷贝保持嵌套结果隔离，不降低模型、注册表、运行时或物理请求身份强度。

---

## Worker 所有权与回收

![Worker 所有权与回收](docs/assets/readme/worker-ownership-recycle.svg)

```text
source model
→ private worker-generation copy
→ spawned child process + one simulator owner
→ correlated IPC request
→ hard deadline and ownership supervision
→ graceful close or verified recycle
```

回收原因包括 timeout、crash、protocol error、tainted write、point budget、worker age、cancellation 和 lease ownership loss。回收只作用于 AspenOps 核验归属的 Worker 或其受监督后代；原模型不被覆盖，旧临时副本在清理时删除。

---

## 性能工程与证据

![性能热点与证据地图](docs/assets/readme/performance-hotspot-map.svg)

![冷启动与热启动证据](docs/assets/readme/cold-warm-startup.svg)

AspenOps 将性能结论分为两类：

1. **低噪声硬合同**：cache-key 次数、solver 调用次数、规范序列化次数、dedup 数量、缓存 flush 状态和 Pareto 支配比较次数；
2. **环境敏感诊断**：wall time、median、P95、min/max、CV、Python `-X importtime`、cProfile、tracemalloc 与 RSS。

```bash
uv run python scripts/measure_cli_startup.py \
  --output var/ci/cli-startup.json \
  --trials 7 \
  --warmups 2

uv run python scripts/measure_operation_counts.py \
  --output var/ci/operation-counts.json
```

CLI console script 先进入轻量 bootstrap。`--version`、顶层帮助和子命令帮助不会导入 Pool、Scheduler、优化器、认证、证据或 MCP；实际命令只委托一次给完整 CLI。`cli-startup.json` 使用同一解释器、同一机器比较 bootstrap 和 full CLI，并单独保存 import-time 诊断；`operation-counts.json` 保存 cProfile、tracemalloc、RSS 和确定性操作计数。

当前自动合同要求：100 个相同请求对象只计算 1 次 cache key、调用 1 次 solver、生成 1 次规范序列化并得到 99 个 `same_batch_dedup` 结果；1024 个缓存命中达到阈值后待刷总数为 0；1000 个完全重复 Pareto 点不执行支配比较。wall time 在共享 runner 上只作为证据，不使用过窄硬阈值。

历史 benchmark 文件仍是便携 Mock 编排的归档证据，不自动代表当前 HEAD。它们不证明 Aspen Plus/HYSYS 模型打开、非线性求解、收敛或工业工程性能。模型与 registry SHA-256 仍按内容计算；没有采用基于 mtime/size 的快捷跳过。Scheduler `list_recent()` 的 N+1 查询与复合索引迁移记录在性能审计中，未通过旁路实现改变租约恢复语义。

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

Knowledge 只读；Concept 与 Parameter 只能输出验证后的 IR；Execution 只能调用 declared available 的受限后端；Repair 有轮次、时间和求解预算；Review 独立检查物理、收敛、约束、守恒和人工批准。

---

## 多模拟器能力声明

![多模拟器能力矩阵](docs/assets/readme/backend-capabilities.svg)

| 后端 | 当前执行 | IR 自动建模编译器 | 当前边界 |
|---|---|---|---|
| Mock | available | planned | 跨平台软件测试，不代表 Aspen 物理 |
| Aspen Plus | available，持证 Windows | planned | 运行既有获批模型；严格解析 engine running flag |
| HYSYS | available，持证 Windows | planned | 运行既有获批模型；严格解析 solver running flag |
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
| `ci.yml` | `ubuntu-24.04`；Python 3.11/3.12/3.13 | Ruff、格式、strict mypy、六组合依赖审计、全量测试、分支覆盖率、构建、Wheel、Mock、MCP、IR、配置、缓存、优化、性能证据和耐久队列 smoke |
| `windows-control-plane.yml` | `windows-2025`；Python 3.12 | Windows Job、IPC、Fake Aspen/HYSYS、PowerShell、配置、路径、性能低噪声合同、IR 和治理合同 |
| `generate-performance-evidence.yml` | `ubuntu-24.04`；Python 3.12 | 受信 baseline/candidate、双冻结环境和稳定回归证据 |
| `licensed-aspen-certification.yml` | `ubuntu-24.04` guard → 持证 Windows | 主干守卫、SHA 绑定、Mock/IR/性能软件门、证据隔离和真实 COM |

冻结依赖审计覆盖 `Linux 与 Windows × Python 3.11、3.12、3.13`，即六组合。托管 runner、第三方 Actions 和 `uv 0.11.16` 固定版本；权限保持 `contents: read`。

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

artifact 名称同时包含 `github.run_id` 与 `github.run_attempt`。当前 job 证据写入 `$RUNNER_TEMP`，上传通过 `${{ runner.temp }}` 读取，并统一使用 `if-no-files-found: error`。缺失 JUnit 或提前失败显示 `INCOMPLETE`；出现 failure/error 显示 `FAIL`。

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

性能任务先验证 `GITHUB_REF == refs/heads/main`。非主干调度写入 `dispatch-ref.txt` 与 `dispatch-guard.log`，再以退出码 2 **显式失败**，而不是 all-skipped。`actions/checkout` 读取受信工作流版本，candidate 与 baseline 经 `--end-of-options` 和祖先检查后使用已验证 SHA 的 detached checkout。

默认性能 baseline：

```text
ebef32ee1f2be74df5d5c5489e7ca86d35ac7bb2
```

Mock 性能只代表编排性能，不代表真实 Aspen 求解速度。

---

## 证据包完整性与真实性

![证据包完整性与真实性](docs/assets/readme/evidence-integrity.svg)

`write_run_bundle()` 使用 `allow_nan=False` 写入 `request.json`、`results.json` 和 `environment.json`。manifest 绑定请求、结果、模型、注册表、运行时 schema/version，以及每个成员的 SHA-256 和大小。

```text
bounded ZIP structure
→ exact required members
→ member size + SHA-256 declarations
→ request / result / model / registry hashes
→ optional Ed25519 manifest signature
→ trusted-key verification
```

未签名包只提供内部完整性检查；Ed25519 只有在公钥可信时才提供来源真实性。哈希、签名和软件 PASS 均不证明物性、动力学或流程模型工程上正确。

---

## 持证 Aspen 认证

![持证认证流程](docs/assets/readme/licensed-certification.svg)

关键合同：

1. 固定 `ubuntu-24.04` guard 验证 `refs/heads/main`。
2. `expected_head_sha` 必须等于本次调度的 `GITHUB_SHA`。
3. 初始 `actions/checkout` 必须匹配该 SHA，随后执行已验证的 detached checkout。
4. checkout 前创建 `$RUNNER_TEMP/aspenops-licensed-artifact-<GITHUB_RUN_ID>-<GITHUB_RUN_ATTEMPT>`。
5. `run-metadata.txt` 记录 run、ref、SHA 和批准身份。
6. Mock JUnit、dashboard、证据副本和最终 `job_status` 进入本次 runner-temp 目录。
7. 真实运行使用 `LICENSED_EVIDENCE_DIR=ASPENOPS_STATE_DIR/licensed-certification/<GITHUB_RUN_ID>-<GITHUB_RUN_ATTEMPT>`。
8. 固定 concurrency group `licensed-aspen-certification` **串行**执行。
9. 上传只读取本次 `${{ runner.temp }}`，名称含 `github.run_attempt`，并使用 `if-no-files-found: error`。

软件只能生成：

```text
PENDING_REAL_ASPEN_CERTIFICATION
```

真实认证仍需持证 Windows、有效许可证、获批模型、签名材料和流程工程师验收。

---

## 项目结构

```text
.github/workflows/       四个权威自动化工作流
docs/                    架构、Windows、性能、认证与质量文档
docs/assets/readme/      二十二张受测试治理的 README SVG
examples/                批处理、优化与 Process Intent 示例
scripts/                 校验器、dashboard、benchmark、性能探针与 Windows 设置
src/aspenops_nexus/      控制平面、后端、Worker、调度、缓存、优化、证据与 MCP
tests/                   Linux、Windows、工作流、文档、安全和性能合同测试
var/                     可复现基线、审计清单和本地运行状态
```

---

## 故障排查

| 现象 | 首先检查 | 处理原则 |
|---|---|---|
| `doctor --probe` 未就绪 | Python 位数、COM ProgID、许可证、允许目录 | 不绕过 preflight 或硬编码裸 COM |
| 直接 `Settings(...)` 创建失败 | backend、mode、布尔字段、预算和 `Path` 类型 | 修正配置，不绕过构造期校验 |
| 路径被拒绝 | `ASPENOPS_ALLOWED_ROOTS` 与 realpath | 将模型、registry、状态和输出放入获批绝对根目录 |
| 提交通过但 scheduler 在另一目录启动 | `paths_pinned` 与 `submission_cwd` | 使用当前版本重新提交，数据库中应保存绝对模型和注册表路径 |
| MCP 启动报告 SDK 大版本不兼容 | `python -m pip show mcp` | 安装 `mcp>=1.9,<2`；不要绕过版本门 |
| MCP 服务退出后仍有 Worker | lifespan、Scheduler stop 与当前进程归属 | shutdown 必须执行 `scheduler.stop()` |
| 批处理返回 `ok=false` | communication、engine、converged、constraints、balances | 分别修复，不把 Run2 返回当作收敛 |
| 结果出现 `constraint_non_finite` | 节点值、单位转换和派生溢出 | 不放宽限制；修复模型或量纲 |
| 结果出现 `balance_non_finite` | 衡算项、系数、单位和残差 | 使用结构化 diagnostics 定位非有限项 |
| 启动证据波动较大 | `coefficient_of_variation`、runner、Python 和 CPU | wall time 只作环境证据；依赖 import 与 operation-count 硬合同 |
| operation-count 不匹配 | cache-key、solver、序列化、dedup 或 Pareto 逻辑 | 视为确定性性能回归，不用多跑几次掩盖 |
| 任务一直是 `pending` | 是否有 `aspenops scheduler` 常驻服务 | 启动调度服务 |
| 后台任务停留在 running | lease、heartbeat、Worker PID、取消期限 | 让调度器回收过期租约，不手工杀不明 Aspen 进程 |
| 缓存结果异常 | cache key、模型/registry 哈希、损坏记录 | 损坏记录应被删除并重新计算 |
| dashboard 显示 `INCOMPLETE` | 当前 job 是否生成 JUnit/coverage | 不复用旧制品，不把缺证据当 PASS |
| README SVG 不显示 | 文件名大小写、XML、字体与资源安全测试 | 使用仓库本地、自包含、无 CJK 内嵌文字的 SVG |
| 持证工作流不运行 | ref、`expected_head_sha`、环境批准、自托管标签 | 仅在受保护 `main` 与持证主机执行 |

---

## 路线图

![AspenOps 路线图](docs/assets/readme/roadmap.svg)

### 已实现

- Process Intent IR、严格验证、canonical JSON 和 SHA-256 图身份；
- Aspen Plus/HYSYS 既有模型控制面；
- 环境与 Python API 统一的 fail-closed Settings 和路径策略；
- 独立通信、引擎、收敛、约束、衡算和有限数值证据门；
- Mock、Fake COM、Windows Job Object、耐久调度、取消、缓存、单航班、优化和 MCP；
- CLI 轻量 bootstrap、低噪声 operation-count、import-time、cProfile 和内存性能证据；
- MCP 1.x 依赖/Wheel/运行时兼容门与 FastMCP 生命周期资源清理；
- 冻结 CI、dashboard、证据 bundle 和持证认证边界。

### 下一阶段

- JobStore `list_recent()` 单查询行解码和复合索引迁移；
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

以下二十二张原创、自包含 SVG 存放在 `docs/assets/readme/`：

1. `hero-architecture.svg`
2. `policy-path-safety.svg`
3. `validity-gates.svg`
4. `process-intent-ir.svg`
5. `agent-pipeline.svg`
6. `backend-capabilities.svg`
7. `com-isolation.svg`
8. `worker-ownership-recycle.svg`
9. `cli-mcp-workflow.svg`
10. `mcp-runtime-lifecycle.svg`
11. `optimization-lifecycle.svg`
12. `durable-path-portability.svg`
13. `scheduler-lifecycle.svg`
14. `cache-singleflight.svg`
15. `performance-hotspot-map.svg`
16. `cold-warm-startup.svg`
17. `industrial-scenarios.svg`
18. `test-matrix.svg`
19. `evidence-chain.svg`
20. `evidence-integrity.svg`
21. `licensed-certification.svg`
22. `roadmap.svg`

`tests/test_readme_visual_assets.py` 检查双语引用、完整清单、XML、大小、路径、无障碍、渲染可移植性、脚本、事件、远程资源、Data URI、源码能力绑定和三道工作流接入。

---

## 文档、贡献与安全边界

- [Architecture](docs/architecture.md)
- [Process Intent IR](docs/process-intent-ir.md)
- [External Agent Integration](docs/external-agent-integration.md)
- [Windows Setup](docs/windows-setup.md)
- [Performance](docs/performance.md)
- [Performance Audit](docs/performance-audit-2026-07-27.md)
- [Certification](docs/certification.md)
- [Test Audit](docs/automated-test-audit-2026-07-22.md)
- [Quality Report](docs/quality-report.md)
- [Contributing](CONTRIBUTING.md)
- [Security](SECURITY.md)

自动化不证明任意 Aspen 版本都能启动、任意模型都收敛，也不证明物性、反应、设备或控制假设工程上正确。代码采用 Apache-2.0；不得提交客户模型、专有物性/动力学、生产 DCS 数据、许可证、私钥、Token、内部主机或商业证据包。
