<div align="center">

# AspenOps 2.0

## 为 Aspen Plus、Aspen HYSYS 与 AI Agent 建立可验证、可并发、可审计的执行控制平面

### Codex / Claude Code / MCP → 语义工艺意图 → 隔离执行 → Aspen 求解 → 工程判定 → 可复现实验证据

**不是 GUI 宏，不是几行 `Tree.FindNode()`，也不是让大模型直接操作 COM。**  
**AspenOps 是 AI Agent 与工业流程模拟器之间的确定性执行层。**

[English](README.en.md) · [Architecture](docs/architecture.md) · [Windows Setup](docs/windows-setup.md) · [Performance](docs/performance.md) · [Certification](docs/certification.md) · [Security](SECURITY.md)

[![CI](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/ci.yml/badge.svg)](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/ci.yml)
[![Windows control plane](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/windows-control-plane.yml/badge.svg)](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/windows-control-plane.yml)
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
| Python | 3.11、3.12、3.13 |
| 最新记录的便携式质量门 | 通过：563 tests，综合分支感知覆盖率 94.97198% |
| CI 覆盖率下限 | 94.5% |
| Windows 公共控制平面 | 通过 |
| MCP 工具数 | 14 |
| 真实 Aspen 许可证环境认证 | 已实现工作流，尚待获批模型与持证 Windows 主机执行 |

审计证据位于：

- `docs/single-main-audit.json`
- `docs/quality-report.md`
- `var/consolidation/final-main-manifest.json`
- `var/consolidation/branch-archive-manifest.json`

上述便携式结果验证的是 AspenOps 控制平面，不冒充 Aspen Plus 或 HYSYS 的真实物理模型认证。

---

## 一句话定义

> AspenOps 2.0 把 Aspen Plus / Aspen HYSYS 从有状态、会阻塞、版本敏感、许可证受限的桌面模拟器，封装为可被 Codex、Claude Code、MCP 客户端和 Python 工作流安全调用的确定性计算执行引擎。

```text
Agent 决定研究什么
Aspen 求解热力学与流程方程
AspenOps 决定操作是否允许、单位是否正确、运行是否收敛、结果是否物理可信、证据是否可复现
```

---

## 为什么普通 COM 脚本不够

最常见的 Aspen 自动化脚本只有：

```python
app = Dispatch("Apwn.Document.XX.0")
app.InitFromArchive2(case)
app.Tree.FindNode(path).Value = x
app.Engine.Run2()
```

这可以演示 COM，但没有解决工程自动化中的关键风险：

- Aspen 升级后 ProgID 变化；
- COM 对象不能安全跨线程或跨进程传递；
- `Run2()` 返回不等于流程收敛；
- Aspen 阻塞时普通 Python 线程无法可靠中止；
- 不同工况可能互相污染，热启动产生路径依赖；
- LLM 拼接任意 Tree Path 会造成误写与越权；
- 单位错误可能产生“数值正常、物理错误”的结果；
- 并行数超过许可证、内存或模型稳定上限后吞吐量反而下降；
- 模型、注册表、请求与结果没有内容哈希时无法追溯；
- 公共 CI 没有商业 Aspen 环境，容易出现“文档说能跑、实际不可证”的假象。

AspenOps 把这些风险变成明确的数据模型、状态机、边界检查、隔离策略和验证证据。

---

## 核心能力

### 确定性执行

- 每个 Worker 使用独立 Windows 子进程、独立 COM STA apartment 和私有模型副本；
- 一次工况通过一次 IPC 完成重置、批量写入、求解、批量读取和工程校验；
- 硬超时只终止 AspenOps 自己创建的 Worker，不执行全机范围的 `taskkill`；
- Worker 可按运行点数或寿命自动回收，控制长期 COM 泄漏；
- 对影响物理求解的请求进行规范化、去重和内容寻址缓存。

### 语义安全

- Agent 使用语义变量，不直接构造 Aspen Tree Path；
- 注册表声明读写权限、标识符、原生单位、物理量维度、上下界、整数约束和候选定位器；
- 标识符拒绝路径穿越、反斜线注入和模板式注入；
- HYSYS 默认通过项目拥有的 Spreadsheet Contract 暴露受控变量；
- MCP 不提供任意 Shell、Python、VBA、`eval`、通用 COM 方法或无限制 Tree Path 写入。

### 工程判定

AspenOps 不使用含糊的 `success=True`。一次结果只有同时满足以下条件才令 `ok=true`：

```text
communication_ok
AND engine_ok
AND converged
AND feasible
AND balances_passed
```

它分别记录：

- IPC 请求与响应关联是否完整；
- 求解器调用是否正常返回；
- 状态节点与错误信息是否支持收敛；
- 工艺约束的实际值、阈值、容差与违反量；
- 物料、能量或元素守恒的绝对与相对残差。

### 耐久任务与证据

- SQLite WAL 作业库；
- pending / running / completed / failed / cancelled / interrupted 状态；
- 任务租约、重试、取消、进度与最后完成点；
- 请求、结果、模型和语义注册表 SHA-256；
- 可验证运行 ZIP；
- 独立模型副本与独立 COM 实例重复认证；
- 真实持证运行的签名证据包与人工最终审核边界。

### DOE 与优化

- Latin Hypercube；
- bounded grid；
- nearest-neighbor 工况排序；
- 有界 `DE/best/1/bin` 差分进化；
- Deb-style feasibility ordering；
- 确定性随机种子；
- 预算、取消、失败惩罚、并发与许可证约束。

---

## 系统架构

```text
┌────────────────────────────────────────────────────────────────────┐
│ Codex / Claude Code / MCP Client / Python                          │
│ 只表达变量、DOE、约束、目标和结果需求；不接触原始 COM             │
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
│ Worker 0          Worker 1             Worker N                    │
│ private process   private process      private process             │
│ COM STA           COM STA              COM STA                     │
│ private case      private case         private case                │
└──────────────┬───────────────┬──────────────────────┬──────────────┘
               ▼               ▼                      ▼
          Aspen Plus      Aspen HYSYS            Mock backend
```

### 不可破坏的架构不变量

1. 一个 COM 对象只属于一个 Windows 子进程和一个 STA apartment。
2. Agent 只调用语义变量，不构造原始 Aspen Tree Path。
3. 每个 Worker 使用源模型的私有副本，不覆盖主模型。
4. 一次工况只进行一次批量 IPC 事务。
5. 超时只处理 AspenOps 自己创建的进程。
6. 通信、求解器返回、收敛、可行性和守恒闭合是五个独立状态。
7. Mock CI 只证明控制平面，不证明真实 Aspen 物理结果。
8. 真实持证运行仍须工程师审核物性方法、模型假设和资格案例。

---

## Aspen 版本兼容策略

AspenOps 不把某个 `Apwn.Document.N.0` 写死为“最新版本”。启动时会：

1. 优先采用操作员显式设置的 `ASPENOPS_PROGID` 或 `ASPENOPS_HYSYS_PROGID`；
2. 扫描 64 位与 32 位 Windows Registry View；
3. 枚举版本化 `Apwn.Document.*` 与 `HYSYS.Application.*`；
4. 解析数字版本并从新到旧排序；
5. 使用 `DispatchEx` 创建隔离 Automation Server；
6. 最后尝试无版本 ProgID；
7. 把实际成功的 ProgID、应用暴露版本和能力写入运行证据。

“能够发现并调用”不等于“已对该 Aspen 版本完成认证”。正式兼容性结论必须来自安装目标版本、有效许可证和获批资格案例的 Windows 主机。

---

## 快速开始：无需 Aspen

### 1. 安装

```bash
git clone https://github.com/SUNHAOJUN22/AspenOps-Agent.git
cd AspenOps-Agent
uv sync --extra dev --extra agent --extra signing
```

### 2. 运行 Mock 端到端示例

```bash
uv run aspenops demo
```

### 3. 运行便携式基准与重复性门

```bash
uv run aspenops benchmark --points 24 --workers 1,2,4
uv run aspenops certify examples/batch-request.example.json --repeats 3
```

### 4. 完整质量门

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -W error::ResourceWarning \
  --cov=aspenops_nexus \
  --cov-branch \
  --cov-report=term-missing \
  --cov-fail-under=94.5
uv build
uv run python scripts/check_mcp.py
```

---

## Windows + Aspen Plus / HYSYS

### 前置条件

- 原生 64 位 Windows；
- Python 3.11–3.13 与 `uv`；
- Aspen Plus 和/或 Aspen HYSYS；
- 有效许可证及明确许可证席位上限；
- 非保密、可稳定收敛的资格模型；
- 经 Variable Explorer 或 HYSYS Spreadsheet 核验的案例专用语义注册表；
- 位于允许根目录内的模型与结果目录。

### 安装与诊断

```powershell
git clone https://github.com/SUNHAOJUN22/AspenOps-Agent.git
cd AspenOps-Agent
powershell -ExecutionPolicy Bypass -File scripts/setup_windows.ps1
```

或手动执行：

```powershell
uv sync --extra windows --extra dev --extra agent --extra signing
Copy-Item .env.example .env
uv run aspenops doctor --probe
```

### 推荐配置

```text
ASPENOPS_BACKEND=aspen_plus
ASPENOPS_MODE=default
ASPENOPS_ALLOWED_ROOTS=D:/AspenModels;D:/AspenResults
ASPENOPS_LICENSE_SLOTS=1
ASPENOPS_MAX_WORKERS=1
ASPENOPS_TIMEOUT_S=1200
ASPENOPS_STARTUP_TIMEOUT_S=90
ASPENOPS_WORKER_MAX_POINTS=200
ASPENOPS_WORKER_MAX_AGE_S=14400
ASPENOPS_MAX_RESIDENT_CASES=2
ASPENOPS_POOL_IDLE_TIMEOUT_S=1800
ASPENOPS_CACHE_FAILURES=0
ASPENOPS_VISIBLE=0
```

首次真实运行建议保持一个 Worker，并按以下顺序执行：

```powershell
uv run aspenops doctor --probe
uv run aspenops dry-run D:/AspenModels/request.json
uv run aspenops run-batch D:/AspenModels/request.json `
  --output D:/AspenResults/results.json `
  --bundle D:/AspenResults/run-bundle.zip
uv run aspenops verify-bundle D:/AspenResults/run-bundle.zip
```

只有单点、约束、守恒和重复性全部稳定后，才增加并发。

---

## 标准请求结构

```json
{
  "backend": "aspen_plus",
  "model_path": "D:/AspenModels/case.bkp",
  "registry_path": "D:/AspenModels/case.registry.json",
  "workers": 2,
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
  "constraints": [
    {
      "name": "product_spec",
      "key": "stream.output.purity",
      "identifiers": {"stream": "PRODUCT"},
      "operator": ">=",
      "value": 0.995,
      "tolerance": 0.000001,
      "unit": "fraction"
    }
  ],
  "balances": [
    {
      "name": "overall_mass",
      "terms": [
        {
          "key": "feed.mass_flow",
          "identifiers": {"stream": "FEED"},
          "coefficient": 1.0,
          "unit": "kg/h"
        },
        {
          "key": "product.mass_flow",
          "identifiers": {"stream": "PRODUCT"},
          "coefficient": -1.0,
          "unit": "kg/h"
        }
      ],
      "abs_tol": 0.1,
      "rel_tol": 0.0001
    }
  ]
}
```

所有具体 Tree Path 或 HYSYS Spreadsheet 单元格都应保存在案例专用注册表内，不放进 Agent 请求。

---

## CLI 命令

| 命令 | 用途 |
|---|---|
| `aspenops demo` | 运行跨平台 Mock 端到端示例 |
| `aspenops doctor --probe` | 检查策略、环境和本机 Automation Server |
| `aspenops dry-run REQUEST` | 不打开 Aspen，验证请求、路径、单位和边界 |
| `aspenops run-batch REQUEST` | 同步执行批处理并生成证据包 |
| `aspenops submit REQUEST` | 提交耐久后台任务 |
| `aspenops job JOB_ID` | 查看任务状态与结果 |
| `aspenops benchmark` | 运行便携式 Worker 调度基准 |
| `aspenops optimize REQUEST` | 执行受预算约束的批量优化 |
| `aspenops certify REQUEST` | 运行重复性门；不会授予真实 Aspen 认证 |
| `aspenops certification-preflight PLAN` | 不打开 COM，验证持证认证计划 |
| `aspenops certify-licensed PLAN` | 在获批持证主机执行受控认证计划 |
| `aspenops verify-licensed-bundle BUNDLE` | 使用受信公钥验证签名认证包 |
| `aspenops verify-bundle BUNDLE` | 验证普通运行证据包 |
| `aspenops mcp` | 启动本地 STDIO MCP Server |

查看完整参数：

```bash
uv run aspenops --help
uv run aspenops <command> --help
```

---

## MCP / Codex / Claude Code

仓库包含：

- `.codex/config.toml`
- `.mcp.json`
- `CLAUDE.md`

启动或检查本地 MCP：

```powershell
uv run aspenops mcp
codex mcp list
claude mcp list
```

MCP 暴露 14 个窄接口工具：

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

推荐 Agent 执行链：

```text
system_info
→ list_semantic_variables
→ dry_run_request
→ submit_batch / submit_optimization
→ job_status / optimization_status
→ job_result / optimization_result
→ verify_evidence_bundle
```

推荐提示：

```text
只通过 AspenOps 操作 Aspen。先读取 system_info 和案例语义注册表，再 dry-run。
不得构造原始 Tree Path，不得覆盖源模型。仅把 communication_ok、engine_ok、
converged、feasible 和守恒判据全部通过的点纳入结果。返回失败点的违反量、
运行证据包路径，以及模型、注册表、请求和结果哈希。
```

---

## 性能设计

朴素逐点启动：

```text
T_naive ≈ N × (T_start + T_open + T_solve + T_read)
```

持久 CasePool：

```text
T_pool ≈ W × (T_start + T_open)
       + N_unique / W × (T_solve + T_verify)
       + T_IPC + T_schedule
```

真正的加速来自：

- Aspen 会话和模型不再逐点重启；
- 每个工况只进行一次批量 IPC；
- 调度前去重；
- 内容寻址缓存；
- 多个私有模型副本并行；
- 动态任务领取降低长尾；
- Worker 自动回收；
- 许可证、内存与稳定性共同限制有效并发。

```text
W_effective = min(W_configured, W_license, W_memory, W_stability)
```

不要把 Mock 调度基准描述为真实 Aspen 求解加速。真实吞吐量必须在目标模型、目标 Aspen 版本和实际许可证环境中测量。

---

## 证据包与认证层级

普通运行 ZIP 可包含：

```text
manifest.json
request.json
results.json
environment.json
README.txt
```

认证分为三个层级：

1. **控制平面认证**：Mock 后端验证隔离、IPC、调度、缓存、单位、约束、守恒、证据与重复性。
2. **持证模拟器运行时认证**：原生 Windows + Aspen + 有效许可证 + 获批资格案例，验证 COM、模型打开、语义变量、真实求解和重复数值行为。
3. **工程模型验证**：由流程工程师负责物性方法、组分、反应、设备假设、工况范围及与装置或实验数据的对应。

真实持证工作流：

```text
.github/workflows/licensed-aspen-certification.yml
```

它必须手工输入完整 40 位获批提交 SHA、认证计划路径、后端类型，并显式批准真实 COM 执行。运行时只能生成 `PENDING_REAL_ASPEN_CERTIFICATION` 证据，不能自行授予工程认证结论。

---

## 安全边界

不得提交：

- 客户 `.bkp`、`.apw`、`.apwz`、`.hsc`；
- 专有动力学、物性参数或生产 DCS 数据；
- Aspen 许可证文件或许可证服务器敏感信息；
- 账号、Token、内部路径、主机名或网络信息；
- 含商业工艺数据的运行证据包；
- 私钥或签名密钥。

生产环境应：

- 只开放最小允许根目录；
- 使用最小许可证席位与 Worker 上限；
- 将签名私钥放在仓库外；
- 使用非保密资格案例；
- 在增加并发前完成单点与重复性验证；
- 把模型工程审核与软件控制平面测试分开。

---

## 仓库结构

```text
src/aspenops_nexus/
  batch.py                  批处理验证与执行
  compat.py                 COM Server 运行时发现
  registry.py               语义变量、权限、单位、边界与防注入
  units.py                  工程单位代数
  worker.py                 spawn 进程、STA、协议关联与硬超时
  pool.py                   持久 CasePool、动态调度、回收与去重
  pool_manager.py           多案例池生命周期管理
  scheduler.py              SQLite WAL 耐久后台作业
  evaluation.py             五重状态、约束和守恒残差
  cache.py                  内容寻址结果缓存
  certification.py          独立重复性门
  licensed_certification.py 持证认证计划、签名包与验证
  provenance.py             普通运行完整性包
  optimization.py           受约束优化编排
  optimizer.py              差分进化与可行性排序
  design.py                 DOE 与工况排序
  mcp_server.py             14 工具窄接口 MCP Server
  backends/
    aspen_plus.py           Aspen Plus COM adapter
    hysys.py                HYSYS Spreadsheet adapter
    mock.py                 跨平台确定性测试后端

tests/                      单元、集成、故障边界和调度测试
examples/                   Mock、请求、注册表和认证计划示例
docs/                       架构、性能、质量、认证、安全和部署
scripts/                    安装、基准与接口核验脚本
.github/workflows/
  ci.yml
  windows-control-plane.yml
  generate-performance-evidence.yml
  licensed-aspen-certification.yml
```

---

## 常见问题

### `doctor --probe` 找不到 Aspen

检查：

- 是否使用原生 64 位 Windows；
- Aspen Automation Server 是否正确注册；
- `pywin32` 是否安装；
- 是否需要显式设置 `ASPENOPS_PROGID` 或 `ASPENOPS_HYSYS_PROGID`；
- Python 位数是否与 Aspen Automation Server 兼容。

### 请求被 allowed roots 拒绝

把模型、注册表、结果和证据包放在 `ASPENOPS_ALLOWED_ROOTS` 指定目录内。不要用关闭路径策略的方式绕过问题。

### `Run2()` 返回但 `ok=false`

查看 `converged`、约束违反量、守恒残差和 Aspen 错误节点。引擎返回只是五重门中的一层。

### 并发增加后反而更慢

降低 Worker 数，检查许可证等待、内存、模型打开时间、单点耗时分布和 Worker 老化阈值。并发不是越大越好。

### 公共 CI 通过，是否代表真实 Aspen 已认证

不代表。公共 CI 证明控制平面；真实 Aspen 需要 `licensed-aspen-certification.yml` 在持证自托管 Windows 主机上执行，并由工程师审核。

---

## 诚实边界与路线图

AspenOps 2.0 当前提供：

- Aspen Plus 稳态 COM 自动化控制平面；
- HYSYS 受控 Spreadsheet Bridge；
- CLI、Python 与本地 STDIO MCP；
- 后台批处理、缓存、并发、超时、验证、优化和证据；
- 真实持证认证计划、签名证据包和人工审核门。

它不宣称：

- 公共 Linux CI 已运行真实 Aspen；
- 任意 Aspen 版本、模块和模型无需资格测试即可兼容；
- `Run2()` 返回即代表热力学和工程结果正确；
- HYSYS 全对象模型已被统一封装；
- Aspen Dynamics、ACM、完整 PBE 或所有动态模型已被稳态后端覆盖；
- LLM 可以替代物性方法选择、反应机理、设备设计规范和工程审查。

后续优先级：

1. 在获批非保密模型上执行 Aspen Plus 与 HYSYS 持证认证；
2. 建立版本化资格案例与注册表证据；
3. 扩展模型级守恒、约束和不确定度模板；
4. 在真实许可证与硬件边界内形成可复现吞吐量基线；
5. 继续保持单一 `main` 主干和最小长期工作流集合。

---

## 许可证

代码采用 Apache-2.0。

Aspen Plus、Aspen HYSYS、模型文件、物性数据库、供应商文档和许可证受各自条款约束。AspenOps 不附带 Aspen 软件、许可证或专有模型。

<div align="center">

## Let agents design the experiment. Let Aspen solve the physics. Let AspenOps enforce the truth.

**AspenOps 2.0 — deterministic process simulation for the agentic era.**

</div>
