<div align="center">

# AspenOps 2.0

## 面向 Aspen Plus / Aspen HYSYS 与 AI Agent 的确定性工程控制平面

**受控需求 → 强类型过程意图 → 工程规则 → 可验证编译 → 隔离执行 → 工程判定 → 可审计证据 → 确定性交付**

[English](README.en.md) · [最终验收](README_ACCEPTANCE.md) · [Architecture](docs/architecture.md) · [Delivery Acceptance](docs/delivery-acceptance.md) · [Delivery Bundle](docs/delivery-bundle.md) · [Windows Setup](docs/windows-setup.md) · [Certification](docs/certification.md) · [Quality Report](docs/quality-report.md)

![version-2.0.0-delivery](https://img.shields.io/badge/version-2.0.0-111827)
![Python](https://img.shields.io/badge/Python-3.11--3.13-3776AB)
![Platforms](https://img.shields.io/badge/platforms-Windows%20%7C%20Linux-2563EB)
![License](https://img.shields.io/badge/license-Apache--2.0-0F766E)

</div>

![AspenOps 最终验收架构](docs/assets/acceptance/final-acceptance-map.svg)

> **资格边界：** `aspenops-nexus 2.0.0` 可以对控制面、过程意图、隔离运行、缓存、调度、优化、证据链和确定性交付进行软件资格验证；没有真实商业求解器、许可证、固定模型、Golden Case、硬件指纹、工程容差和签名审查时，不得自授真实 Aspen 工程资格。真实环境状态保持 `PENDING_REAL_ASPEN_CERTIFICATION`。

## 验收状态

| 项目 | 当前交付合同 |
|---|---|
| 权威长期分支 | `main` |
| 支持平台 | Linux 与 Windows；真实 Aspen COM 仅限许可 Windows 主机 |
| Python | Python 3.11、3.12、3.13；六种 Linux/Windows 组合进入软件验证 |
| 历史归档资格 | `1224 passed`，0 failed，95.03% branch coverage |
| 当前运行时回归 | 1247+ tests，95.03% branch coverage；以最新 `main` CI 为准 |
| 包与锁 | `uv 0.11.16`，`uv lock --check`，`mcp>=1.9,<2` |
| 外部求解器资格 | `PENDING_REAL_ASPEN_CERTIFICATION` |

这里记录的是**已验证归档基线**，不是对任意后续提交的自动声明。当前树必须由永久、只读工作流重新验证；历史 PASS 不能覆盖新代码的失败。

## AI 辅助视觉系统

以下二十三幅仓库内 SVG 严格解释真实代码合同，不依赖外部图床。它们是 AI-assisted 概念信息图，不是流程模拟数据、Golden Case、实验结果或商业软件执行证明。

| 架构与过程意图 | 执行与安全 | 证据与工程 |
|---|---|---|
| ![hero architecture](docs/assets/readme/hero-architecture.svg) | ![agent pipeline](docs/assets/readme/agent-pipeline.svg) | ![process intent](docs/assets/readme/process-intent-ir.svg) |
| ![backend capabilities](docs/assets/readme/backend-capabilities.svg) | ![adapter conformance](docs/assets/readme/adapter-conformance.svg) | ![COM isolation](docs/assets/readme/com-isolation.svg) |
| ![worker recycle](docs/assets/readme/worker-ownership-recycle.svg) | ![validity gates](docs/assets/readme/validity-gates.svg) | ![optimization lifecycle](docs/assets/readme/optimization-lifecycle.svg) |
| ![scheduler lifecycle](docs/assets/readme/scheduler-lifecycle.svg) | ![durable paths](docs/assets/readme/durable-path-portability.svg) | ![cache singleflight](docs/assets/readme/cache-singleflight.svg) |
| ![evidence chain](docs/assets/readme/evidence-chain.svg) | ![evidence integrity](docs/assets/readme/evidence-integrity.svg) | ![licensed certification](docs/assets/readme/licensed-certification.svg) |
| ![CLI MCP workflow](docs/assets/readme/cli-mcp-workflow.svg) | ![MCP lifecycle](docs/assets/readme/mcp-runtime-lifecycle.svg) | ![path safety](docs/assets/readme/policy-path-safety.svg) |
| ![performance hotspot](docs/assets/readme/performance-hotspot-map.svg) | ![cold warm startup](docs/assets/readme/cold-warm-startup.svg) | ![test matrix](docs/assets/readme/test-matrix.svg) |
| ![industrial scenarios](docs/assets/readme/industrial-scenarios.svg) | ![roadmap](docs/assets/readme/roadmap.svg) |  |

## 系统定位

AspenOps 不是“让大模型随意生成 COM/VBA/Python 去操作 Aspen”的脚本包装器。它把人或 Agent 的意图收敛为可验证的数据合同：

```text
Human / Agent
  → ProcessRequirementDocument
  → ProcessDesignIR / aspenops.flowsheet/v1
  → engineering rules + units + degrees of freedom
  → simulator capability profile
  → compilation / evaluation plan
  → CasePool / scheduler / optimizer
  → isolated Windows Worker + owned COM session
  → Aspen Plus / HYSYS / Mock
  → readback + convergence + constraints + balances
  → evidence bundle + deterministic handover
```

DWSIM 与 IDAES 处于 `planned` 路线，当前**未实现**生产 adapter。`aspenops.flowsheet/v1` 明确报告不可用能力，不能把“了解某软件名称”伪装成可执行适配器。

## 数学与工程合同

### 1. 组分物料衡算

对组分 \(i\)：

\[
\frac{dN_i}{dt}=\sum_{s\in\mathcal I}\dot n_{i,s}
-\sum_{s\in\mathcal O}\dot n_{i,s}
+\sum_{r\in\mathcal R}\nu_{i,r}r_rV.
\]

稳态残差：

\[
R_i=\sum_s\dot n_{i,s}^{in}-\sum_s\dot n_{i,s}^{out}
+\sum_r\nu_{ir}r_rV,
\qquad |R_i|\le\tau_i.
\]

非有限衡算形成 `balance_non_finite`；有限但超限形成 `balance_failed`。退出码 0、COM 返回或缓存命中都不能替代衡算门。

### 2. 能量衡算

\[
\frac{dU}{dt}=\dot Q-\dot W
+\sum_{s\in\mathcal I}\dot n_s\hat h_s
-\sum_{s\in\mathcal O}\dot n_s\hat h_s.
\]

实际工程仍需批准焓基准、相平衡、反应热、热损失、轴功和设备模型。

### 3. 多层有效性门

\[
OK=C_{comm}\land C_{engine}\land C_{conv}\land C_{finite}
\land C_{constraint}\land C_{balance}.
\]

约束违背度：

\[
V(x)=\sum_j\max(0,g_j(x)-\varepsilon_j)
+\sum_k\max(0,|h_k(x)|-\varepsilon_k).
\]

`NaN`、`Infinity`、字符串伪数值和 Boolean 数值别名 fail closed；约束中的非有限值使用 `constraint_non_finite`。证据 JSON 固定 `allow_nan=False`。

### 4. 单位与仿射换算

\[
x_t=(x_s+a_s)\frac{m_s}{m_t}-a_t,
\qquad T_K>0.
\]

参数同时检查有限性、物理维度、整数性、分数范围和正值范围。

### 5. 回流图与撕裂边

对有向图 \(G=(V,E)\) 和撕裂边集合 \(T\)：

\[
\forall C\in cycles(G),\qquad C\cap T\neq\varnothing.
\]

撕裂边必须属于实际循环；声明“存在 recycle”不能压制无关拓扑错误。

### 6. 精馏自由度

\[
DOF=N_c-N_s.
\]

\(N_c\) 为独立可操纵变量数，\(N_s\) 为独立规范数。能力 profile 与工程规则必须一致，避免欠规定或过度规定。

### 7. 缓存身份

\[
K=SHA256(schema\Vert version\Vert backend\Vert runtime
\Vert model\Vert registry\Vert request_{physical}).
\]

展示 metadata 不改变物理身份；模型、registry、backend、runtime 或校验语义变化必须改变缓存键。

### 8. Warm-start 轨迹

\[
x_{k+1}=F(x_k,u_k),\qquad y_k=G(x_k).
\]

Warm-start 是路径依赖计算，因此同一轨迹只由一个 Worker 顺序执行；禁止 persistent cache、same-batch dedup 和 `inflight_singleflight`；session/step 进入身份；优化默认采用 `reset_mode='reinitialize'`。

### 9. 约束优化

\[
\min_x J(x)=\sum_{m=1}^{M}w_m f_m(x),
\qquad J_p(x)=J(x)+\lambda V(x),\quad\lambda\ge0.
\]

先验证可行性、收敛和工程门，再比较目标值。高罚系数不能掩盖求解失败或非有限输出。

### 10. 许可证与有效并发

\[
W_{effective}=\min(W_{configured},W_{license},W_{memory},W_{stable}).
\]

池化时间模型：

\[
T_{pool}\approx W(T_{start}+T_{open})+
\frac{N_{unique}}{W_{effective}}(T_{solve}+T_{verify})+T_{IPC}.
\]

更多进程不必然更快；Windows spawn、商业许可证、内存、回流收敛和模型稳定性共同限制并发。

## 配置边界

永久质量工作流使用 `ubuntu-24.04`，Windows 控制面和真实 COM 预检使用 `windows-2025`。Python 3.11、3.12、3.13 在 Linux 与 Windows 形成六种软件审计组合。真实 Aspen Plus/HYSYS 仍要求许可 Windows 主机。

```bash
git clone https://github.com/SUNHAOJUN22/AspenOps-Agent.git
cd AspenOps-Agent
uv lock --check
uv sync --frozen --extra dev --extra agent --extra signing
```

固定工具链为 `uv 0.11.16`；MCP 运行时边界为 `mcp>=1.9,<2`。

## 配置与路径安全策略

`.env.example` 默认使用 Mock。真实模型、registry、state 和输出路径必须位于显式 allowed roots；持久请求在提交时固定 `paths_pinned` 和 `submission_cwd`，防止调度器工作目录变化后重新解释相对路径。重复 JSON key、非有限数值、越界路径和不平衡配置均 fail closed。

## 原生适配器一致性门

原生适配器必须通过 manifest、输入/输出 Schema、单位、failure isolation 和确定性对照。适配器 PASS 只证明软件接口，不证明客户模型或工程结论。

```bash
uv run aspenops doctor --probe
uv run python scripts/validate_process_ir.py examples/process-intent.example.json
```

生成的 `process-ir-dashboard.html` 是合同可视化，不是模拟结果。

## 快速开始

```bash
uv run aspenops demo
uv run aspenops dry-run examples/request.example.json
uv run aspenops run-batch examples/request.example.json --output var/results.json --bundle var/run-bundle.zip
uv run aspenops verify-bundle var/run-bundle.zip
```

## 独立有效性门

每个点必须分别记录 communication、engine、convergence、finite、constraint 和 balance 状态。任何门失败都不能被平均分数或求解器“成功”覆盖。

## 典型工作流

```bash
uv run aspenops submit examples/request.example.json
JOB_ID=$(uv run aspenops submit examples/request.example.json | python -c "import json,sys; print(json.load(sys.stdin)['job_id'])")
uv run aspenops job "$JOB_ID"
uv run aspenops cancel "$JOB_ID" --grace-s 2
uv run aspenops scheduler
uv run aspenops optimize examples/optimization-request.example.json
```

## MCP 兼容性与服务生命周期

```bash
uv run aspenops mcp
```

MCP lifespan 拥有 scheduler 的启动、关闭和异常回收；MCP 面不公开真实 Aspen 认证，也不绕过显式执行权限。

## 约束优化闭环

优化器按预算生成批次，保存原子 checkpoint、可行性排序和 Pareto archive。求解失败、非有限目标或工程门失败不能被“最佳目标值”覆盖。

## 调度与恢复

持久状态包括 `retry_wait` 与 `dead_letter`。租约、心跳、取消截止、worker crash、幂等提交和恢复均有事务边界；warm-start 轨迹保持单 Worker 串行。

## 缓存、批内去重与单航班

相同不可变请求可使用 same-batch dedup、持久缓存和 `inflight_singleflight`。缓存身份绑定 runtime、model、registry 与物理请求；失败默认不缓存，返回对象保持深度隔离。

## Worker 所有权与回收

每个 Windows Worker 独占 COM 会话、私有模型副本和 job scope。point budget、age、timeout、protocol error、tainted state 或 cancellation deadline 会触发可验证回收。

## 性能工程与证据

```bash
uv run python scripts/measure_cli_startup.py --output var/ci/cli-startup.json
uv run python scripts/measure_operation_counts.py --output var/ci/operation-counts.json
uv run python scripts/measure_job_store_queries.py --output var/ci/job-store-query-plan.json
uv run python scripts/render_test_dashboard.py --input-dir var/ci --output-html var/ci/test-dashboard.html --output-svg var/ci/test-dashboard.svg
```

治理工件为 `cli-startup.json`、`operation-counts.json`、`job-store-query-plan.json`；解释规则见 Performance Audit V2。当前运行证据只写入 `RUNNER_TEMP`/`${{ runner.temp }}`，artifact 名包含 `github.run_id` 与 `github.run_attempt`，避免早期失败发布旧文件。

## 工业应用场景

软件支持批量参数扫描、受约束优化、牌号切换、故障复算和受控数字孪生交接；它不替代流程工程师、HAZOP/LOPA/SIL、许可证、客户模型批准或现场授权。

## 证据包完整性与真实性

永久工作流为 `ci.yml`、`windows-control-plane.yml`、`generate-performance-evidence.yml` 和 `licensed-aspen-certification.yml`。手动证据生产只接受 `refs/heads/main`；dispatch guard 在 `actions/checkout` 前检查 ref，不满足时**显式失败**并返回 status 2，而不是产生 all-skipped 假绿。候选和基线随后在 `detached` worktree 中验证。

许可认证环境要求 `expected_head_sha == GITHUB_SHA`，并记录 `GITHUB_RUN_ID`、`GITHUB_RUN_ATTEMPT`、`LICENSED_EVIDENCE_DIR`、`run-metadata.txt`、`job_status` 和 `aspenops-licensed-artifact`。上传使用 `if-no-files-found: error`，目录位于 `runner.temp`，真实 Aspen 任务保持串行。没有新许可运行和签名证据时，状态仍为 `PENDING_REAL_ASPEN_CERTIFICATION`。

## 项目结构

- `src/aspenops_nexus/`：控制面、过程 IR、调度、缓存、优化、证据与 adapter；
- `tests/`：数值、并发、文件安全、文档、artifact 与工作流合同；
- `scripts/`：审计、性能、dashboard、Process IR 和交付包；
- `.github/workflows/`：四个永久只读/受控工作流；
- `docs/assets/readme/`：二十三幅确定性 SVG。

## 故障排查

先运行 `uv run aspenops doctor --probe`，再检查 allowed roots、registry SHA、模型身份、许可证、worker generation、state database 和 evidence bundle。禁止通过关闭测试、降低容差或把非收敛重解释为成功来消除错误。

## 最终验收命令

```bash
python scripts/final_acceptance_preflight.py --root . --json
uv lock --check
uv sync --frozen --extra dev --extra agent --extra signing
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run python -m compileall -q src scripts
uv run python scripts/audit_source_tree.py
uv run pytest -W error::ResourceWarning --cov=aspenops_nexus --cov-branch --cov-fail-under=95.0
uv build
```

## License

Apache-2.0 仅覆盖本仓库。Aspen Plus、Aspen HYSYS、Windows、许可证服务、客户模型和工艺数据分别受其许可、保密和安全制度约束。
