# AspenOps 2.0

**把过程方案落实为有单位、有边界的执行请求；以收敛、约束、衡算和原始证据逐点判断结果。**

[English](README.en.md) · [完整实现指南](docs/implementation-guide.zh-CN.md) · [Windows 部署](docs/windows-setup.md) · [交付验收](docs/delivery-acceptance.md)

![version-2.0.0-delivery](https://img.shields.io/badge/version-2.0.0-111827)
![Python 3.11–3.13](https://img.shields.io/badge/Python-3.11--3.13-3776AB)
![Apache 2.0](https://img.shields.io/badge/license-Apache--2.0-0F766E)

`aspenops-nexus 2.0.0` 是 Aspen Plus / Aspen HYSYS 的 Python 控制面。它统一 CLI、MCP、持久队列和隔离 Worker；热力学物性、设备模型与流程求解由外部商业模拟器和经过审阅的用户模型提供。

## 执行架构

![AI 生成的 AspenOps 执行架构：声明、治理、隔离执行和独立验证](docs/assets/ai-generated/architecture.png)

**图 1｜AI 生成示意图。** 请求先经过路径、注册表、单位和资源检查，再进入受限执行；搜索中的候选不自动成为可行解。图中的装置、轨迹与文件仅说明软件关系，不是 Aspen 计算结果、测量数据或工程认证。

| 需要完成的工作 | 实现入口 | 使用边界 |
|---|---|---|
| 把模型变量变成有单位的输入输出 | [registry](src/aspenops_nexus/registry.py)、[evaluation_plan](src/aspenops_nexus/evaluation_plan.py) | 必须核实具体模型节点和权限 |
| 批量运行并隔离失败 | [batch](src/aspenops_nexus/batch.py)、[worker](src/aspenops_nexus/worker.py)、[scheduler](src/aspenops_nexus/scheduler.py) | 私有模型快照、许可上限、超时和取消 |
| 采样与优化 | [design](src/aspenops_nexus/design.py)、[optimizer](src/aspenops_nexus/optimizer.py) | LHS、网格和有界 DE；可行性优先，不保证全局最优 |
| 验证过程意图与工程规则 | [process_ir](src/aspenops_nexus/process_ir.py)、[engineering_rules](src/aspenops_nexus/engineering_rules.py) | 有效 IR 不授予任意执行权限 |
| 固定结果身份并保留失败证据 | [provenance](src/aspenops_nexus/provenance.py)、[archive_safety](src/aspenops_nexus/archive_safety.py) | 摘要、签名信任与工程适用性分别判断 |

DWSIM、IDAES 与 Modelica/FMI 的执行适配器及通用 `aspenops.flowsheet/v1` 编译器仍为 `planned`，未实现不能写成已可用。已有 v2 规划对象与原生构建协议仍需对应的适配器资格和一致性测试。

真实工程状态保持 **`PENDING_REAL_ASPEN_CERTIFICATION`**。Mock 回归验证不代表真实 Aspen 已验收；发现 ProgID 也不认证商业软件版本。真实验收需要固定的 Windows 主机、许可证、模型与 registry、Golden Cases、工程容差、签名证据和工程师接受。


## 快速开始

从仓库根目录执行。推荐与 CI 相同的 **uv 0.11.16**、Python 3.12；项目支持 Python 3.11、3.12、3.13。

```bash
git clone https://github.com/SUNHAOJUN22/AspenOps-Agent.git
cd AspenOps-Agent
uv lock --check
uv sync --frozen --extra dev --extra agent --extra signing
uv run aspenops --version
uv run aspenops doctor --probe
uv run aspenops demo
uv run aspenops dry-run examples/guarded-mock-batch.example.json
uv run aspenops run-batch examples/guarded-mock-batch.example.json \
  --output var/guarded-results.json --bundle var/guarded-run-bundle.zip
uv run aspenops verify-bundle var/guarded-run-bundle.zip
```

这个[可运行请求](examples/guarded-mock-batch.example.json)包含三个温度/回流比点、必要输出、纯度约束，以及进料设定值的线性一致性检查。`declared_feed_setpoint` 检查流量读回值是否等于 `120 kg/h`，**它不是全装置质量守恒证明**：Mock 未提供全部出口。原始[最小批量示例](examples/batch-request.example.json)继续保留，用于检查连接和执行链。

`dry-run` 不开启 Aspen，返回路径、注册表摘要、有效 Worker 数和 I/O 预算。`run-batch` 写入逐点 JSON 和证据 ZIP；任一点 `ok=false` 时退出码为 `2`，诊断仍被保存。`verify-bundle` 校验归档及摘要；未签名包只提供完整性证据。[CLI 实现](src/aspenops_nexus/cli.py)

Windows 同步依赖时另加 `--extra windows`。真实环境步骤见 [Windows 指南](docs/windows-setup.md)。`.env.example` 是模板，应把变量导入实际进程环境。

## 简洁技术路线

![AI 生成的 AspenOps 技术路线：发现环境、绑定变量、预检、执行、核验证据](docs/assets/ai-generated/roadmap.png)

**图 2｜AI 生成示意图。** `system_info` → `list_semantic_variables` → `dry_run_request` → `submit_batch` → `job_status` / `job_result` → `verify_evidence_bundle`。超过 16 点或长求解使用后台队列；每种新批次定义先预检。

$$
W_{\rm eff}=\min(W_{\rm request},W_{\max},L),\qquad
\mathrm{ok}=C\land E\land V\land F.
$$

$L$ 是声明的许可槽位，不是程序测得的授权数量；$C,E,V,F$ 分别为通信、引擎、收敛和声明约束／衡算的资格。任一必需门失败都保留诊断并停止接受。摘要证明指定字节的一致性；签名还需要外部可信公钥，真实工程接受还需要实际许可运行与人工审阅。


## 数学与工程合同

![AI 生成的 AspenOps 算法图：目标归一化、有界 DE、线性衡算和评估预算](docs/assets/ai-generated/algorithm.png)

**图 3｜AI 生成示意图。** 下列关系对应实际代码；完整定义、单位、异常路径和回归入口见[实现指南](docs/implementation-guide.zh-CN.md)。

### 先保证输入可解释

JSON 中非有限数值以及被解析成零的非零小数会被拒绝；已经在调用方舍入成零的 Python 浮点数无法恢复原始十进制信息。真实单位必须来自 registry；单位转换同时处理比例和偏移。

$$
y=\frac{a_sx+b_s-b_t}{a_t}.
$$

$a_s,a_t$ 为到共同基准单位的比例，$b_s,b_t$ 为偏移。温度参考值与温差尺度应分别处理：绝对 $20\,{}^\circ\mathrm C$ 对应 $293.15\,\mathrm K$，$10\,{}^\circ\mathrm C$ 的温差尺度仍为 $10\,\mathrm K$。[单位实现](src/aspenops_nexus/units.py)

### 衡算先检查数值有效性，再检查容差

每个 $q_i$ 先转换到共同 `base_unit`；$c_i$ 是有限、无量纲系数，$b$ 是声明目标，$f$ 是尺度下限：

$$
r=\operatorname{fsum}(c_1q_1,\ldots,c_nq_n,-b),\qquad
S=\max\left(\sum_i|c_iq_i|,f\right),\qquad \rho=|r|/S.
$$

$$
\mathrm{passed}\iff\mathrm{valid}\land
\left(|r|\le a_{\rm tol}\ \lor\ \rho\le r_{\rm tol}\right).
$$

`valid` 包括有限性、定义域与下溢检查；$S$ 不包含 $|b|$。$r,S,f,a_{\rm tol}$ 使用同一单位，$\rho,r_{\rm tol}$ 无量纲；$S=0$ 无效。非零比值下溢时，代码使用最小正浮点数作为保守上界，并标注 `relative_upper_bound`。实际质量或能量守恒需要完整的物料项或功率／焓流项。[衡算实现](src/aspenops_nexus/evaluation.py)

### 搜索中的候选、可行性与目标分别判断

$$
z_j=\sigma_j\frac{y_j-r_j}{s_j},\qquad J=\sum_jw_jz_j,
\qquad s_j>0,\ w_j>0.
$$

$\sigma_j=+1$ 表示最小化，$-1$ 表示最大化；读回值先转换到声明单位。可行解优于不可行解；两个可行解比较目标，不可行解比较诊断违约量。该违约量不是统一物理单位的工程损失。DE/rand/1/bin 使用

$$
v_d=a_d+F_m(b_d-c_d),\qquad x_d\in[\ell_d,h_d].
$$

正常、未取消执行中，种群 $P\ge4$、预算 $B\ge P$、计划代数 $G\ge0$ 满足

$$
G_* =\min\left(G,\left\lfloor\frac{B-P}{P}\right\rfloor\right),\qquad
N_{\rm eval}=P(1+G_*)\le B.
$$

预算不足完整一代时不启动该代。计数对象是候选评估，缓存可能减少真实求解次数；种群并非热力学系综。[优化实现](src/aspenops_nexus/optimizer.py)


## 七仓总路线与统计力学背景

![AI 生成的七仓技术总路线，虚线表示建议接口，公式表示正则平衡理论背景](docs/assets/ai-generated/seven-repo-roadmap.png)

**图 4｜AI 生成示意图。** 七仓保持独立；虚线表示建议的交接关系，不能据图推断已存在端到端集成。固定 $N,V,T$、$T>0$ 的正则平衡体系满足

$$
\beta=\frac{1}{k_BT},\qquad Z=\sum_i e^{-\beta E_i},\qquad
p_i=\frac{e^{-\beta E_i}}{Z},\qquad F_{\rm Helmholtz}=-k_BT\ln Z.
$$

$E_i$ 为微观态能量，$k_B$ 为 Boltzmann 常数。这提供能量与熵竞争的理论背景；AspenOps 没有据此实现配分函数或物性求解器。开放流程仍须单独处理流入、流出、反应和能量传递；DE 的候选群体也不服从图中的 Boltzmann 分布。[Tong 统计物理讲义](https://www.damtp.cam.ac.uk/user/tong/statphys/statmechhtml/S1.html)

四幅当前科学示意图的[来源与提示词](docs/assets/ai-generated/README.md)可核对；图内共用英文标签，中英图注分别解释。原有二十三幅工程 SVG 保存在明确的[历史图集](docs/assets/README.md)，[旧中文 hero](docs/assets/readme-vnext/hero.zh-CN.svg)仅作历史普通链接。


<details>
<summary>操作、部署与验收细节</summary>


## 配置边界

| 环境变量 | 默认值 | 含义 |
|---|---|---|
| `ASPENOPS_BACKEND` | `mock` | `mock`、`aspen_plus`、`hysys` |
| `ASPENOPS_MODE` | `default` | `readonly` 禁止参数写入；部分扩展操作需要 `enhanced` |
| `ASPENOPS_ALLOWED_ROOTS` | 空 | 分号分隔的允许根目录；真实后端必须声明绝对路径 |
| `ASPENOPS_STATE_DIR` | `var` | 缓存和任务目录；真实后端要求允许根目录内的绝对路径 |
| `ASPENOPS_LICENSE_SLOTS` / `ASPENOPS_MAX_WORKERS` | `1` / 许可证槽数 | 管理员声明的并发上限，代码不自动证明许可容量 |
| `ASPENOPS_TIMEOUT_S` / `ASPENOPS_STARTUP_TIMEOUT_S` | `1200` / `90` 秒 | 点请求默认响应预算 / Worker 启动预算 |
| `ASPENOPS_WORKER_MAX_POINTS` / `ASPENOPS_WORKER_MAX_AGE_S` | `200` / `14400` 秒 | 周期回收条件 |
| `ASPENOPS_MAX_REQUEST_BYTES` / `ASPENOPS_MAX_BATCH_POINTS` | `10000000` / `10000` | 请求大小 / 批次点数上限 |
| `ASPENOPS_MAX_SEMANTIC_OPERATIONS` | `1000000` | 批次声明的语义操作预算 |
| `ASPENOPS_MAX_OPTIMIZATION_EVALUATIONS` | `10000` | 优化评估上限；另限制 64 个变量与 16 个目标 |

其余调度选项及类型检查以 [Settings](src/aspenops_nexus/config.py) 为准。[资源预算](tests/test_config_resource_budgets.py)与[批次限制](tests/test_batch_resource_limits.py)测试覆盖拒绝路径。

## 配置与路径安全策略

路径先展开并解析，再检查允许范围。真实后端拒绝空根目录、相对根目录和范围外状态目录。主模型只用于生成私有快照；Worker 开启前后核对模型/注册表摘要。`readonly` 按实际写入行为拒绝请求。[策略](src/aspenops_nexus/policy.py) · [快照身份测试](tests/test_phase0_artifact_identity.py)

持久提交把模型、注册表及 checkpoint 路径固定为绝对路径，记录 `paths_pinned`、`submission_cwd`。scheduler 从另一目录启动仍指向提交时的文件，内容身份继续由摘要保护。[路径实现](src/aspenops_nexus/durable_request.py) · [CLI 回归](tests/test_cli_durable_queue.py)

`run-batch` 在解析前限制普通文件大小，解析后检查规范化请求预算；重复 JSON 键与无效数值不会被静默改写。不要把输出路径设为主模型，也不要让 Agent 使用旁路 `win32com`、任意 Shell、VBA 或未经注册的模拟器路径。

## 独立有效性门

逐点检查 `communication_ok`、`engine_ok`、`converged`、`feasible`、`violations`、`balance_residuals`。`constraint_non_finite` / `balance_non_finite` 表示无效数值证据；`constraint_failed` / `balance_failed` 表示声明检查未通过。进程返回、引擎空闲及任务 `completed` 都不能代替逐点 `ok`。

Mock 使用人工设定的关系验证软件合同，其公式和单位约定见[实现指南](docs/implementation-guide.zh-CN.md)。这些关系不是经过拟合的物性或装置模型。

## 典型工作流

**小批次：** 先 `doctor`、检查注册表，再 `dry-run`、`run-batch`。验证少量点的单位、约束和收敛证据后扩大范围。只注册已确认的模型节点，不猜测 Aspen Tree Path 或 HYSYS 对象链。

**耐久批次：** 在终端 A 启动服务，在相同环境的终端 B 提交；两者必须共享 `ASPENOPS_STATE_DIR`。

```bash
# 终端 A：保持运行，Ctrl+C 停止
uv run aspenops scheduler
```

```bash
# 终端 B：Bash；只提交一次
JOB_ID=$(uv run aspenops submit examples/guarded-mock-batch.example.json \
  | python -c "import json,sys; print(json.load(sys.stdin)['job_id'])")
uv run aspenops job "$JOB_ID"
# 仅在确需取消时执行：
uv run aspenops cancel "$JOB_ID" --grace-s 2
```

PowerShell 可保存 `uv run aspenops submit ... | ConvertFrom-Json` 的结果，再读取 `.job_id`，不要照搬 Bash 赋值。提交成功不代表 scheduler 已执行。[任务指南](docs/agent-usage.md)

[Python 调用示例](docs/implementation-guide.zh-CN.md)使用 `__main__` 保护进程入口。

## MCP 兼容性与服务生命周期

```bash
uv run aspenops mcp
```

安装 `agent` extra 后提供本地 stdio MCP，依赖合同为 `mcp>=1.30.0,<2`。服务 lifespan 启停同一 scheduler/PoolManager。[实现](src/aspenops_nexus/mcp_server.py) · [兼容性检查](scripts/check_mcp.py) · [历史 MCP 生命周期技术图](docs/assets/readme/mcp-runtime-lifecycle.svg)

Agent 顺序：`system_info` → `list_semantic_variables` → `dry_run_request` → `submit_batch` → `job_status` / `job_result` → `verify_evidence_bundle`。`run_batch_sync` 上限 16 点；长求解即使点数少也应后台提交。优化工具为 `submit_optimization`、`optimization_status`、`optimization_result`、`cancel_optimization`。只接受 `ok=true` 的点，证据校验与工程解释另行完成。

## 约束优化闭环

```bash
uv run aspenops optimize examples/optimization-request.example.json \
  --output var/optimization-result.json
```

[示例](examples/optimization-request.example.json)使用温度和有序回流比，设置最小纯度约束、目标单位和规范化尺度。先确认可行域，再增加种群、代数；实际预算受 Settings 限制。输出保留 trace、候选、可行 Pareto 集、请求身份及预算。checkpoint 在初始种群及每代后原子写入，作为复查快照；当前 CLI 不宣称可从任意 checkpoint 自动恢复 DE 状态。[优化指南](docs/optimization-engine.md)

## Process Intent 与工程设计

```bash
uv run python scripts/validate_process_ir.py examples/process-intent.example.json \
  --canonical-output var/ci/process-intent-canonical.json \
  --report-output var/ci/process-intent-report.json
uv run python scripts/render_process_ir_dashboard.py \
  --input var/ci/process-intent-report.json \
  --output-html var/ci/process-ir-dashboard.html \
  --output-svg var/ci/process-ir-dashboard.svg
uv run python scripts/validate_process_design_v2.py \
  examples/process-requirement-v1.example.json examples/process-design-v2.example.json \
  --report-output var/ci/process-design-report.json
```

v1 检查组件、设备、端口、流股、引用和资源上限；规范化排序使相同图的不同输入顺序不影响摘要。`process-ir-dashboard.html` 是合同检查面板，不是模拟结果。v2 增加需求绑定、参数、组成、电荷、质量和 recycle 合同检查。[IR 指南](docs/process-intent-ir.md)

## 原生适配器一致性门

v2 原生构建要求 `NativeBuildAdapter` 协议、manifest、输入/输出 schema、单位、失败隔离、事务和拓扑/layout 读回，并绑定适配器代码、运行时身份、签名资格、撤销策略与有效见证。缺证据的计划必须阻断；声明兼容版本不是目标商业软件认证。[适配器门](src/aspenops_nexus/native_adapter_conformance.py) · [受控执行](src/aspenops_nexus/native_builder.py) · [指南](docs/native-adapter-conformance.md)

## 缓存、批内去重与单航班

规范 JSON 以排序键和固定分隔符构建稳定摘要，使用 `allow_nan=False` 拒绝非有限输出；输入原始十进制的检查由请求解析层负责。[摘要实现](src/aspenops_nexus/hashing.py)

独立 `reinitialize` 请求可使用持久缓存、`same_batch_dedup`、`inflight_singleflight`。默认不缓存失败；启用 `ASPENOPS_CACHE_FAILURES` 仍排除通信/引擎失败及污染 Worker。SQLite WAL、内存 LRU 减少重复访问；结果深复制隔离调用方修改。[缓存](src/aspenops_nexus/cache.py) · [回归](tests/test_pool_cache_efficiency.py)

**缓存命中只返回独立历史结果**，不会把参数写回当前 Worker。`warm_start` 禁用结果缓存，要求单 Worker、同一 session、递增且唯一的 step，不能与冷点混在一个 pool 调用。实时池在跨调用、跨租约复用时继续绑定 session 与最后派发的 step；跨 session、重复或倒退步骤在任何参数写入和读回之前拒绝，返回 `warm_start_session_mismatch` 或 `warm_start_step_not_increasing`，原轨迹状态保持不变。

已派发的步骤即使不收敛也占用其编号；派发前取消不消耗编号。需要恢复时使用同一 session 的更大 step，或实际执行一次冷初始化后开启新 session。这些标签是轨迹顺序合同，不是用户身份认证。关闭、替换、超时、失败冷初始化或冷请求只命中缓存会阻断延续；只有当前 Worker 真正完成通信/引擎成功且收敛的 `reinitialize` 才清除旧绑定并恢复延续资格。失败约束与实时状态有效性仍分开判断。[热启动回归](tests/test_warm_start_continuity.py) · [跨调用/租约绑定回归](tests/test_warm_start_session_binding.py)

## Worker 所有权与回收

Worker 在私有模型快照上开启模拟器，IPC 绑定协议版本、请求 ID、结果 schema。真实后端要求 Windows Job Object 监督；进程清理核对 PID、创建时间、可执行文件指纹及后代关系，不能终止用户独立开启的 Aspen。[Worker](src/aspenops_nexus/worker.py) · [监督](src/aspenops_nexus/windows_job.py) · [所有权回归](tests/test_aspen_process_ownership.py)

$$
R_{\rm periodic}=(n_{\rm evaluated}\ge n_{\max})\lor(t_{\rm age}\ge t_{\max}).
$$

点数和单调时钟年龄是周期条件；崩溃、协议错误、污染状态、超时和取消截止还有独立回收路径。替换后 generation 增加，旧实时状态不会隐式恢复。

## 原生失败隔离

`timeout_s` 是一次 Worker 请求等待响应的预算，不是排队、启动、重建、证据打包的总耗时 SLA。超时会终止所属 Worker 并返回 `worker_timeout`；启动有独立预算，终止/回收有清理时间。协议或 request ID 不匹配的响应不能被当成成功。[IPC 回归](tests/test_worker_protocol_hardening.py) · [轮询数值边界](tests/test_polling_numeric_boundaries.py)

## 调度与恢复

队列保存 owner、租约、心跳、完成位置和取消状态。可恢复失败进入 `retry_wait`，耗尽尝试进入 `dead_letter`；租约 fencing 防止旧执行者覆盖重新认领后的任务结果。取消先请求停止，宽限到期回收活跃 Worker。任务完成后仍须检查逐点 `ok`。[实现](src/aspenops_nexus/scheduler.py) · [竞争测试](tests/test_scheduler_multiprocess_races.py) · [租约回归](tests/test_scheduler_claimed_lease_fencing.py)

## 证据包完整性与真实性

运行包绑定请求、结果、模型/注册表和环境摘要。归档读取拒绝不安全路径、重复声明、超限成员与不匹配摘要。Ed25519 以外部信任的公钥验证签名，包内公钥不能自行成为信任根。完整性、真实性和模型适用性分别判断。[证据实现](src/aspenops_nexus/provenance.py) · [归档测试](tests/test_provenance_zip_safety.py)

核心质量与执行工作流包括 `ci.yml`、`windows-control-plane.yml`、`generate-performance-evidence.yml`、`licensed-aspen-certification.yml`。质量作业使用 `ubuntu-24.04`，Windows 控制面使用 `windows-2025`。冻结依赖分别审计 Linux 与 Windows、Python 3.11、3.12、3.13 六种组合；执行矩阵以工作流文件为准。 另有 [EPDM 公开来源下载](.github/workflows/epdm-public-source-download.yml)工作流，用于原始公开资料与下载回执，不执行模拟器。

手动流程只接受 `refs/heads/main`，在 `actions/checkout` 前进行 dispatch guard；非 main **显式失败**并返回 status 2。候选/基线使用 `detached` worktree。许可任务在受保护、自托管 Windows 环境串行运行，要求 `expected_head_sha == GITHUB_SHA`，记录 `GITHUB_RUN_ID`、`GITHUB_RUN_ATTEMPT`、`LICENSED_EVIDENCE_DIR`、`run-metadata.txt`、`job_status`。手动性能/许可证据目录为 `RUNNER_TEMP` / `${{ runner.temp }}`，工件名同时包含 `github.run_id` 与 `github.run_attempt`，区分不同运行及同一运行的重试，许可上传使用 `aspenops-licensed-artifact` 和 `if-no-files-found: error`。[许可控制面](docs/licensed-certification-control-plane.md)

## 性能工程与证据

可测指标包括冷/热 CLI 启动、导入时间、读节点数、缓存访问、序列化次数、SQLite 查询计划及内存峰值。单 Worker 同步派发减少额外线程，仿真仍在隔离进程。性能结论需要同环境、同工作量前后对比；Mock 时间不是 Aspen 加速比。

```bash
uv run aspenops benchmark --points 4 --workers 1,2
uv run python scripts/measure_cli_startup.py --output var/ci/cli-startup.json
uv run python scripts/measure_operation_counts.py --output var/ci/operation-counts.json
uv run python scripts/measure_job_store_queries.py --output var/ci/job-store-query-plan.json
```

解读 `cli-startup.json`、`operation-counts.json`、`job-store-query-plan.json` 时参考 [Performance Audit V2](docs/performance-audit-2026-07-27-v2.md)。历史报告只作对照，本次交付使用目标提交的新记录。

## 工业应用场景

| 场景 | 使用策略 |
|---|---|
| 分离/反应条件扫描 | 少量冷点验证后扩大 LHS/网格，先声明产品约束和完整流股项 |
| 能耗与质量折中 | 固定单位、参考尺度、可行域和预算，再解释 Pareto 候选 |
| 延续轨迹、牌号切换研究 | 单 Worker 与明确 session/step；丢失状态后重建受控初始条件 |
| 故障重现、模型交接 | 固定摘要、注册表、运行时、seed 和原始结果，保留失败点 |
| Agent 过程方案 | 输出受限 IR 与引用假设，通过图/工程规则后进入授权执行 |

这些是工作流用途；具体设计仍需批准模型及工程审查，代码不提供工厂级安全认证。

## 交付验收

只维护一个长期分支 `main`。[质量报告](docs/quality-report.md)中的**已验证归档基线**供历史对照，**不是对任意后续提交的自动声明**。此次交付需绑定目标 SHA 的完整日志、JUnit、分支覆盖率、构建与工件摘要；收集数、跳过数、旧截图均不是通过数。

原冻结门禁如下，Windows 同步时另加 `--extra windows`：

```bash
uv lock --check
uv sync --frozen --extra dev --extra agent --extra signing
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run python -m compileall -q src scripts
uv run python scripts/audit_source_tree.py
uv run pytest -W error::ResourceWarning \
  --cov=aspenops_nexus --cov-branch --cov-fail-under=95.0
uv build
uv run python scripts/check_mcp.py
uv run python scripts/check_wheel_metadata.py --dist-dir dist
uv run python scripts/validate_process_ir.py examples/process-intent.example.json
uv run aspenops --version
uv run aspenops demo
uv run python scripts/verify_delivery.py --root . --output var/ci/delivery-acceptance.json
```

CI 另执行六组合冻结依赖审计、Bandit `1.9.4` high/high 和 Python 3.12 逆序/固定随机顺序测试。面板由 `scripts/render_test_dashboard.py` 从原始证据生成：`test-dashboard-quality.html` 展示通用软件质量门禁，`test-dashboard-windows.html` 展示 Windows 软件门禁，`test-dashboard-licensed.html` 展示受保护的真实引擎资格验证证据。三者的运行平台和证据范围不同，阅读面板时应核对源码 SHA 与原始结果。长时间稳定性运行必须记录真实活动测试时间、循环结果及源码身份；单次回归不能代替六小时完成证明。

## 确定性交付包

`scripts/build_delivery_bundle.py` 要求干净 Git tree 及真实当前 SHA，拒绝未提交文件与不匹配身份。产物为 `aspenops-source-<sha12>.zip`、`aspenops-handover-<sha12>.zip`、`aspenops-sbom-<sha12>.spdx.json`、`SHA256SUMS`，使用排序成员、规范时间戳与 `SPDX-2.3` SBOM。

```bash
# 在已提交、已验证的干净 main 上执行，使用真实 SHA。
uv run python scripts/build_delivery_bundle.py \
  --root . --output-dir var/delivery --source-sha "$(git rev-parse HEAD)"
uv run python scripts/verify_delivery.py \
  --root . --require-current-qualification \
  --output var/ci/delivery-acceptance-current.json
```

`--require-current-qualification` 需要当前源码的合格证据记录；仅构建 ZIP 不会自动授予 PASS。按[交付指南](docs/delivery-acceptance.md)从原始证据写入该记录，保留真实工程资格边界。

## 项目结构

| 路径 | 责任 |
|---|---|
| `src/aspenops_nexus/` | 唯一运行时：模型、单位、注册表、执行、队列、优化、IR、研究、证据 |
| `examples/` | Mock、注册表、优化、过程及研究合同示例 |
| `tests/` | 数值、协议、并发、文件安全、打包、文档与工作流回归 |
| `scripts/` | 审计、IR、基准、面板及确定性交付 |
| `.github/workflows/` | 软件、Windows 控制面、性能和许可工作流 |
| `docs/assets/ai-generated/` | 四幅完整 AI 示意图、提示词和字节身份 |
| `docs/assets/README.md` | 二十三幅工程 SVG 与验收图的历史技术图集 |

## 故障排查

| 现象 | 排查方向 |
|---|---|
| `dry-run` 失败 | 允许路径、键/标识符、权限、单位、上下界和预算 |
| `worker_timeout` | 点预算、求解状态和回收；终止不表示收敛 |
| `warm_start_session_mismatch` / `warm_start_step_not_increasing` | 核对池的活跃 session 与最后派发步骤；换轨迹需真正完成冷初始化 |
| `warm_start_state_lost` | 在当前 Worker 实际完成受控 `reinitialize`，缓存不能恢复状态 |
| `constraint_non_finite` / `balance_non_finite` | 原始值、单位量级、缺失项和派生溢出 |
| `balance_underflow` 或零容差失败 | 检查尺度与实际误差要求，不能把小非零量改为零 |
| 长期 pending | scheduler 是否运行，提交端和服务端状态目录是否一致 |
| 缓存不复用 | 模型、注册表、运行时、请求与算法语义摘要是否改变 |
| 许可/签名失败 | 受信公钥、目标 SHA、有效期、撤销状态与原始阻断证据 |

## License

[Apache-2.0](LICENSE) 覆盖本仓库代码。Aspen Plus、Aspen HYSYS、Windows、客户模型及商业工艺数据遵循各自许可和数据使用要求。

</details>

<!-- CURRENT_MAIN_ACCEPTANCE_V2:START -->
## 可再生实现索引

本索引由 `scripts/refresh_current_main_readme.py --write` 生成，使用 `--check` 检查固定点。正文中的数理定义与可执行流程是主要使用说明；下列源文件与历史概念图保留用于追溯。

[`src/aspenops_nexus/process_ir.py`](src/aspenops_nexus/process_ir.py) · [`src/aspenops_nexus/models.py`](src/aspenops_nexus/models.py) · [`src/aspenops_nexus/pool.py`](src/aspenops_nexus/pool.py)

[历史中文代码合同图](docs/current-main/aspenops-current-main-zh.svg)

软件门禁不等于真实 Aspen Plus/HYSYS 工程认证；外部状态保持 PENDING_REAL_ASPEN_CERTIFICATION。

<!-- CURRENT_MAIN_ACCEPTANCE_V2:END -->
