<div align="center">

# AspenOps 2.0

## Aspen Plus、Aspen HYSYS 与 AI Agent 之间的确定性执行控制平面

### Codex / Claude Code / MCP → 语义工艺意图 → 隔离执行 → Aspen 求解 → 工程判定 → 可复现实验证据

**AspenOps 不是 GUI 宏，也不是让大模型直接调用任意 COM。**  
**它负责授权、路径、单位、收敛、约束、守恒、并发、审计和证据。**

[English](README.en.md) · [Architecture](docs/architecture.md) · [Windows Setup](docs/windows-setup.md) · [Performance](docs/performance.md) · [Certification](docs/certification.md) · [Test Audit](docs/automated-test-audit-2026-07-22.md) · [Quality Report](docs/quality-report.md) · [Security](SECURITY.md)

[![CI main push](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/ci.yml/badge.svg?branch=main&event=push)](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/ci.yml?query=branch%3Amain+event%3Apush)
[![Windows main push](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/windows-control-plane.yml/badge.svg?branch=main&event=push)](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/windows-control-plane.yml?query=branch%3Amain+event%3Apush)
![Python](https://img.shields.io/badge/Python-3.11--3.13-3776AB)
![Version](https://img.shields.io/badge/version-2.0.0-111827)
![License](https://img.shields.io/badge/license-Apache--2.0-0F766E)

</div>

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
| CI 覆盖率下限 | 94.5% |
| 已归档 Windows 公共门 | Actions run `29814739334`，104 passed，2.06 s |
| MCP 工具数 | 14 |
| 真实 Aspen 认证 | `PENDING_REAL_ASPEN_CERTIFICATION` |

以上是**已验证归档基线**，来自已检查的 JUnit、coverage JSON 和日志，**不是对任意后续提交的自动声明**。顶部徽章显示当前 `main` push 的平台状态；README 不用历史结果替代最新 Actions 证据。

公共 CI 可以证明控制平面、路径策略、进程隔离、调度、归档和接口契约，不能证明某台主机上的商业 Aspen、许可证、物性方法或工程模型已经获得认证。

---

## 一句话定义

> AspenOps 把有状态、会阻塞、版本敏感、许可证受限的 Aspen 桌面模拟器，封装成 Agent、CLI 和 Python 工作流可安全调用的确定性执行引擎。

```text
Agent 决定研究什么
Aspen 求解热力学和流程方程
AspenOps 判断操作是否允许、单位是否正确、求解是否收敛、结果是否可行、守恒是否闭合、证据是否可复现
```

---

## 核心架构

```text
┌────────────────────────────────────────────────────────────────────┐
│ Codex / Claude Code / MCP Client / Python                          │
│ 变量、DOE、约束、目标和结果需求；不接触原始 COM                    │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ typed MCP / CLI / JSON
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│ AspenOps Control Plane                                             │
│ Policy · Registry · Units · Scheduler · Cache · Evidence · Audit   │
│ Certification · Optimization                                      │
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

不可破坏的不变量：

1. 一个 COM 对象只属于一个 Windows 子进程和一个 STA apartment。
2. Agent 只调用语义变量，不构造任意 Aspen Tree Path。
3. 每个 Worker 使用私有模型副本，不覆盖主模型。
4. 每个工况只进行一次批量 IPC 事务。
5. 硬超时只终止 AspenOps 创建并验证归属的进程。
6. 通信、引擎返回、收敛、可行性和守恒闭合是独立状态。
7. Mock CI 只证明控制平面，不证明真实 Aspen 物理结果。
8. 持证结果仍须流程工程师审核。

只有以下状态全部成立，结果才令 `ok=true`：

```text
communication_ok
AND engine_ok
AND converged
AND feasible
AND balances_passed
```

---

## 快速开始：无需 Aspen

要求：Python 3.11–3.13 与 `uv >= 0.11.16`。

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

`.env.example` 的首次运行默认值为 Mock 后端、空允许根目录和仓库内状态目录，因此复制后不会把 Windows 专用绝对路径强加给 Linux 或 macOS 用户。

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

UV_PREVIEW_FEATURES=json-output uv audit --frozen \
  --python-platform linux --python-version 3.11 --output-format json
UV_PREVIEW_FEATURES=json-output uv audit --frozen \
  --python-platform windows --python-version 3.11 --output-format json

uv build
uv run python scripts/check_mcp.py
uv run aspenops --version
uv run aspenops --help
uv run aspenops demo
```

CI 会自动扩展漏洞审计：Linux 与 Windows 两个平台分别检查 Python 3.11、3.12、3.13，共**六种**受支持组合，并验证每份输出是合法 JSON。

pytest 策略：pytest 8.3+、strict markers、strict configuration、strict xfail，并把 `ResourceWarning` 作为错误。

---

## 四个权威自动工作流

| 工作流 | 触发方式 | 固定环境 | 职责 |
|---|---|---|---|
| `ci.yml` | `main` push、PR、手动 | `ubuntu-24.04`；Python 3.11/3.12/3.13 | 全量测试、覆盖率、Ruff、格式、mypy、六组合依赖审计、构建、Mock、MCP、Wheel、README 命令 |
| `windows-control-plane.yml` | `main` push、PR、手动 | `windows-2025`；Python 3.12 | Windows Job、进程归属、IPC、调度、归档、Fake Aspen/HYSYS、PowerShell AST、路径、文档与工作流治理 |
| `generate-performance-evidence.yml` | 手动 | `ubuntu-24.04`；Python 3.12 | 不可变 baseline、独立重复、稳定性能回归策略 |
| `licensed-aspen-certification.yml` | 受保护手动执行 | `self-hosted, windows, x64, aspen-licensed` | 受信 `main` SHA、Mock 回归、realpath 门、preflight、真实 COM、签名证据和人工审核 |

所有托管 runner、第三方 Actions 和 `uv 0.11.16` 都固定版本。依赖安装先执行 `uv lock --check`，随后使用 `uv sync --frozen`。

### 自动治理规则

自动测试会拒绝：

- 未固定完整 commit SHA 的第三方 Action；
- `ubuntu-latest` 或 `windows-latest` 等漂移 runner 标签；
- `contents: write`、持久 checkout 凭据、`pull_request_target`；
- 静默 `continue-on-error`；
- 非冻结依赖安装；
- 缺少 `set -euo pipefail` 的 Bash 步骤；
- 在 `run: |`、`run: >`、单行 `run:` 或简写 `- run:` 中直接插入手动输入；
- 原始 baseline ref 直接进入 worktree；
- 用户输入进入制品名称；
- 文档中的旧工具版本、旧 runner、旧工作流名称或失效本地链接；
- Windows 或持证门删除关键路径、后端和文档契约测试。

### 锁定依赖 Wheel 验证

便携式 CI 从 `uv.lock` 导出带哈希的运行时依赖，使用 `uv pip sync --require-hashes` 创建干净环境，再用 `--offline --no-deps` 安装构建的 Wheel，执行 `uv pip check` 和关键 CLI smoke。Wheel 验证不会现场重新解析依赖版本。

### 文档契约

`tests/test_documentation_contracts.py` 自动检查：

- 中英文 README、Windows 指南、质量报告、测试审计和认证文档均存在；
- 本地 Markdown 链接可解析且不得逃出仓库；
- `uv 0.11.16`、`ubuntu-24.04`、`windows-2025` 和四个工作流名称保持一致；
- 不得重新出现旧工作流或漂移 runner；
- README 必须明确六种依赖审计组合；
- `.env.example` 必须保持可移植 Mock 首次运行；
- 归档证据与真实认证边界不得被删除。

---

## Windows + Aspen Plus / HYSYS

### 前置条件

- 原生 64 位 Windows；
- Python 3.11–3.13；
- `uv >= 0.11.16`；
- Aspen Plus 和/或 Aspen HYSYS；
- 有效许可证和明确席位上限；
- 非保密、在 GUI 中稳定收敛的资格模型；
- 经核验的案例语义注册表；
- 非空、绝对、已存在的允许根目录；
- 位于允许根目录内的绝对状态、模型、注册表、结果和证据目录。

真实后端缺少 `ASPENOPS_ALLOWED_ROOTS`，或状态目录位于根目录之外时，会在 `Settings` 构造阶段直接失败，不进入 Aspen preflight，也不创建状态文件。

### 推荐安装

```powershell
git clone https://github.com/SUNHAOJUN22/AspenOps-Agent.git
cd AspenOps-Agent
powershell -ExecutionPolicy Bypass -File scripts/setup_windows.ps1
```

脚本会：

1. 开启严格 PowerShell 行为；
2. 在缺少 `uv` 时通过 winget 安装；
3. 在 `uv` 低于 0.11.16 时通过 winget 自动升级；
4. 刷新机器和用户 PATH，同时保留当前进程 PATH；
5. 校验锁文件并冻结安装 `windows + agent + dev + signing`；
6. 创建、验证并加载 `.env`；
7. 拒绝重复变量和未闭合引号；
8. `.env` 错误只报告行号，不回显潜在密钥内容；
9. 使用加载后的配置运行 `doctor --probe`；
10. 检查所有外部命令退出码。

首次真实模型：

```powershell
uv run aspenops dry-run D:/AspenModels/request.json
uv run aspenops run-batch D:/AspenModels/request.json `
  --output D:/AspenResults/results.json `
  --bundle D:/AspenResults/run-bundle.zip
uv run aspenops verify-bundle D:/AspenResults/run-bundle.zip
```

从一个 Worker 和一个已知收敛点开始。约束、守恒、重复性、内存和许可证行为稳定后再增加并发。

---

## 真实后端路径策略

同一套规则覆盖环境加载、直接 Python 构造、批处理请求、CLI 输出和持证认证：

- 真实后端必须配置非空 `ASPENOPS_ALLOWED_ROOTS`；
- 根目录和状态目录必须显式为绝对路径；
- 状态目录必须解析到某个允许根目录内；
- 请求后端必须与配置的真实后端一致；
- 模型、注册表、结果、普通证据包和持证输出必须位于根目录内；
- realpath 检查拒绝 `..`、符号链接和 Windows 联接点逃逸；
- 不安全配置在打开 Aspen 前失败。

---

## 持证 Aspen 认证

权威工作流：`licensed-aspen-certification.yml`。

```text
精确获批 SHA checkout
→ 验证 SHA 属于受信 main 历史
→ 锁文件检查与冻结依赖
→ 不接触真实密钥的 Mock 软件回归
→ 计划、允许根目录和状态目录 realpath 验证
→ 持证 preflight
→ 明确人工执行批准
→ 范围受限的真实 COM 执行
→ 签名证据包验证
→ 工程师最终审核
```

软件只能生成 `PENDING_REAL_ASPEN_CERTIFICATION`。签名证明来源与完整性，不等于物性、反应、设备假设或工程适用范围已被批准。

---

## CLI 与 MCP

主要 CLI：

| 命令 | 用途 |
|---|---|
| `aspenops demo` | Mock 端到端演示 |
| `aspenops doctor --probe` | 主机、策略和 Automation Server 诊断 |
| `aspenops dry-run REQUEST` | 不打开 Aspen，验证路径、语义、单位和并发 |
| `aspenops run-batch REQUEST` | 执行批处理并生成完整性包 |
| `aspenops submit REQUEST` | 提交耐久后台任务 |
| `aspenops job JOB_ID` | 查看任务状态和结果 |
| `aspenops benchmark` | 便携式调度基准 |
| `aspenops optimize REQUEST` | 有预算约束的优化 |
| `aspenops certify REQUEST` | 重复性门，不授予真实认证 |
| `aspenops certification-preflight PLAN` | 不打开 COM，检查持证计划 |
| `aspenops certify-licensed PLAN` | 在获批持证主机执行计划 |
| `aspenops verify-licensed-bundle BUNDLE` | 验证签名认证包 |
| `aspenops verify-bundle BUNDLE` | 验证普通运行包 |
| `aspenops mcp` | 启动本地 STDIO MCP Server |

MCP 精确暴露 14 个窄接口工具：

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

不存在任意 Shell、Python、VBA、`eval`、无限制 COM 方法或原始 Tree Path 写入工具。

---

## 覆盖率策略

归档综合覆盖率只比 94.5% 门槛高约 0.47 个百分点。后续优先补测：

```text
scheduler.py
pool.py
worker.py
provenance.py
batch.py
convergence.py
```

在复杂边界补齐前，不为漂亮数字盲目提高全局门槛。

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

## 安全与许可证

不得提交客户模型、专有物性或动力学、生产 DCS 数据、许可证文件、私钥、Token、内部主机、私有路径或含商业数据的证据包。

代码采用 Apache-2.0。Aspen 产品、模型、数据库、供应商文档和许可证受各自条款约束；AspenOps 不附带 Aspen 软件、许可证或专有模型。

<div align="center">

## Let agents design the experiment. Let Aspen solve the physics. Let AspenOps enforce the truth.

</div>
