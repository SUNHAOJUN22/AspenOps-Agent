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

这些数字来自已下载并检查的 JUnit、coverage JSON 和日志，是**已验证归档基线**，不是对任意后续提交的自动声明。顶部徽章只显示 `main` 最新 `push` 状态。

当前 `main` 还强制：

- 真实后端缺少 `ASPENOPS_ALLOWED_ROOTS` 时，环境加载和直接 `Settings(...)` 构造均立即失败；
- 状态、模型、注册表、CLI 输出和证据目录必须位于解析后的允许根目录内；
- 持证路径使用 realpath，拒绝 `..`、符号链接和联接点逃逸；
- 持证提交必须属于受信 `main` 历史；
- 真实密钥不暴露给依赖安装或 Mock 回归；
- Windows 公共门与持证回归门都运行直接构造、后端升级、CLI 输出和 realpath 测试；
- CI 使用 `uv audit` 对 Python 3.12 的 Linux 与 Windows 锁定依赖进行漏洞审计，并保存 JSON 证据。

公共 CI 验证控制平面，不冒充 Aspen Plus 或 HYSYS 的真实物理模型认证。

---

## 一句话定义

> AspenOps 把有状态、会阻塞、版本敏感、许可证受限的 Aspen 桌面模拟器，封装为可被 Agent、CLI 和 Python 工作流安全调用的确定性执行引擎。

```text
Agent 决定研究什么
Aspen 求解热力学和流程方程
AspenOps 决定操作是否允许、单位是否正确、运行是否收敛、结果是否可行、守恒是否闭合、证据是否可复现
```

---

## 架构与不变量

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

不可破坏的规则：

1. 一个 COM 对象只属于一个 Windows 子进程和一个 STA apartment。
2. Agent 只调用语义变量，不构造原始 Aspen Tree Path。
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

uv audit --frozen --python-platform linux --python-version 3.12
uv audit --frozen --python-platform windows --python-version 3.12
uv build
uv run python scripts/check_mcp.py
uv run aspenops --version
uv run aspenops --help
uv run aspenops demo
```

pytest 策略：pytest 8.3+、strict markers、strict configuration、strict xfail，并把 `ResourceWarning` 作为错误。

---

## 自动测试与长期工作流

仓库只保留四个权威工作流：

| 工作流 | 触发方式 | 固定环境 | 职责 |
|---|---|---|---|
| `ci.yml` | `main` push、PR、手动 | `ubuntu-24.04`；Python 3.11/3.12/3.13 | 全量测试、覆盖率、Ruff、格式、mypy、锁文件漏洞审计、构建、Mock、MCP、锁定依赖 Wheel、README 命令 |
| `windows-control-plane.yml` | `main` push、PR、手动 | `windows-2025`；Python 3.12 | Windows Job、进程归属、IPC、调度、归档、Fake Aspen/HYSYS、PowerShell AST、路径与工作流治理 |
| `generate-performance-evidence.yml` | 手动 | `ubuntu-24.04`；Python 3.12 | 不可变 baseline、独立重复、稳定性能回归策略 |
| `licensed-aspen-certification.yml` | 受保护手动执行 | `self-hosted, windows, x64, aspen-licensed` | `main` 祖先 SHA、realpath 门、Mock 回归、preflight、真实 COM、签名证据、人工审核 |

所有托管 runner、第三方 Actions 和 `uv` 都固定版本。当前工作流和 Windows 安装脚本要求 **uv 0.11.16**；该版本包含 CI 使用的 `uv audit --output-format json` 能力。依赖安装始终检查 `uv.lock` 并使用 `--frozen`。

### 工作流治理规则

自动测试强制：

- 第三方 Actions 固定到完整 40 位 commit SHA；
- `uv` 固定为 `0.11.16`，JSON 漏洞审计不得回退到不支持该能力的版本；
- `contents: read`，checkout 不保留写凭据；
- 禁止 `pull_request_target`、`contents: write` 和静默 `continue-on-error`；
- 所有 Bash 步骤使用 `set -euo pipefail`；
- 所有 `run: |`、`run: >`、单行 `run:` 和简写 `- run:` 都接受输入注入扫描；
- 手动输入不直接插入 Shell/PowerShell 命令；
- 性能 baseline 先解析为完整提交 SHA，再创建 worktree；
- 制品名称使用 `github.run_id`；
- 持证提交必须是受信 `main` 的祖先；
- Python realpath 门阻止符号链接、联接点和路径穿越；
- 真实密钥不进入依赖安装或 Mock 回归；
- Windows CI 使用 PowerShell AST 解析安装脚本；
- Windows 公共门和持证回归门必须运行直接 Settings、后端策略和 realpath 测试。

### 锁定依赖 Wheel 验证

CI 从 `uv.lock` 导出带哈希的运行时依赖，使用 `uv pip sync --require-hashes` 建立干净环境，再以 `--offline --no-deps` 安装 Wheel，执行 `uv pip check` 和关键 CLI smoke。不会在 Wheel 验证时临时重新解析依赖。

### 覆盖率策略

归档覆盖率只比门槛高约 0.47 个百分点。后续优先补测 `scheduler.py`、`pool.py`、`worker.py`、`provenance.py`、`batch.py` 和 `convergence.py`，不为漂亮数字盲目提高门槛。

---

## Windows + Aspen Plus / HYSYS

前置条件：

- 原生 64 位 Windows；
- Python 3.11–3.13；
- `uv >= 0.11.16`；
- Aspen Plus 和/或 Aspen HYSYS；
- 有效许可证与明确席位上限；
- 非保密、在 GUI 中稳定收敛的资格模型；
- 经核验的案例语义注册表；
- 非空、绝对、已存在的允许根目录；
- 位于允许根目录内的绝对状态、模型、注册表、结果和证据目录。

真实后端缺少根目录或状态目录越界时，会在 `Settings` 构造阶段直接失败，不会进入 preflight 或创建状态文件。

```powershell
git clone https://github.com/SUNHAOJUN22/AspenOps-Agent.git
cd AspenOps-Agent
powershell -ExecutionPolicy Bypass -File scripts/setup_windows.ps1
```

脚本会安装或校验 `uv >= 0.11.16`，保留当前进程 PATH，检查锁文件，冻结安装 `windows + agent + dev + signing`，创建并加载 `.env`，随后用真实加载的配置运行 `doctor --probe`。

首次真实模型：

```powershell
uv run aspenops dry-run D:/AspenModels/request.json
uv run aspenops run-batch D:/AspenModels/request.json `
  --output D:/AspenResults/results.json `
  --bundle D:/AspenResults/run-bundle.zip
uv run aspenops verify-bundle D:/AspenResults/run-bundle.zip
```

从一个 Worker 和一个已知收敛点开始，约束、守恒、重复性、内存和许可证行为稳定后再增加并发。

---

## CLI 与 MCP

主要 CLI：`demo`、`doctor`、`dry-run`、`run-batch`、`submit`、`job`、`benchmark`、`optimize`、`certify`、`certification-preflight`、`certify-licensed`、`verify-licensed-bundle`、`verify-bundle`、`mcp`。

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

不提供任意 Shell、Python、VBA、`eval`、通用 COM 方法或无限制 Tree Path 写入。

---

## 性能与认证边界

```text
T_naive ≈ N × (T_start + T_open + T_solve + T_read)
T_pool ≈ W × (T_start + T_open)
       + N_unique / W × (T_solve + T_verify)
       + T_IPC + T_schedule
W_effective = min(W_configured, W_license, W_memory, W_stability)
```

Mock 基准不得描述为真实 Aspen 求解性能。

三级认证：

1. **控制平面认证**：Mock 验证软件隔离、调度、单位、约束、守恒和证据。
2. **持证模拟器运行时认证**：原生 Windows + Aspen + 有效许可证 + 获批案例。
3. **工程模型验证**：工程师审核物性、反应、设备、工况和实际数据对应。

持证顺序：

```text
精确获批 SHA 且属于受信 main 历史
→ 冻结依赖
→ 无真实密钥的 Mock 软件回归
→ realpath 与符号链接逃逸检查
→ preflight
→ 明确人工批准
→ 真实 COM 执行
→ 签名包验证
→ 工程师最终审核
```

运行时只能生成 `PENDING_REAL_ASPEN_CERTIFICATION`，不能自行授予工程认证。

---

## 安全与数据边界

不得提交客户 Aspen 案例、专有动力学或物性数据、生产 DCS 数据、许可证材料、凭据、内部主机信息、机密证据包或签名私钥。生产环境使用最小允许根目录、许可证席位和 Worker 上限。

## 许可证

代码采用 Apache-2.0。Aspen 产品、模型、数据库、供应商文档和许可证受各自条款约束。AspenOps 不附带 Aspen 软件、许可证或专有模型。
