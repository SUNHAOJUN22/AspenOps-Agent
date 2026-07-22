<div align="center">

# AspenOps 2.0

## Aspen Plus、Aspen HYSYS 与 AI Agent 之间的确定性执行控制平面

### Codex / Claude Code / MCP → 语义工艺意图 → 隔离执行 → Aspen 求解 → 工程判定 → 可复现实验证据

**不是 GUI 宏，不是几行 `Tree.FindNode()`，也不是让大模型直接接触 COM。**  
**AspenOps 负责授权、隔离、单位、收敛、约束、守恒、并发、审计和证据。**

[English](README.en.md) · [Architecture](docs/architecture.md) · [Windows Setup](docs/windows-setup.md) · [Performance](docs/performance.md) · [Certification](docs/certification.md) · [Test Audit](docs/automated-test-audit-2026-07-22.md) · [Security](SECURITY.md)

[![CI main push](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/ci.yml/badge.svg?branch=main&event=push)](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/ci.yml?query=branch%3Amain+event%3Apush)
[![Windows main push](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/windows-control-plane.yml/badge.svg?branch=main&event=push)](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/windows-control-plane.yml?query=branch%3Amain+event%3Apush)
![Python](https://img.shields.io/badge/Python-3.11--3.13-3776AB)
![Version](https://img.shields.io/badge/version-2.0.0-111827)
![License](https://img.shields.io/badge/license-Apache--2.0-0F766E)
![Aspen](https://img.shields.io/badge/Aspen-Plus%20%7C%20HYSYS-005A9C)

</div>

---

## 当前权威状态

| 项目 | 状态 |
|---|---|
| 默认及唯一长期分支 | `main` |
| 软件包 | `aspenops-nexus 2.0.0` |
| 公共测试矩阵 | Python 3.11、3.12、3.13 |
| 已归档便携式基线 | Actions run `29814739487` |
| Python 3.12 基线 | 72 个测试模块，563 passed，0 failed，0 skipped，16.73 s |
| 综合分支感知覆盖率 | 94.9719800747198% |
| 语句 / 分支覆盖率 | 96.23677786818551% / 90.84880636604774% |
| CI 覆盖率下限 | 94.5% |
| 已归档 Windows 公共门 | Actions run `29814739334`，104 passed，2.06 s |
| MCP 工具数 | 14 |
| 真实 Aspen 认证 | 等待持证 Windows、获批模型和工程师审核 |

上述数字来自已下载并检查的 JUnit、coverage JSON 和日志，不是从 README 反推。它们是**已验证归档基线**，不是对任意后续提交的自动声明。顶部徽章只显示 `main` 的 `push` 状态。

本轮对当前工作流表面进行了额外隔离验证：

```text
15/15 工作流治理与持证工作流测试通过
4/4 GitHub Actions YAML 文件可解析
全部 Bash run 块通过 bash -n 语法检查
PowerShell AST 解析已加入 Windows 自动工作流
```

完整记录：

- [`docs/automated-test-audit-2026-07-22.md`](docs/automated-test-audit-2026-07-22.md)
- [`docs/quality-report.md`](docs/quality-report.md)
- [`docs/single-main-audit.json`](docs/single-main-audit.json)
- [`var/consolidation/final-main-manifest.json`](var/consolidation/final-main-manifest.json)

公共 CI 验证控制平面，不冒充 Aspen Plus/HYSYS 的真实物理模型认证。

---

## 一句话定义

> AspenOps 把有状态、会阻塞、版本敏感、许可证受限的 Aspen 桌面模拟器，封装为可被 Agent、CLI 和 Python 工作流安全调用的确定性执行引擎。

```text
Agent 决定研究什么
Aspen 求解热力学和流程方程
AspenOps 决定操作是否允许、单位是否正确、运行是否收敛、结果是否可行、守恒是否闭合、证据是否可复现
```

---

## 为什么普通 COM 脚本不够

```python
app = Dispatch("Apwn.Document.XX.0")
app.InitFromArchive2(case)
app.Tree.FindNode(path).Value = x
app.Engine.Run2()
```

这能演示 COM，却没有解决：

- ProgID 随 Aspen 版本变化；
- COM 对象不能安全跨线程或跨进程共享；
- `Run2()` 返回不等于收敛；
- 阻塞求解无法可靠终止；
- 热启动、旧结果和状态污染；
- LLM 构造任意 Tree Path 导致误写或越权；
- 单位错误产生“数值正常、物理错误”的结果；
- 并发超过许可证、内存或稳定上限；
- 模型、注册表、请求和结果不可追溯；
- 公共 CI 没有商业 Aspen，却被误写成“真实模型已认证”。

AspenOps 将这些问题转化为明确的数据模型、进程边界、状态机、验证门和证据包。

---

## 系统架构

```text
┌────────────────────────────────────────────────────────────────────┐
│ Codex / Claude Code / MCP Client / Python                          │
│ 变量、DOE、约束、目标和结果需求；不接触原始 COM                    │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ typed MCP / CLI / JSON
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│ AspenOps Control Plane                                             │
│ Policy · Registry · Units · Bounds · Dry Run · Scheduler · Audit   │
│ Cache · Evidence · Certification · Optimization                    │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ one batched RPC per point
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│ Persistent CasePool                                                │
│ private process · COM STA · private model copy · one session       │
└──────────────┬───────────────────┬──────────────────────┬───────────┘
               ▼                   ▼                      ▼
          Aspen Plus          Aspen HYSYS             Mock backend
```

### 不可破坏的不变量

1. 一个 COM 对象只属于一个 Windows 子进程和一个 STA apartment。
2. Agent 只调用语义变量，不构造原始 Aspen Tree Path。
3. 每个 Worker 使用源模型的私有副本，不覆盖主模型。
4. 每个工况只进行一次批量 IPC 事务。
5. 硬超时只终止 AspenOps 创建并验证归属的进程。
6. 通信、引擎返回、收敛、可行性和守恒闭合是独立状态。
7. Mock CI 只证明控制平面，不证明真实 Aspen 物理结果。
8. 持证运行仍须流程工程师审核物性、反应、设备假设和适用范围。

---

## 有效性契约

只有以下状态全部成立，结果才令 `ok=true`：

```text
communication_ok
AND engine_ok
AND converged
AND feasible
AND balances_passed
```

每个结果保留：

- 请求/响应关联；
- 引擎返回和收敛证据；
- 约束实际值、阈值、容差和违反量；
- 物料、能量或元素守恒的绝对与相对残差；
- 请求、结果、模型和注册表 SHA-256；
- 环境、时间和证据包位置。

---

## 核心能力

### 确定性执行

- 独立子进程、COM STA、私有模型副本；
- 持久 CasePool 和动态任务领取；
- 内容寻址缓存与同批次去重；
- Worker 按寿命或点数回收；
- 许可证、内存和模型稳定性共同限制有效并发；
- SQLite WAL 作业库、租约、心跳、重试、取消和 owner fencing。

### 语义安全

- 注册表声明读写权限、标识符、原生单位、维度、上下界和候选定位器；
- 拒绝路径穿越、反斜线注入和模板式标识符；
- HYSYS 默认使用项目拥有的 Spreadsheet Contract；
- MCP 不提供任意 Shell、Python、VBA、`eval`、通用 COM 方法或无限制 Tree Path 写入。

### DOE 与优化

- Latin Hypercube；
- bounded grid；
- nearest-neighbor 工况排序；
- 有界 `DE/best/1/bin`；
- Deb-style 可行性排序；
- 确定性随机种子；
- 预算、并发、失败惩罚、取消和检查点。

---

## 快速开始：无需 Aspen

```bash
git clone https://github.com/SUNHAOJUN22/AspenOps-Agent.git
cd AspenOps-Agent
uv lock --check
uv sync --frozen --extra dev --extra agent --extra signing

uv run aspenops demo
uv run aspenops dry-run examples/batch-request.example.json
uv run aspenops benchmark --points 24 --workers 1,2,4
uv run aspenops certify examples/batch-request.example.json --repeats 3
```

---

## 本地完整质量门

```bash
uv lock --check
uv sync --frozen --extra dev --extra agent --extra signing

uv run ruff check .
uv run ruff format --check .
uv run mypy src

uv run pytest \
  --cov=aspenops_nexus \
  --cov-branch \
  --cov-report=term-missing \
  --cov-report=json:var/coverage.json \
  --junitxml=var/junit.xml \
  --durations=20 \
  --cov-fail-under=94.5

uv build
uv run python scripts/check_mcp.py
uv run aspenops --version
uv run aspenops --help
uv run aspenops demo
```

pytest 仓库策略：

```text
pytest >= 8.3
strict markers
strict configuration
strict xfail
ResourceWarning = error
```

---

## 自动测试与长期工作流

仓库只保留四个权威工作流：

| 工作流 | 触发方式 | 环境 | 职责 |
|---|---|---|---|
| `ci.yml` | `main` push、PR、手动 | Ubuntu；Python 3.11/3.12/3.13 | 全量测试、分支覆盖率、Ruff、格式、mypy、构建、Mock、MCP、Wheel、README 命令 |
| `windows-control-plane.yml` | `main` push、PR、手动 | `windows-latest`；Python 3.12 | Windows Job、进程归属、IPC、调度、归档、Fake Aspen/HYSYS、PowerShell AST、工作流治理 |
| `generate-performance-evidence.yml` | 手动 | Ubuntu；Python 3.12 | 不可变 baseline、独立重复、稳定性能回归策略 |
| `licensed-aspen-certification.yml` | 受保护手动执行 | 自托管持证 Windows | 精确 SHA、路径门、软件回归、preflight、真实 COM、签名证据、人工审核 |

### 工作流治理规则

`tests/test_workflow_governance.py` 和持证工作流专项测试强制：

- 第三方 Actions 固定到完整 40 位 commit SHA；
- `contents: read`，checkout 不保留写凭据；
- 禁止 `pull_request_target`、`contents: write` 和静默 `continue-on-error`；
- 所有环境执行 `uv lock --check` 与 `uv sync --frozen`；
- 同时审计命名步骤的 `uses:` 与简写 `- uses:`；
- 手动输入只能通过环境变量进入 Shell，不得直接插值到脚本；
- 性能工作流使用固定可信并发组；
- baseline ref 先解析成完整提交 SHA，再创建 worktree；
- 制品名称使用 `github.run_id`，不使用任意输入；
- 持证计划必须是单行、仓库相对路径，并限制在 workspace 内；
- 持证状态目录必须是单行绝对路径，并位于绝对允许根目录内；
- 规范化计划/状态路径通过 `GITHUB_ENV` 传给后续步骤；
- Windows CI 使用 PowerShell AST 解析 `setup_windows.ps1`；
- Windows 初始化脚本必须加载 `.env`、保留原进程 PATH、冻结依赖并检查退出码。

### 覆盖率策略

现有覆盖率只比门槛高约 0.47 个百分点。后续优先补测：

```text
scheduler.py
pool.py
worker.py
provenance.py
batch.py
convergence.py
```

在复杂边界补齐前，不为漂亮数字盲目提高门槛。

---

## Windows + Aspen Plus / HYSYS

### 前置条件

- 原生 64 位 Windows；
- Python 3.11–3.13 与 `uv`；
- Aspen Plus 和/或 Aspen HYSYS；
- 有效许可证及明确席位上限；
- 非保密、在 GUI 中稳定收敛的资格模型；
- 经 Variable Explorer 或 HYSYS Spreadsheet 核验的案例注册表；
- 位于绝对允许根目录内的模型和结果目录。

### 推荐安装

```powershell
git clone https://github.com/SUNHAOJUN22/AspenOps-Agent.git
cd AspenOps-Agent
powershell -ExecutionPolicy Bypass -File scripts/setup_windows.ps1
```

脚本会：

1. 开启严格 PowerShell 行为；
2. 缺少时通过 `winget` 安装 `uv`；
3. 刷新机器/用户 PATH，同时保留当前进程 PATH；
4. 再次确认 `uv` 可调用；
5. 校验 `uv.lock`；
6. 冻结安装 `windows + agent + dev + signing`；
7. 创建并解析 `.env`；
8. 把 `.env` 加载到当前进程；
9. 使用加载后的后端执行 `doctor --probe`；
10. 检查每个外部命令退出码。

首次复制的 `.env` 默认为 Mock。改成 `aspen_plus` 或 `hysys` 后重新执行脚本。

### 首次真实模型

```powershell
uv run aspenops dry-run D:/AspenModels/request.json
uv run aspenops run-batch D:/AspenModels/request.json `
  --output D:/AspenResults/results.json `
  --bundle D:/AspenResults/run-bundle.zip
uv run aspenops verify-bundle D:/AspenResults/run-bundle.zip
```

从一个 Worker 和一个已知收敛点开始。约束、守恒、重复性、内存和许可证行为稳定后再增加并发。

详细说明见 [`docs/windows-setup.md`](docs/windows-setup.md)。

---

## 版本兼容策略

AspenOps 不把某个 `Apwn.Document.N.0` 写死为“最新版本”。它会：

1. 优先采用显式 `ASPENOPS_PROGID` / `ASPENOPS_HYSYS_PROGID`；
2. 扫描 64 位与 32 位 Registry View；
3. 枚举版本化 Automation Server；
4. 按数字版本从新到旧尝试；
5. 使用 `DispatchEx` 创建隔离实例；
6. 保留无版本 ProgID 作为回退；
7. 把实际成功的 ProgID 和应用暴露版本写入证据。

发现并调用不等于完成认证。正式兼容性仍需目标版本、许可证、获批模型和工程审核。

---

## CLI

| 命令 | 用途 |
|---|---|
| `aspenops demo` | Mock 端到端示例 |
| `aspenops doctor --probe` | 主机、策略和 Automation Server 诊断 |
| `aspenops dry-run REQUEST` | 不打开 Aspen，验证路径、语义、单位、边界和并发 |
| `aspenops run-batch REQUEST` | 执行批处理并生成完整性包 |
| `aspenops submit REQUEST` | 提交耐久后台任务 |
| `aspenops job JOB_ID` | 查看任务状态和结果 |
| `aspenops benchmark` | 便携式调度基准 |
| `aspenops optimize REQUEST` | 受预算约束的批量优化 |
| `aspenops certify REQUEST` | 重复性门，不授予真实认证 |
| `aspenops certification-preflight PLAN` | 不打开 COM，验证持证计划 |
| `aspenops certify-licensed PLAN` | 在获批持证主机执行计划 |
| `aspenops verify-licensed-bundle BUNDLE` | 验证签名认证包 |
| `aspenops verify-bundle BUNDLE` | 验证普通运行包 |
| `aspenops mcp` | 启动本地 STDIO MCP Server |

---

## MCP / Codex / Claude Code

仓库包含 `.codex/config.toml`、`.mcp.json` 和 `CLAUDE.md`。

MCP 精确暴露 14 个工具：

```text
system_info
list_semantic_variables
dry_run_request
run_batch_sync
submit_batch
submit_optimization
optimization_status
optimization_result
cancel_optimization
job_status
job_result
list_recent_jobs
cancel_job
verify_evidence_bundle
```

推荐链路：

```text
system_info
→ list_semantic_variables
→ dry_run_request
→ submit_batch / submit_optimization
→ job_status / optimization_status
→ job_result / optimization_result
→ verify_evidence_bundle
```

---

## 性能模型

```text
T_naive ≈ N × (T_start + T_open + T_solve + T_read)

T_pool ≈ W × (T_start + T_open)
       + N_unique / W × (T_solve + T_verify)
       + T_IPC + T_schedule

W_effective = min(W_configured, W_license, W_memory, W_stability)
```

加速来自持久会话、批量 IPC、去重、缓存、动态领取、私有模型并行和 Worker 回收。Mock 调度基准不得描述为真实 Aspen 求解加速。

---

## 三级认证

1. **控制平面认证**：Mock 验证隔离、IPC、调度、缓存、单位、约束、守恒和证据。
2. **持证模拟器运行时认证**：原生 Windows + Aspen + 有效许可证 + 获批资格案例。
3. **工程模型验证**：流程工程师审核物性、组分、反应、设备、工况和装置/实验对应。

权威持证工作流：

```text
.github/workflows/licensed-aspen-certification.yml
```

安全顺序：

```text
精确获批 SHA
→ 规范化计划和状态目录
→ 冻结依赖
→ 隔离 Mock 软件回归
→ preflight
→ 明确人工批准
→ 真实 COM 执行
→ 签名包验证
→ 工程师最终审核
```

运行时只能生成 `PENDING_REAL_ASPEN_CERTIFICATION`，不能自行授予最终工程认证。

---

## 安全与数据边界

不得提交：

- 客户 `.bkp`、`.apw`、`.apwz`、`.hsc`；
- 专有动力学、物性参数或生产 DCS 数据；
- 许可证文件或敏感许可证服务器信息；
- 账号、Token、内部主机和私有路径；
- 含商业工艺数据的证据包；
- 签名私钥。

生产环境使用最小允许根目录、最小许可证席位和最小 Worker 上限。密钥、许可证、专有模型与机密证据必须位于仓库外。

---

## 仓库结构

```text
src/aspenops_nexus/        运行时、控制平面、适配器和优化
tests/                     单元、集成、故障边界和工作流治理
examples/                  Mock、请求、注册表和认证计划示例
docs/                      架构、性能、质量、认证、安全和部署
scripts/                   Windows 安装、基准和接口核验
.github/workflows/         四个权威长期工作流
```

---

## 自动测试明确不证明什么

公共自动化不证明：

- 任意商业 Aspen 版本都能在本机启动；
- 任意模型一定收敛；
- 物性、反应和设备假设工程上正确；
- Mock 性能等于真实 Aspen 性能；
- 软件可以替代流程工程师；
- 软件可以自行授予真实 Aspen 工程认证。

---

## 许可证

代码采用 Apache-2.0。Aspen 产品、模型文件、数据库、供应商文档和许可证受各自条款约束。AspenOps 不附带 Aspen 软件、许可证或专有模型。

<div align="center">

## Let agents design the experiment. Let Aspen solve the physics. Let AspenOps enforce the truth.

**AspenOps 2.0 — deterministic process simulation for the agentic era.**

</div>
