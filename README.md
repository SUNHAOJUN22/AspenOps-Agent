<div align="center">

# AspenOps 2.0

## 为 Aspen Plus、Aspen HYSYS 与 AI Agent 建立可验证、可并发、可审计的执行控制平面

### Codex / Claude Code / MCP → 语义工艺意图 → 隔离执行 → Aspen 求解 → 工程判定 → 可复现实验证据

**不是 GUI 宏，不是几行 `Tree.FindNode()`，也不是让大模型直接操作 COM。**  
**AspenOps 是 AI Agent 与工业流程模拟器之间的确定性执行层。**

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
| 公共测试 Python | 3.11、3.12、3.13 |
| 已归档便携式基线 | Actions run `29814739487` |
| Python 3.12 基线 | 72 个测试模块，563 passed，0 failed，0 skipped，16.73 s |
| 综合分支感知覆盖率 | 94.9719800747198% |
| 语句 / 分支覆盖率 | 96.23677786818551% / 90.84880636604774% |
| CI 覆盖率下限 | 94.5% |
| 已归档 Windows 公共门 | Actions run `29814739334`，104 passed，2.06 s |
| MCP 工具数 | 14 |
| 真实 Aspen 认证 | 工作流已实现；仍需持证 Windows、获批模型和工程师审核 |

上述数字来自已归档的 JUnit、coverage JSON 与日志证据，不是根据 README 自行估算。顶部徽章只显示 `main` 的 `push` 运行状态；公共 CI 证明 AspenOps 控制平面，不证明某个商业 Aspen 版本或具体工艺模型已经完成工程认证。

完整记录：

- [`docs/automated-test-audit-2026-07-22.md`](docs/automated-test-audit-2026-07-22.md)
- [`docs/quality-report.md`](docs/quality-report.md)
- [`docs/single-main-audit.json`](docs/single-main-audit.json)
- [`var/consolidation/final-main-manifest.json`](var/consolidation/final-main-manifest.json)

---

## 一句话定义

> AspenOps 2.0 把 Aspen Plus / Aspen HYSYS 从有状态、会阻塞、版本敏感、许可证受限的桌面模拟器，封装为可被 Codex、Claude Code、MCP 客户端和 Python 工作流安全调用的确定性计算执行引擎。

```text
Agent 决定研究什么
Aspen 求解热力学与流程方程
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

这段代码能演示 COM，但没有解决：

- Aspen 升级后的 ProgID 变化；
- COM 对象跨线程、跨进程的不安全传递；
- `Run2()` 返回但模型未真正收敛；
- 阻塞求解无法可靠中止；
- 热启动、旧结果和模型状态污染；
- LLM 构造任意 Tree Path 造成误写和越权；
- 单位错误产生“数值正常、物理错误”的结果；
- 并发超过许可证、内存或模型稳定上限；
- 模型、注册表、请求与结果不可追溯；
- 公共 CI 没有商业 Aspen，却被错误描述为“真实模型已认证”。

AspenOps 把这些问题变成明确的数据模型、进程边界、状态机、校验规则、证据包和认证门。

---

## 系统架构

```text
┌────────────────────────────────────────────────────────────────────┐
│ Codex / Claude Code / MCP Client / Python                          │
│ 变量、DOE、约束、目标与结果请求；不接触原始 COM                    │
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

### 不可破坏的架构不变量

1. 一个 COM 对象只属于一个 Windows 子进程和一个 STA apartment。
2. Agent 只调用语义变量，不构造原始 Aspen Tree Path。
3. 每个 Worker 使用源模型的私有副本，不覆盖主模型。
4. 一次工况通过一次批量 IPC 完成重置、写入、求解、读取与校验。
5. 硬超时只终止 AspenOps 自己创建并验证归属的进程。
6. 通信、引擎返回、收敛、可行性与守恒闭合是五个独立状态。
7. Mock CI 只证明控制平面，不证明真实 Aspen 物理结果。
8. 持证运行仍须流程工程师审核物性方法、反应、设备假设和适用范围。

---

## 核心能力

### 确定性与安全执行

- 独立子进程、COM STA 和私有模型副本；
- 持久 CasePool、动态任务领取和 Worker 回收；
- 一次工况一次批量 IPC；
- 内容寻址缓存与同批次去重；
- 许可证、内存和稳定性共同限制有效并发；
- 语义注册表声明权限、单位、标识符、边界和候选定位器；
- 路径、标识符和归档输入失败闭合；
- 不提供任意 Shell、Python、VBA、`eval`、通用 COM 方法或任意 Tree Path 写入。

### 工程判定

只有以下状态全部通过，结果才令 `ok=true`：

```text
communication_ok
AND engine_ok
AND converged
AND feasible
AND balances_passed
```

每个结果保留：

- 请求和响应关联；
- 引擎返回与收敛证据；
- 工艺约束实际值、阈值、容差和违反量；
- 物料、能量或元素守恒的绝对与相对残差；
- 请求、结果、模型和注册表 SHA-256；
- 运行环境与证据包路径。

### DOE、优化与耐久任务

- Latin Hypercube、bounded grid、nearest-neighbor 排序；
- 有界 `DE/best/1/bin`；
- Deb-style 可行性排序；
- 确定性随机种子；
- SQLite WAL 作业库；
- pending / running / completed / failed / cancelled / interrupted；
- 租约、心跳、重试、取消、owner fencing 和检查点恢复。

---

## 快速开始：无需 Aspen

### 安装

```bash
git clone https://github.com/SUNHAOJUN22/AspenOps-Agent.git
cd AspenOps-Agent
uv lock --check
uv sync --frozen --extra dev --extra agent --extra signing
```

### Mock 端到端示例

```bash
uv run aspenops demo
```

### dry-run、基准与重复性门

```bash
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

pytest 仓库配置强制：

```text
minimum pytest 8.3
strict markers
strict configuration
strict xfail
ResourceWarning = error
```

---

## 自动测试与长期工作流

仓库只保留四个权威长期工作流：

| 工作流 | 触发方式 | 环境 | 主要职责 |
|---|---|---|---|
| `ci.yml` | `main` push、PR、手动 | Ubuntu；Python 3.11/3.12/3.13 | 全量测试、分支覆盖率、Ruff、格式、mypy、构建、Mock、MCP、Wheel、README 命令 |
| `windows-control-plane.yml` | `main` push、PR、手动 | `windows-latest`；Python 3.12 | Windows Job、进程归属、IPC、调度、归档、Fake Aspen/HYSYS、认证接口 |
| `generate-performance-evidence.yml` | 手动 | Ubuntu；Python 3.12 | 精确 baseline/candidate、独立重复、稳定性能回归策略 |
| `licensed-aspen-certification.yml` | 受保护手动执行 | 自托管持证 Windows | 精确 SHA、软件回归、preflight、真实 COM、签名证据和人工审核边界 |

### 工作流治理规则

自动测试会强制：

- 第三方 Actions 固定到完整 40 位 commit SHA；
- 全局 `contents: read`，checkout 不保留写凭据；
- 禁止 `pull_request_target`、`contents: write` 和静默 `continue-on-error`；
- 所有环境执行 `uv lock --check` 与 `uv sync --frozen`；
- 手动输入只能通过环境变量传给 Shell，不得直接插值到脚本；
- 性能 baseline 先解析成不可变提交 SHA，再创建 worktree；
- 持证计划必须是单行、仓库相对路径，经过规范化和越界检查后才跨步骤传递；
- 制品名称使用 `github.run_id`，不使用任意用户输入；
- Windows 初始化脚本必须加载 `.env`，并在安装后重新检查 `uv`；
- `tests/test_workflow_governance.py` 与持证工作流专项测试锁住上述规则。

### 覆盖率审计

现有覆盖率超过 94.5% 门槛，但余量有限。新增测试优先覆盖：

```text
scheduler.py
pool.py
worker.py
provenance.py
batch.py
convergence.py
```

在这些复杂模块补齐边界前，不为了漂亮数字盲目提高门槛。

---

## Windows + Aspen Plus / HYSYS

### 前置条件

- 原生 64 位 Windows；
- Python 3.11–3.13 与 `uv`；
- Aspen Plus 和/或 Aspen HYSYS；
- 有效许可证与明确席位上限；
- 非保密、在 GUI 中可稳定收敛的资格模型；
- 经 Variable Explorer 或 HYSYS Spreadsheet 核验的案例专用语义注册表；
- 位于允许根目录内的模型和结果目录。

### 安装脚本

```powershell
git clone https://github.com/SUNHAOJUN22/AspenOps-Agent.git
cd AspenOps-Agent
powershell -ExecutionPolicy Bypass -File scripts/setup_windows.ps1
```

脚本会：

1. 检查或通过 `winget` 安装 `uv`；
2. 刷新当前 PowerShell 的 PATH；
3. 校验 `uv.lock`；
4. 冻结安装 `windows + agent + dev + signing`；
5. 创建并加载 `.env`；
6. 使用加载后的配置执行 `aspenops doctor --probe`；
7. 对每个外部命令检查退出码。

首次复制的 `.env` 默认使用 Mock 后端。编辑为 `aspen_plus` 或 `hysys` 后，应重新执行脚本或在当前进程设置相同环境变量。

### 手动等价命令

```powershell
uv lock --check
uv sync --frozen --extra windows --extra dev --extra agent --extra signing
Copy-Item .env.example .env
# 编辑并加载 .env 后：
uv run aspenops doctor --probe
```

### 首次真实模型运行

```powershell
uv run aspenops dry-run D:/AspenModels/request.json
uv run aspenops run-batch D:/AspenModels/request.json `
  --output D:/AspenResults/results.json `
  --bundle D:/AspenResults/run-bundle.zip
uv run aspenops verify-bundle D:/AspenResults/run-bundle.zip
```

从一个 Worker、一个已知收敛点开始。约束、守恒、重复性、内存和许可证行为稳定后再增加并发。

---

## Aspen 版本兼容策略

AspenOps 不把某个 `Apwn.Document.N.0` 写死为“最新版本”。运行时会：

1. 优先采用显式 `ASPENOPS_PROGID` 或 `ASPENOPS_HYSYS_PROGID`；
2. 扫描 64 位和 32 位 Windows Registry View；
3. 枚举版本化 Automation Server；
4. 按数字版本从新到旧尝试；
5. 使用 `DispatchEx` 创建隔离实例；
6. 保留无版本 ProgID 作为回退；
7. 把实际成功的 ProgID 与应用暴露版本写入证据。

“能够发现并调用”不等于“已经认证”。正式兼容性结论仍需目标版本、有效许可证、获批模型和工程审核。

---

## CLI

| 命令 | 用途 |
|---|---|
| `aspenops demo` | 跨平台 Mock 端到端示例 |
| `aspenops doctor --probe` | 检查主机、策略和 Automation Server |
| `aspenops dry-run REQUEST` | 不打开 Aspen，验证路径、语义、单位、边界和并发 |
| `aspenops run-batch REQUEST` | 执行批处理并生成完整性包 |
| `aspenops submit REQUEST` | 提交耐久后台任务 |
| `aspenops job JOB_ID` | 查看任务状态和结果 |
| `aspenops benchmark` | 运行便携式调度基准 |
| `aspenops optimize REQUEST` | 运行受预算约束的批量优化 |
| `aspenops certify REQUEST` | 运行重复性门，不授予真实 Aspen 认证 |
| `aspenops certification-preflight PLAN` | 不打开 COM，验证持证计划 |
| `aspenops certify-licensed PLAN` | 在获批持证主机执行计划 |
| `aspenops verify-licensed-bundle BUNDLE` | 验证签名认证包 |
| `aspenops verify-bundle BUNDLE` | 验证普通运行包 |
| `aspenops mcp` | 启动本地 STDIO MCP Server |

```bash
uv run aspenops --help
uv run aspenops <command> --help
```

---

## MCP / Codex / Claude Code

仓库包含 `.codex/config.toml`、`.mcp.json` 和 `CLAUDE.md`。

MCP 暴露 14 个受控工具：

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

## 标准请求骨架

```json
{
  "backend": "aspen_plus",
  "model_path": "D:/AspenModels/case.bkp",
  "registry_path": "D:/AspenModels/case.registry.json",
  "workers": 1,
  "reset_mode": "reinitialize",
  "timeout_s": 1200,
  "base_writes": [],
  "points": [
    {
      "metadata": {"name": "design-001"},
      "writes": [
        {
          "key": "stream.input.temperature",
          "identifiers": {"stream": "FEED"},
          "value": 95.0,
          "unit": "C"
        }
      ]
    }
  ],
  "reads": [
    {
      "key": "stream.output.purity",
      "identifiers": {"stream": "PRODUCT"},
      "unit": "fraction",
      "required": true
    }
  ],
  "constraints": [],
  "balances": []
}
```

具体 Tree Path 或 HYSYS Spreadsheet 单元格只保存在案例专用注册表内，不放进 Agent 请求。

---

## 性能设计

```text
T_naive ≈ N × (T_start + T_open + T_solve + T_read)

T_pool ≈ W × (T_start + T_open)
       + N_unique / W × (T_solve + T_verify)
       + T_IPC + T_schedule
```

有效并发：

```text
W_effective = min(W_configured, W_license, W_memory, W_stability)
```

加速来自持久会话、批量 IPC、去重、缓存、动态领取、私有模型并行和 Worker 回收。Mock 调度基准不得描述为真实 Aspen 求解加速。

---

## 证据与三级认证

1. **控制平面认证**：Mock 后端验证隔离、IPC、调度、缓存、单位、约束、守恒和证据。
2. **持证模拟器运行时认证**：原生 Windows + Aspen + 有效许可证 + 获批资格案例。
3. **工程模型验证**：流程工程师审核物性方法、组分、反应、设备、工况与装置或实验数据。

权威持证工作流：

```text
.github/workflows/licensed-aspen-certification.yml
```

安全顺序：

```text
精确获批 SHA
→ 冻结依赖
→ 隔离 Mock 软件回归
→ 规范化计划路径
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

生产环境应使用最小允许根目录、最小许可证席位和最小 Worker 上限。密钥、许可证、专有模型与机密证据必须位于仓库外。

---

## 仓库结构

```text
src/aspenops_nexus/
  batch.py
  compat.py
  registry.py
  units.py
  worker.py
  pool.py
  pool_manager.py
  scheduler.py
  evaluation.py
  cache.py
  certification.py
  licensed_certification.py
  provenance.py
  optimization.py
  optimizer.py
  design.py
  mcp_server.py
  backends/
    aspen_plus.py
    hysys.py
    mock.py

tests/                      单元、集成、故障边界与工作流治理
examples/                   Mock、请求、注册表与认证计划示例
docs/                       架构、性能、质量、认证、安全与部署
scripts/                    Windows 安装、基准和接口核验
.github/workflows/           四个权威长期工作流
```

---

## 自动测试明确不证明什么

公共测试不证明：

- 本机能启动任意 Aspen 商业版本；
- 任意模型一定收敛；
- 物性方法、反应和设备假设工程上正确；
- Mock 性能等于真实 Aspen 求解性能；
- 软件可以替代流程工程师；
- 软件可以自行授予真实 Aspen 工程认证。

---

## 许可证

代码采用 Apache-2.0。Aspen Plus、Aspen HYSYS、模型文件、物性数据库、供应商文档和许可证受各自条款约束。AspenOps 不附带 Aspen 软件、许可证或专有模型。

<div align="center">

## Let agents design the experiment. Let Aspen solve the physics. Let AspenOps enforce the truth.

**AspenOps 2.0 — deterministic process simulation for the agentic era.**

</div>
