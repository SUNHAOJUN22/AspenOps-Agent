<div align="center">

# AspenOps 2.0

## Aspen Plus、Aspen HYSYS 与 AI Agent 之间的确定性执行控制平面

**Agent / CLI / Python → 语义工艺意图 → 隔离执行 → Aspen 求解 → 工程判定 → 可复现实验证据**

[English](README.en.md) · [Architecture](docs/architecture.md) · [Windows Setup](docs/windows-setup.md) · [Performance](docs/performance.md) · [Certification](docs/certification.md) · [Test Audit](docs/automated-test-audit-2026-07-22.md) · [Quality Report](docs/quality-report.md) · [Security](SECURITY.md) · [Contributing](CONTRIBUTING.md)

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
| 覆盖率门槛 | 94.5% |
| 已归档 Windows 公共门 | Actions run `29814739334`，104 passed，2.06 s |
| MCP 工具数 | 14 |
| 真实 Aspen 认证 | `PENDING_REAL_ASPEN_CERTIFICATION` |

以上是**已验证归档基线**，来自已检查的 JUnit、coverage JSON 和日志，**不是对任意后续提交的自动声明**。顶部徽章反映当前 `main` push 状态；历史数字不会替代最新 Actions 证据。

公共 CI 证明控制平面、路径策略、进程隔离、调度、归档和接口契约，不证明商业 Aspen、许可证、物性方法或工程模型已完成认证。

---

## 核心不变量

1. 一个 COM 对象只属于一个 Windows 子进程和一个 STA apartment。
2. Agent 只使用语义变量，不构造任意 Aspen Tree Path。
3. 每个 Worker 使用私有模型副本，不覆盖主模型。
4. 硬超时只终止 AspenOps 创建并核验归属的进程。
5. 通信、引擎返回、收敛、可行性和守恒闭合分别判定。
6. Mock CI 不冒充真实 Aspen 物理认证。

只有以下条件全部成立，结果才为 `ok=true`：

```text
communication_ok
AND engine_ok
AND converged
AND feasible
AND balances_passed
```

---

## 快速开始与本地质量门

要求：Python 3.11–3.13，`uv >= 0.11.16`。

```bash
git clone https://github.com/SUNHAOJUN22/AspenOps-Agent.git
cd AspenOps-Agent
uv lock --check
uv sync --frozen --extra dev --extra agent --extra signing
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -W error::ResourceWarning \
  --cov=aspenops_nexus --cov-branch --cov-fail-under=94.5
uv build
uv run python scripts/check_mcp.py
uv run aspenops demo
uv run aspenops dry-run examples/batch-request.example.json
```

Windows 增加 `--extra windows`。`.env.example` 默认使用 Mock、空允许根目录和仓库内状态目录，因此首次运行保持跨平台。

---

## 四个权威工作流

| 工作流 | 固定环境 | 作用 |
|---|---|---|
| `ci.yml` | `ubuntu-24.04`；Python 3.11/3.12/3.13 | 全量测试、覆盖率、Ruff、mypy、六组合依赖审计、构建、Wheel、Mock、MCP、README 命令 |
| `windows-control-plane.yml` | `windows-2025`；Python 3.12 | Windows Job、IPC、Fake Aspen/HYSYS、PowerShell helper、路径、文档和治理契约 |
| `generate-performance-evidence.yml` | `ubuntu-24.04`；Python 3.12 | 非主干显式失败、受信比较、双冻结环境、独立重复和稳定回归证据 |
| `licensed-aspen-certification.yml` | `ubuntu-24.04` guard → 持证 Windows | 非主干显式失败、调度 SHA 绑定、全局串行、按运行尝试隔离证据和真实 COM |

所有托管 runner、第三方 Actions 和 `uv 0.11.16` 固定版本。工作流仅授予 `contents: read`；治理测试拒绝任意 `*: write`、`write-all`、持久 checkout 凭据、`pull_request_target` 和静默 `continue-on-error`。

### 六组合冻结依赖审计

```text
Linux 与 Windows × Python 3.11、3.12、3.13
```

每种组合保存 JSON 和 stderr 日志并校验 JSON。某项失败不会阻止其余取证；全部完成后统一失败。

### 锁定依赖 Wheel

运行时依赖从 `uv.lock` 导出并带哈希，使用 `uv pip sync --require-hashes` 创建干净环境，再以 `--offline --no-deps` 安装 Wheel，执行 `uv pip check` 和关键 CLI smoke，不在验证时重新解析版本。

---

## 受信、隔离且无旧文件污染的性能证据

性能任务第一步检查事件 ref。若不是 `refs/heads/main`，任务会写入 `dispatch-ref.txt` 和 `dispatch-guard.log`，再以退出码 2 **显式失败**，不会显示成 skipped。

默认 baseline：

```text
ebef32ee1f2be74df5d5c5489e7ca86d35ac7bb2
```

```text
显式验证 GITHUB_REF == refs/heads/main
→ actions/checkout 当前受信 main 工作流版本
→ 用 --end-of-options 解析 candidate_ref / baseline_ref
→ 两个 SHA 都必须属于 main
→ baseline 必须是 candidate 的祖先
→ detached checkout 已验证 candidate SHA
→ 创建 baseline detached worktree
```

手动 candidate 输入不会直接进入 `actions/checkout`。两个提交分别使用自己的 `uv.lock`、`.venv` 和 benchmark 脚本。所有本次运行日志、JSON 和报告只写入 `$RUNNER_TEMP/aspenops-performance-evidence`；上传 action 通过 `${{ runner.temp }}` 读取该目录，不接触候选工作区中已提交的旧 `var/benchmarks` 文件。

Mock 性能只表示编排性能，不代表真实 Aspen 求解速度。

---

## Windows 与真实后端

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_windows.ps1
```

脚本会安全安装或升级 `uv >= 0.11.16`，保留当前 PATH，冻结安装 `windows + agent + dev + signing`，严格加载 `.env`，拒绝重复变量和未闭合引号，错误只报告行号且不回显潜在密钥，并运行 `doctor --probe`。

真实后端必须配置非空绝对 `ASPENOPS_ALLOWED_ROOTS`；状态、模型、注册表、结果和证据路径必须解析到允许根目录内。realpath 检查拒绝 `..`、符号链接和 Windows 联接点逃逸。

---

## 持证 Aspen 认证

持证工作流先在固定 `ubuntu-24.04` guard job 上检查 `GITHUB_REF`。非主干调度明确失败，且不会占用 `self-hosted, windows, x64, aspen-licensed` 主机。

`expected_head_sha` 必须等于本次 `refs/heads/main` 调度的 `GITHUB_SHA`。工作流先核对初始 checkout 已经是该 SHA，再验证其仍属于可信 `origin/main`，随后以同一 SHA detached checkout。由此，工作流定义、运行代码、测试与 `validate_licensed_paths.py` 均来自同一提交；不能选择早期 main 祖先退回旧安全实现。

所有真实认证运行使用统一 concurrency group `licensed-aspen-certification`。外部证据目录按运行尝试隔离：

```text
ASPENOPS_STATE_DIR/licensed-certification/<GITHUB_RUN_ID>-<GITHUB_RUN_ATTEMPT>
```

该目录每次运行先删除再重建，并通过 `LICENSED_EVIDENCE_DIR` 贯穿 preflight、真实执行、签名验证、报告检查和工作区暂存。重跑不会复用上一次 report/bundle，Aspen Plus 与 HYSYS 也不会共享固定目录。上传制品名称包含 `github.run_id` 和 `github.run_attempt`。

```text
Ubuntu guard 验证 GITHUB_REF == refs/heads/main
→ actions/checkout 本次主干 GITHUB_SHA
→ 验证 expected_head_sha == GITHUB_SHA
→ 核对初始 HEAD 与主干祖先关系
→ detached checkout 同一 GITHUB_SHA
→ 清理 var/ci 并执行隔离 Mock 回归
→ 建立 run_id-run_attempt 独立外部目录
→ realpath → preflight → 人工批准 → 真实 COM
→ 签名包验证 → 全部证据非空检查
→ 清理并暂存至 var/ci/licensed-evidence
→ 仅上传工作区 var/ci → 工程师审核
```

软件只能生成 `PENDING_REAL_ASPEN_CERTIFICATION`，签名不等于工程模型已获批准。

---

## 文档、CLI 与 MCP 契约

`tests/test_documentation_contracts.py` 从 `pyproject.toml` 动态读取版本，核对 README、`__version__`、CHANGELOG、AGENTS、CLAUDE、CONTRIBUTING 和核心文档；本地链接不得逃出仓库，操作指南必须使用冻结质量门，聊天内部引用或 `sandbox:/` 标记不得进入仓库 Markdown。

主要 CLI：`demo`、`doctor`、`dry-run`、`run-batch`、`submit`、`job`、`benchmark`、`optimize`、`certify`、`certification-preflight`、`certify-licensed`、`verify-licensed-bundle`、`verify-bundle`、`mcp`。

MCP 精确暴露 14 个窄接口工具，不提供任意 Shell、Python、VBA、`eval`、无限制 COM 方法或原始 Tree Path 写入。

---

## 自动测试不证明什么

自动化不证明任意 Aspen 版本都能启动、任意模型都收敛、物性/反应/设备假设工程上正确，也不能替代流程工程师或自行授予真实认证。

代码采用 Apache-2.0。不得提交客户模型、专有物性/动力学、生产 DCS 数据、许可证、私钥、Token、内部主机或商业证据包。
