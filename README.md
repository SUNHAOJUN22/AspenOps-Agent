<div align="center">

# AspenOps 2.0

## Aspen Plus、Aspen HYSYS 与 AI Agent 之间的确定性执行控制平面

### Agent / CLI / Python → 语义工艺意图 → 隔离执行 → Aspen 求解 → 工程判定 → 可复现实验证据

**AspenOps 不是 GUI 宏，也不允许大模型任意调用 COM。**  
**它负责授权、路径、单位、收敛、约束、守恒、并发、审计和证据。**

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
| CI 覆盖率下限 | 94.5% |
| 已归档 Windows 公共门 | Actions run `29814739334`，104 passed，2.06 s |
| MCP 工具数 | 14 |
| 真实 Aspen 认证 | `PENDING_REAL_ASPEN_CERTIFICATION` |

以上是**已验证归档基线**，来自已检查的 JUnit、coverage JSON 和日志，**不是对任意后续提交的自动声明**。顶部徽章显示当前 `main` push 的平台状态；历史结果不会替代最新 Actions 证据。

公共 CI 可以证明控制平面、路径策略、进程隔离、调度、归档和接口契约，不能证明商业 Aspen、许可证、物性方法或工程模型已获得认证。

---

## 核心架构与有效性契约

```text
Agent / CLI / Python
        │ typed MCP / JSON
        ▼
AspenOps Control Plane
Policy · Registry · Units · Scheduler · Cache · Evidence · Audit
        │ one batched RPC per point
        ▼
Private Worker Process · COM STA · Private Model Copy
        │
        ├─ Aspen Plus
        ├─ Aspen HYSYS
        └─ Mock backend
```

不可破坏的不变量：

1. 一个 COM 对象只属于一个 Windows 子进程和一个 STA apartment。
2. Agent 只调用语义变量，不构造任意 Aspen Tree Path。
3. 每个 Worker 使用私有模型副本，不覆盖主模型。
4. 硬超时只终止 AspenOps 创建并验证归属的进程。
5. 通信、引擎返回、收敛、可行性和守恒闭合是独立状态。
6. Mock CI 只证明控制平面，不证明真实 Aspen 物理结果。

只有以下条件全部成立，结果才令 `ok=true`：

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

`.env.example` 默认使用 Mock、空允许根目录和仓库内状态目录，不会把 Windows 绝对路径强加给 Linux 或 macOS 首次运行。

---

## 本地完整质量门

```bash
uv lock --check
uv sync --frozen --extra dev --extra agent --extra signing
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
uv run aspenops --version
uv run aspenops demo
```

Windows 本地环境增加 `--extra windows`。

pytest 使用 strict markers、strict configuration、strict xfail，并把 `ResourceWarning` 作为错误。

---

## 四个权威自动工作流

| 工作流 | 触发方式 | 固定环境 | 职责 |
|---|---|---|---|
| `ci.yml` | `main` push、PR、手动 | `ubuntu-24.04`；Python 3.11/3.12/3.13 | 全量测试、覆盖率、Ruff、格式、mypy、六组合依赖审计、构建、Mock、MCP、Wheel、README 命令 |
| `windows-control-plane.yml` | `main` push、PR、手动 | `windows-2025`；Python 3.12 | Windows Job、进程归属、IPC、Fake Aspen/HYSYS、PowerShell helper、路径、文档和工作流治理 |
| `generate-performance-evidence.yml` | 手动 | `ubuntu-24.04`；Python 3.12 | 受信 `main` baseline/candidate、独立重复、稳定性能回归证据 |
| `licensed-aspen-certification.yml` | 受保护手动执行 | `self-hosted, windows, x64, aspen-licensed` | 受信 `main` SHA、Mock 回归、realpath、真实 COM、签名证据和人工审核 |

所有托管 runner、第三方 Actions 和 `uv 0.11.16` 均固定版本。所有工作流只授予 `contents: read`，自动测试拒绝任意 `*: write`、`write-all`、持久 checkout 凭据、`pull_request_target` 和静默 `continue-on-error`。

### 六组合冻结依赖审计

CI 对 Linux 与 Windows 分别审计 Python 3.11、3.12、3.13，共**六种**组合：

```text
linux  × 3.11 / 3.12 / 3.13
windows × 3.11 / 3.12 / 3.13
```

每种组合分别保存 JSON 和错误日志并校验 JSON。即使某一项失败，其余组合仍继续取证；完成全部证据收集后统一令质量任务失败。

### 锁定依赖 Wheel 验证

CI 从 `uv.lock` 导出带哈希的运行时依赖，用 `uv pip sync --require-hashes` 创建干净环境，再以 `--offline --no-deps` 安装构建的 Wheel，执行 `uv pip check` 和关键 CLI smoke；不会现场重新解析依赖版本。

### 文档与操作契约

`tests/test_documentation_contracts.py` 从 `pyproject.toml` 动态读取版本，并检查：

- README 徽章、包版本、`__version__`、CHANGELOG 和 AspenOps 标题一致；
- README、AGENTS、CLAUDE、CONTRIBUTING、Security、Architecture、Performance、Windows、质量、测试审计和认证文档存在；
- 本地 Markdown 链接可解析且不得逃出仓库；
- AGENTS/CONTRIBUTING 必须使用冻结质量门；
- `.env.example` 保持可移植 Mock 首次运行；
- 归档证据与真实认证边界不得被删除。

---

## 受信性能证据

`generate-performance-evidence.yml` 在安装工具或运行 Python 前完成：

```text
checkout candidate
→ 获取受信 main 历史
→ 解析 candidate 与 baseline 完整 SHA
→ 两者都必须属于 main
→ baseline 必须是 candidate 的祖先
→ 创建 baseline detached worktree
→ 冻结安装 candidate 依赖
→ 运行独立重复与稳定回归策略
```

未合并、无关或反向时间顺序的提交不能生成看似权威的性能证据。Mock 结果仅表示编排性能，不代表真实 Aspen 求解速度。

---

## Windows + Aspen Plus / HYSYS

```powershell
git clone https://github.com/SUNHAOJUN22/AspenOps-Agent.git
cd AspenOps-Agent
powershell -ExecutionPolicy Bypass -File scripts/setup_windows.ps1
```

脚本会安全安装或升级 `uv >= 0.11.16`，保留当前 PATH，冻结安装 `windows + agent + dev + signing`，严格加载 `.env`，拒绝重复变量和未闭合引号，错误只报告行号且不回显潜在密钥，并使用真实加载配置运行 `doctor --probe`。

真实后端必须配置非空绝对 `ASPENOPS_ALLOWED_ROOTS`；状态、模型、注册表、结果和证据目录必须解析到允许根目录内。realpath 检查拒绝 `..`、符号链接和 Windows 联接点逃逸。

---

## 持证 Aspen 认证

```text
精确获批 SHA checkout
→ 验证 SHA 属于受信 main
→ 冻结依赖与隔离 Mock 回归
→ 计划、根目录和状态目录 realpath 验证
→ preflight
→ 明确人工批准
→ 范围受限的真实 COM 执行
→ 签名包验证
→ 验证全部证据存在且非空
→ 复制到 var/ci/licensed-evidence
→ 仅上传工作区 var/ci
→ 工程师最终审核
```

早期失败时，上传动作不会解析未定义的外部状态目录；只有工作区内诊断可进入制品。成功时，preflight、认证报告和签名包先复制到工作区暂存目录后再上传。

软件只能生成 `PENDING_REAL_ASPEN_CERTIFICATION`。签名证明来源与完整性，不等于物性、反应、设备假设或工程适用范围已被批准。

---

## CLI 与 MCP

主要 CLI：`demo`、`doctor`、`dry-run`、`run-batch`、`submit`、`job`、`benchmark`、`optimize`、`certify`、`certification-preflight`、`certify-licensed`、`verify-licensed-bundle`、`verify-bundle`、`mcp`。

MCP 精确暴露 14 个窄接口工具，不提供任意 Shell、Python、VBA、`eval`、无限制 COM 方法或原始 Tree Path 写入。

---

## 自动测试明确不证明什么

公共自动化不证明：

- 任意商业 Aspen 版本都能启动或任意模型都能收敛；
- 物性、反应和设备假设工程上正确；
- Mock 性能等于真实 Aspen 性能；
- 软件可以替代流程工程师或自行授予真实工程认证。

代码采用 Apache-2.0。不得提交客户模型、专有物性/动力学、生产 DCS 数据、许可证文件、私钥、Token、内部主机或含商业数据的证据包。
