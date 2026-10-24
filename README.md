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

<!-- CLOSURE_STATUS_START -->
## 当前代码资格与工程边界

- 多目标优化在标量化前使用显式单位、物理维度、参考值与正参考尺度；改变 kW/W 等表示不会改变物理解排序。
- 规范 JSON/SHA-256 只由 `aspenops_nexus.hashing.canonical_hash` 实现，过程需求、编译计划、拓扑、适配器与许可链接共用同一摘要合同。
- Mock/离线资格只验证控制面软件；没有已授权商业求解器、许可证、固定模型与签名工程审查时，真实执行状态保持 `PENDING_REAL_ASPEN_CERTIFICATION`。
- README 中的流程图和公式是代码合同说明，不是 Aspen Plus/HYSYS 求解结果或装置性能保证。
<!-- CLOSURE_STATUS_END -->

<!-- LOCALIZED_VISION_ZH:START -->
## 中文项目愿景图：从过程意图到工业装置证据闭环

<p align="center">
  <img src="docs/assets/vision-zh.png" width="100%" alt="AspenOps 中文工艺与科学计算愿景图">
</p>

> 图中公式和模块来自当前代码合同；它展示的是控制平面愿景，不是 Aspen Plus/HYSYS 求解结果、装置数据或工程认证。

<!-- LOCALIZED_VISION_ZH:END -->

![最终验收架构](docs/assets/acceptance/final-acceptance-map.svg)

> **资格边界：** `aspenops-nexus 2.0.0` 对控制面、过程意图、隔离执行、缓存、调度、优化、证据链和确定性交付进行软件资格验证。没有真实商业求解器、许可证、固定模型、Golden Case、硬件指纹、工程容差和签名审查时，不得自授 Aspen 工程资格；状态保持 `PENDING_REAL_ASPEN_CERTIFICATION`。

## 验收状态

| 项目 | 当前合同 |
|---|---|
| 权威长期分支 | `main` |
| 支持平台 | Linux 与 Windows；真实 Aspen COM 仅限许可 Windows 主机 |
| Python | Python 3.11、3.12、3.13；六种 Linux/Windows 软件组合 |
| 归档资格 | `docs/quality-report.md` 中的已验证归档基线仅供历史对照，不是对任意后续提交的自动声明 |
| 当前回归 | 必须核对目标提交的完整 CI、覆盖率与原始 JUnit；本行不继承归档数字 |
| 工具链 | `uv 0.11.16`；`mcp>=1.30.0,<2` |
| 外部资格 | `PENDING_REAL_ASPEN_CERTIFICATION` |

这是**已验证归档基线**，不是对任意后续提交的自动声明。历史 PASS 不能覆盖新代码失败。

## AI 辅助视觉系统

以下二十三幅仓库内 SVG 解释真实软件合同，不是流程模拟、Golden Case、实验数据或商业软件执行证据。

| 架构与意图 | 执行与安全 | 证据与工程 |
|---|---|---|
| ![hero](docs/assets/readme/hero-architecture.svg) | ![agent](docs/assets/readme/agent-pipeline.svg) | ![intent](docs/assets/readme/process-intent-ir.svg) |
| ![backend](docs/assets/readme/backend-capabilities.svg) | ![adapter](docs/assets/readme/adapter-conformance.svg) | ![COM](docs/assets/readme/com-isolation.svg) |
| ![worker](docs/assets/readme/worker-ownership-recycle.svg) | ![validity](docs/assets/readme/validity-gates.svg) | ![optimization](docs/assets/readme/optimization-lifecycle.svg) |
| ![scheduler](docs/assets/readme/scheduler-lifecycle.svg) | ![paths](docs/assets/readme/durable-path-portability.svg) | ![cache](docs/assets/readme/cache-singleflight.svg) |
| ![chain](docs/assets/readme/evidence-chain.svg) | ![integrity](docs/assets/readme/evidence-integrity.svg) | ![licensed](docs/assets/readme/licensed-certification.svg) |
| ![CLI](docs/assets/readme/cli-mcp-workflow.svg) | ![MCP](docs/assets/readme/mcp-runtime-lifecycle.svg) | ![policy](docs/assets/readme/policy-path-safety.svg) |
| ![hotspot](docs/assets/readme/performance-hotspot-map.svg) | ![startup](docs/assets/readme/cold-warm-startup.svg) | ![matrix](docs/assets/readme/test-matrix.svg) |
| ![industrial](docs/assets/readme/industrial-scenarios.svg) | ![roadmap](docs/assets/readme/roadmap.svg) |  |

交付、数学、原生隔离和 warm-start 的补充视觉：

![delivery acceptance](docs/assets/ai/delivery-acceptance.svg)
![mathematical contracts](docs/assets/ai/mathematical-contracts.svg)
![native failure isolation](docs/assets/ai/native-failure-isolation.svg)
![warm-start trajectory](docs/assets/ai/warm-start-trajectory.svg)

## 系统定位

```text
Human / Agent
  → ProcessRequirementDocument
  → ProcessDesignIR / aspenops.flowsheet/v2
  → engineering rules + units + DOF
  → capability profile + compilation plan
  → CasePool / scheduler / optimizer
  → isolated Windows Worker + owned COM session
  → Aspen Plus / HYSYS / Mock
  → readback + convergence + constraints + balances
  → evidence bundle + deterministic handover
```

`ProcessIntent` 使用 `aspenops.flowsheet/v1`，对应 `scripts/validate_process_ir.py` 的示例入口；`ProcessDesignIR` 使用 `aspenops.flowsheet/v2`，通过 `validate_process_design` 执行工程规则。两者具有各自的数据合同，提交时应使用对应的 schema。

DWSIM 与 IDAES 处于 `planned` 路线，当前**未实现**生产 adapter。能力未知或无 adapter 时必须显式报告，不能把“知道软件名称”伪装成可执行能力。

## 数学与工程合同

以下公式描述代码实际执行的检查；动态守恒方程是设置模型与残差的物理依据。AspenOps 不在 Python 内重写 Aspen 热力学或反应求解器。每次使用都应保存模型版本、单位、参数来源、适用范围和工程容差。

### 1. 单位先于数值比较

设源单位和目标单位到规范单位的比例与偏移分别为 $(s_s,b_s)$ 和 $(s_t,b_t)$，则

$$
x_t=\frac{s_s x_s+b_s-b_t}{s_t},\qquad T_K>0.
$$

`units.convert` 检查支持单位与有限数。偏移相同的换算先合成 $s_s/s_t$，避免规范单位的中间值溢出或下溢；若非零比例换算的最终结果下溢为零，则显式抛出 `UnitError`。同单位和等价别名保持可表示的小量；$273.15\,\mathrm K\to0\,{}^\circ\mathrm C$ 等合法仿射零点仍然有效。`evaluation_plan` 在读、写、约束编译时绑定注册表的源单位；未知源单位不能被请求中的 `K` 或 `bar` 标签变成物理证据。无单位的文本/布尔状态可保留；无量纲数值使用显式 `1`、`fraction` 等。比例先归一化为 $[0,1]$：$50\%=0.5=500000\,\mathrm{ppm}$。温度先转 K；物理参数缺少单位产生阻断，计数只能使用 `1` 或未标单位，不能用百分数冒充级数。

JSON 文件的数值解析也属于这个边界。设 $x$ 为文件中的十进制数、$\operatorname{fl}(x)$ 为解析后的浮点值，则：

$$
\neg\operatorname{isfinite}(\operatorname{fl}(x))
\;\lor\;
\bigl(x\ne0\;\land\;\operatorname{fl}(x)=0\bigr)
\quad\Longrightarrow\quad\text{拒绝输入}.
$$

请求、批量执行文件、注册表、设计/过程 IR、研究文档、许可计划及证据读取会拒绝 `1e999` 等溢出，以及 `1e-400` 等非零数下溢为零；批量文件与其他请求入口采用同一重复键检查，后出现的键不能覆盖先前的科学输入。`0e-9999`、带符号的真正零和可表示的 `5e-324` 仍然有效；JSON 整数在解析时保留整数类型。损坏缓存中的下溢数值按缓存失效处理，不会当作成功结果复用。遇到拒绝时，应检查原始数据和单位量级并重新导出文件；不能把非零观测手动改为零以通过验收。此保证针对原始 JSON 文件；已经由调用方舍入成零的 Python 浮点数无法恢复其原始十进制值。实现与公开入口回归：[JSON 输入](src/aspenops_nexus/json_input.py) · [边界测试](tests/test_json_numeric_boundaries.py)。

源码：[单位](src/aspenops_nexus/units.py)、[读写计划](src/aspenops_nexus/evaluation_plan.py)、[工程规则](src/aspenops_nexus/engineering_rules.py)。

### 2. 反应的元素、电荷和质量守恒

令 $A_{ei}$ 为组分 $i$ 中元素 $e$ 的原子数，$\nu_i$ 为反应计量系数（反应物负、产物正），$z_i$ 为显式离子电荷，$M_i$ 为声明分子量：

$$
A\boldsymbol{\nu}=\boldsymbol 0,\qquad
\sum_i z_i\nu_i=0,\qquad
\sum_i M_i\nu_i=0.
$$

最后一项只在全部分子量可用时检查。对每一种元素、电荷或声明质量，令相应贡献为 $c_i=a_i\nu_i$，采用相对贡献尺度：

$$
R=\sum_i c_i,\qquad S=\sum_i|c_i|,\qquad
|R|\le\tau S,\qquad
\tau=\begin{cases}10^{-10}&\text{元素或电荷},\\10^{-6}&\text{声明质量}.\end{cases}
$$

$S=0$ 表示该量的所有贡献均为零。代码对已接纳的有限浮点输入使用精确有理数完成乘积与求和，不设人为的绝对容差下限；整体缩放保持可表示的计量比例时，守恒判定不变。这样既保留非零次正规量，也避免大系数的中间溢出；质量容差仍允许声明分子量的舍入。支持 `Ca(OH)2`、`CuSO4·5H2O`、`Na+`、`Fe^3+` 等有界分子式。未定义组成、伪组分、聚合物通配符或不支持的语法返回 `ENGINEERING_BLOCKER`，不虚构组成。例：$2H_2+O_2\to2H_2O$ 满足守恒，$H_2+O_2\to H_2O$ 不满足；把后一反应的所有系数乘以 $10^{-12}$ 仍然不满足。完整反应检查在 `validate_process_design` 路径执行。

### 3. 流程衡算与独立有效性门

动态模型的物理关系为

$$
\frac{dN_i}{dt}=\sum_{\rm in}\dot n_i-\sum_{\rm out}\dot n_i+
\sum_r\nu_{ir}r_rV,
\qquad
\frac{dU}{dt}=\dot Q-\dot W+\sum_{\rm in}\dot n\hat h-\sum_{\rm out}\dot n\hat h.
$$

运行时读取用户声明的衡算项，先换算至同维单位，再检查线性残差 $R=\sum_jc_jy_j$ 及配置的绝对/相对容差。系数、单位、符号和实际可得项必须与模型一致；缺失项不能用零填补。

$$
OK=C_{\rm communication}\land C_{\rm engine}\land C_{\rm convergence}
\land C_{\rm finite}\land C_{\rm constraint}\land C_{\rm balance}.
$$

`constraint_non_finite` / `balance_non_finite` 区别于有限但超差的失败；证据 JSON 使用 `allow_nan=False`。任何单门失败都不能被其他分数抵消。源码：[实际评估](src/aspenops_nexus/evaluation.py)。

### 4. 有量纲目标的规范化与可行性排序

每一目标的实际输出 $y_j$ 首先由 `result.units` 转到目标单位，再使用参考值 $r_j$ 和正尺度 $a_j$：

$$
\widetilde f_j(x)=\sigma_j\frac{y_j(x)-r_j}{a_j},\quad
J(x)=\sum_jw_j\widetilde f_j(x),\quad w_j>0,
\qquad \sigma_j=\begin{cases}+1&\text{minimize}\\-1&\text{maximize}.\end{cases}
$$

例如 $r=100\,\mathrm{kW},a=50\,\mathrm{kW}$ 时，$125\,\mathrm{kW}$ 与 $125000\,\mathrm W$ 均给出 $0.5$。缺单位、不同量纲、非有限或缺失输出使候选不可行；不会进入可行 Pareto 集。单目标可使用其原始标度，多目标要求完整的无量纲规范化合同。代码采用 Deb 可行性排序：可行优于不可行；两个可行候选比较目标，两个不可行候选比较违约量，而非未经声明的固定惩罚系数。

$$
x\prec y\iff\left(\forall j:f_j(x)\le f_j(y)\right)\land
\left(\exists j:f_j(x)<f_j(y)\right).
$$

等价目标不互相支配；公共 Pareto 接口拒绝非有限数、空目标、负违约量和维度不一致。源码：[优化评估](src/aspenops_nexus/optimization.py)、[DE/Pareto](src/aspenops_nexus/optimizer.py)。

### 5. 采样、拓扑、状态与计算预算

LHS 在每维 $n$ 个等宽层内各抽取一点并独立置乱；网格点数为 $N=\prod_d L_d$。生成前检查有限正区间、正整数层数，以及 $N\le100000$、$Nd\le10^6$ 和 $d\le256$。最近邻排序额外限制 5000 点，防止二次复杂度拖垮交互任务。随机种子固定可复现；增加样本数不代表模型验证。

$$
x_{kd}=\ell_d+\frac{\pi_d(k)+u_{kd}}{n}(u_d-\ell_d),\quad u_{kd}\in[0,1),
\qquad \forall C\in\operatorname{cycles}(G),\ C\cap T\ne\varnothing.
$$

循环必须有属于该循环的撕裂边；设备规范与自由度检查在构建前阻断缺失定义。Warm-start 是 $x_{k+1}=F(x_k,u_k)$ 的有状态轨迹，必须单 Worker、串行执行。冷启动可受限并发并复用持久缓存，但缓存命中只返回独立历史结果，不会把状态写入当前 Worker；关闭、替换或预算回收丢失状态后，同轨迹 warm 请求会在写入/求解前以 `warm_start_state_lost` 拒绝，只有当前池当前 Worker 实际执行、通信和引擎状态成功且收敛的 `reinitialize` 才能恢复延续。Mock 回归验证不代表真实 Aspen 已验收。源码：[采样](src/aspenops_nexus/design.py)、[流程规则](src/aspenops_nexus/engineering_rules.py)、[Worker 状态合同](docs/architecture.md)。

### 6. 证据摘要与测试计数

$$
K=\operatorname{SHA256}(\operatorname{canonicalJSON}(\text{schema, runtime, model, registry, physical request})),
\qquad N_{\rm pass}=N_{\rm total}-N_{\rm fail}-N_{\rm error}-N_{\rm skip}.
$$

摘要校验字节身份，签名校验指定信任根下的真实性；两者均不能证明模型适用性。JUnit 计数必须是非负整数，失败/错误/跳过之和不大于总数，耗时有限非负；父套件与子套件/用例不能矛盾或重复累计。损坏证据报错，不再默认为零失败。回归：[生产入口反例](tests/test_acceptance_repair.py)。

## 配置边界

永久质量工作流使用 `ubuntu-24.04`，Windows 控制面与真实 COM 预检使用 `windows-2025`。Python 3.11、3.12、3.13 在 Linux 与 Windows 形成六种组合。

```bash
git clone https://github.com/SUNHAOJUN22/AspenOps-Agent.git
cd AspenOps-Agent
uv lock --check
uv sync --frozen --extra dev --extra agent --extra signing
```

## 配置与路径安全策略

`.env.example` 默认 Mock。真实 model、registry、state 与 output 必须位于 allowed roots。持久请求固定 `paths_pinned` 和 `submission_cwd`；重复 JSON key、非有限数值、越界路径和不平衡配置 fail closed。

## 原生适配器一致性门

原生 adapter 必须通过 manifest、输入/输出 Schema、单位、failure isolation 与确定性对照。

```bash
uv run aspenops doctor --probe
uv run python scripts/validate_process_ir.py examples/process-intent.example.json
```

`process-ir-dashboard.html` 是合同图，不是模拟结果。

## 快速开始

```bash
uv run aspenops demo
uv run aspenops dry-run examples/request.example.json
uv run aspenops run-batch examples/request.example.json --output var/results.json --bundle var/run-bundle.zip
uv run aspenops verify-bundle var/run-bundle.zip
```

`run-batch` 在解析 JSON 前将文件输入限制为 `ASPENOPS_MAX_REQUEST_BYTES`（默认 10,000,000 字节），并拒绝非普通文件；解析后仍会校验规范化请求大小。内存中的 Python 请求继续由同一请求大小门校验。

## 独立有效性门

每个点分别记录 communication、engine、convergence、finite、constraint 和 balance 状态。任何门失败都不能被求解器“成功”或平均分数覆盖。

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

MCP lifespan 拥有 scheduler 启停和异常回收，不公开真实 Aspen 认证，也不绕过显式执行权限。

## 约束优化闭环

优化器保存 evaluation budget、原子 checkpoint、Deb-style feasibility 排序与 Pareto archive；求解失败和非有限目标不能被最佳分数覆盖。

## 调度与恢复

持久状态包括 `retry_wait` 与 `dead_letter`。租约、心跳、取消截止、worker crash、幂等提交和恢复均有事务边界。

## 缓存、批内去重与单航班

相同不可变冷启动请求可使用 same-batch dedup、持久缓存和 `inflight_singleflight`。缓存命中可作为该请求的独立结果，但不会执行参数写入或恢复新 Worker 的模拟器状态；warm-start 延续只使用当前 Worker 的实时状态。失败默认不缓存，返回对象保持深度隔离。

## Worker 所有权与回收

每个 Windows Worker 独占 COM session、私有模型副本与 job scope。point budget、age、timeout、protocol error、tainted state 或 cancellation deadline 触发回收。

## 原生失败隔离

原生/商业 backend 的进程、COM apartment、临时模型、Windows Job Object 和日志边界必须隔离；一个 Worker 的 timeout、protocol error 或 crash 不得污染其他 Worker。失败后先终止所属进程树、记录 violation 与 generation，再创建替代 Worker；禁止在未知状态的同一 COM 实例上继续计算。

## 性能工程与证据

```bash
uv run python scripts/measure_cli_startup.py --output var/ci/cli-startup.json
uv run python scripts/measure_operation_counts.py --output var/ci/operation-counts.json
uv run python scripts/measure_job_store_queries.py --output var/ci/job-store-query-plan.json
uv run python scripts/render_test_dashboard.py --input-dir var/ci --output-html var/ci/test-dashboard-quality.html --output-svg var/ci/test-dashboard-quality.svg
```

治理工件包括 `cli-startup.json`、`operation-counts.json`、`job-store-query-plan.json`、`test-dashboard-quality.html` 与 Python/Windows/licensed dashboard；解释规则见 Performance Audit V2。当前运行证据仅写入 `RUNNER_TEMP`/`${{ runner.temp }}`，artifact 名包含 `github.run_id` 与 `github.run_attempt`。

## 工业应用场景

支持批量参数扫描、受约束优化、牌号切换、故障复算和受控数字孪生交接；不替代流程工程师、HAZOP/LOPA/SIL、客户模型批准或现场授权。

## 交付验收

`scripts/verify_delivery.py` 验证版本、README、工作流、AI 图、归档基线和真实 Aspen 边界。软件 PASS 只表示交付树满足声明合同；外部状态保持 `PENDING_REAL_ASPEN_CERTIFICATION`。

```bash
uv run python scripts/verify_delivery.py --root . --output var/ci/delivery-acceptance.json
```

## 确定性交付包

`scripts/build_delivery_bundle.py` 从干净 Git tree 生成：

```text
aspenops-source-<sha12>.zip
aspenops-handover-<sha12>.zip
aspenops-sbom-<sha12>.spdx.json
SHA256SUMS
```

SBOM 使用 `SPDX-2.3`；所有工件具有规范时间戳、排序成员和 SHA-256。`<sha12>` 是 commit 前 12 位，不是运行时占位输入。

```bash
uv run python scripts/build_delivery_bundle.py --root . --output-dir var/delivery --source-sha 0123456789abcdef0123456789abcdef01234567
```

## 证据包完整性与真实性

永久工作流为 `ci.yml`、`windows-control-plane.yml`、`generate-performance-evidence.yml`、`licensed-aspen-certification.yml`。手动证据仅接受 `refs/heads/main`；dispatch guard 在 `actions/checkout` 前检查 ref，不满足时**显式失败**并返回 status 2，而不是 all-skipped 假绿。候选和基线在 `detached` worktree 中验证。

许可环境要求 `expected_head_sha == GITHUB_SHA`，记录 `GITHUB_RUN_ID`、`GITHUB_RUN_ATTEMPT`、`LICENSED_EVIDENCE_DIR`、`run-metadata.txt`、`job_status` 和 `aspenops-licensed-artifact`。上传使用 `if-no-files-found: error`，路径位于 `runner.temp`，真实 Aspen 任务串行。

## 项目结构

- `src/aspenops_nexus/`：控制面、Process IR、scheduler、cache、optimizer、evidence、adapter；
- `tests/`：数值、并发、文件安全、文档、artifact 与 workflow 合同；
- `scripts/`：审计、性能、dashboard、Process IR 和 delivery bundle；
- `.github/workflows/`：四个永久工作流；
- `docs/assets/readme/`：二十三幅确定性 SVG。

## 故障排查

先运行 `uv run aspenops doctor --probe`，再检查 allowed roots、registry SHA、model identity、license、worker generation、state database 与 evidence bundle。禁止关闭测试、降低容差或把非收敛重解释为成功。

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

Apache-2.0 仅覆盖本仓库。Aspen Plus、Aspen HYSYS、Windows、许可证服务、客户模型和工艺数据受各自许可、保密与安全制度约束。


### 当前交付树强制验收

最终交付必须把测试结果、覆盖率与 Git 身份绑定到当前树；历史 PASS 不能代替当前源码资格。

```bash
uv run python scripts/verify_delivery.py \
  --root . \
  --require-current-qualification \
  --output var/ci/delivery-acceptance-current.json
```

验收面板包括 `test-dashboard-quality.html`、`test-dashboard-windows.html`、`test-dashboard-licensed.html`、`test-dashboard-licensed-mock.html` 与各 Python 版本面板。面板只汇总对应作业证据，不构成真实 Aspen 工程认证。

<!-- CURRENT_MAIN_ACCEPTANCE_V2:START -->
## 当前实现：代码、数学与使用策略

![中文代码与数学合同概念图](docs/current-main/aspenops-current-main-zh.svg)

> 软件门禁不等于真实 Aspen Plus/HYSYS 工程认证；外部状态保持 PENDING_REAL_ASPEN_CERTIFICATION。

#### 有界并发调度

$$
N_{\mathrm{dispatch}}=\min(N_{\mathrm{handles}},N_{\mathrm{unique}})
$$

这是 `CasePool` 的实际线程启动上界：有效工作句柄数与去重请求数取较小值。许可证、内存与稳定性仍须在部署时核实；该公式不声称程序自动测得全部资源限额。

源码对应: [`src/aspenops_nexus/pool.py`](src/aspenops_nexus/pool.py)

#### 热启动的状态隔离

$$
\exists q:\neg q.\mathrm{reinitialize}\;\Longrightarrow\;N_{\mathrm{workers}}=1
$$

复用求解器历史的请求必须使用单工作进程；否则代码拒绝执行。冷启动批次可以并发并使用持久缓存，但缓存命中只返回独立历史结果，不会恢复当前 Worker 的模拟器状态。关闭、替换或预算回收丢失状态后，warm 请求在写入/求解前以 warm_start_state_lost 拒绝；只有当前池当前 Worker 实际执行、通信和引擎状态成功且收敛的 reinitialize 才能恢复延续。Mock 回归不等于真实 Aspen 验收。

源码对应: [`src/aspenops_nexus/pool.py`](src/aspenops_nexus/pool.py)

#### 工作进程生命周期

$$
R_{\mathrm{periodic}}=(N_{\mathrm{eval}}\ge N_{\max})\lor(t_{\mathrm{age}}\ge t_{\max})
$$

周期性回收由已处理点数或单调时钟年龄触发；崩溃、超时、协议错误和污染状态还有独立回收条件。该布尔式只表示周期性条件，不是完整故障分类，也不证明一次 Aspen 计算收敛。

源码对应: [`src/aspenops_nexus/pool.py`](src/aspenops_nexus/pool.py)

#### 轮询输入与外部调用边界

$$
T_{\mathrm{timeout}},\Delta t\in\mathbb{R}_{>0}\cap\mathbb{R}_{\mathrm{finite}},\quad n_{\mathrm{stable}}\in\mathbb{N}_{>0}
$$

在读取外部 COM 引擎之前，timeout_s 与 poll_interval_s 必须为有限正数，stable_samples 必须是正整数，布尔值不能冒充这些数值。NaN 不能使超时失效；无法转换成有限浮点数的 COM 整数状态返回 UNKNOWN，而不是抛出未处理的溢出。轮询停止不等于求解收敛；收敛仍由状态节点、否定标记和引擎空闲证据共同判断。

源码对应: [`src/aspenops_nexus/convergence.py`](src/aspenops_nexus/convergence.py) · [`tests/test_polling_numeric_boundaries.py`](tests/test_polling_numeric_boundaries.py)

### 使用与验收顺序

1. 先核对安装环境、输入结构、单位、有效范围与执行权限。
2. 按上面的源码锚点区分原生实现、解释性合同和外部执行要求。
3. 先运行快速回归和完整质量门，再用固定提交执行长期回归。
4. 逐项保存原始日志、机器报告和限制；任何缺失证据不得写成 PASS。

```bash
uv lock --check
uv sync --frozen --extra dev --extra agent --extra signing
uv run python scripts/verify_delivery.py
```

每次修复均须绑定新提交重新测试。基线回归、两段各三小时的重复回归、浏览器图形检查和外部工程认证是不同证据，不可互相替代。没有原始回执时，不宣称已完成六小时验收。

源码锚点: [`src/aspenops_nexus/process_ir.py`](src/aspenops_nexus/process_ir.py) · [`src/aspenops_nexus/models.py`](src/aspenops_nexus/models.py) · [`src/aspenops_nexus/pool.py`](src/aspenops_nexus/pool.py)

<!-- CURRENT_MAIN_ACCEPTANCE_V2:END -->
