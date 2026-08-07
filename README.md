<div align="center">

# AspenOps 2.0

## 面向 Aspen Plus / Aspen HYSYS 与 AI Agent 的确定性工程控制平面

**受控需求 → 强类型过程意图 → 工程规则 → 可验证编译 → 隔离执行 → 工程判定 → 可审计证据 → 确定性交付**

[English](README.en.md) · [Architecture](docs/architecture.md) · [Delivery Acceptance](docs/delivery-acceptance.md) · [Delivery Bundle](docs/delivery-bundle.md) · [Windows Setup](docs/windows-setup.md) · [Certification](docs/certification.md) · [Quality Report](docs/quality-report.md)

[![CI main push](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/ci.yml/badge.svg?branch=main&event=push)](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/ci.yml?query=branch%3Amain+event%3Apush)
[![Windows main push](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/windows-control-plane.yml/badge.svg?branch=main&event=push)](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/windows-control-plane.yml?query=branch%3Amain+event%3Apush)
![Python](https://img.shields.io/badge/Python-3.11--3.13-3776AB)
![Version](https://img.shields.io/badge/version-2.0.0-111827)
![License](https://img.shields.io/badge/license-Apache--2.0-0F766E)

</div>

![AspenOps 总体架构](docs/assets/readme/hero-architecture.svg)

> **验收边界：** AspenOps 可以完成控制面、过程意图、隔离运行、缓存/调度/优化、证据链和确定性交付的软件资格；它不能在没有真实商业求解器、许可证、固定模型、Golden Case、硬件指纹和工程容差时自授真实 Aspen 工程资格。真实环境状态必须保持 `PENDING_REAL_ASPEN_CERTIFICATION`。

## 验收状态

| 项目 | 当前规则 |
|---|---|
| 长期分支 | 仅 `main` |
| Python 包 | `aspenops-nexus 2.0.0` |
| 历史全量软件资格基线 | `1224 passed`，0 failed，0 errors，95.03% branch coverage |
| 测试顺序 | reverse-order PASS；seed `20260728` PASS |
| 交付面验证 | `python scripts/verify_delivery.py` |
| 当前树严格资格 | `python scripts/verify_delivery.py --require-current-qualification` |
| 确定性交付包 | `scripts/build_delivery_bundle.py` |
| 真实 Aspen/HYSYS | `PENDING_REAL_ASPEN_CERTIFICATION` |

历史资格只证明其记录的源码；它不会自动证明任何后续提交。当前树若需要“最终验收资格”而不是“交付面完整”，必须提供 `docs/DELIVERY_QUALIFICATION.json` 并使用 `--require-current-qualification`。

---

## AI 与工程视觉图谱

以下图全部位于仓库内，不依赖第三方图片链接；四张 `docs/assets/ai/` 图为验收阶段的 AI 辅助示意图。

| 架构与意图 | 执行与安全 | 证据与工程 |
|---|---|---|
| ![hero](docs/assets/readme/hero-architecture.svg) | ![agent pipeline](docs/assets/readme/agent-pipeline.svg) | ![process IR](docs/assets/readme/process-intent-ir.svg) |
| ![backend](docs/assets/readme/backend-capabilities.svg) | ![adapter](docs/assets/readme/adapter-conformance.svg) | ![math](docs/assets/ai/mathematical-contracts.svg) |
| ![com isolation](docs/assets/readme/com-isolation.svg) | ![worker recycle](docs/assets/readme/worker-ownership-recycle.svg) | ![native failure isolation](docs/assets/ai/native-failure-isolation.svg) |
| ![validity](docs/assets/readme/validity-gates.svg) | ![warm start](docs/assets/ai/warm-start-trajectory.svg) | ![optimization](docs/assets/readme/optimization-lifecycle.svg) |
| ![scheduler](docs/assets/readme/scheduler-lifecycle.svg) | ![durable path](docs/assets/readme/durable-path-portability.svg) | ![cache](docs/assets/readme/cache-singleflight.svg) |
| ![evidence chain](docs/assets/readme/evidence-chain.svg) | ![evidence integrity](docs/assets/readme/evidence-integrity.svg) | ![licensed certification](docs/assets/readme/licensed-certification.svg) |
| ![cli mcp](docs/assets/readme/cli-mcp-workflow.svg) | ![mcp lifecycle](docs/assets/readme/mcp-runtime-lifecycle.svg) | ![path safety](docs/assets/readme/policy-path-safety.svg) |
| ![performance](docs/assets/readme/performance-hotspot-map.svg) | ![startup](docs/assets/readme/cold-warm-startup.svg) | ![test matrix](docs/assets/readme/test-matrix.svg) |
| ![industry](docs/assets/readme/industrial-scenarios.svg) | ![delivery](docs/assets/ai/delivery-acceptance.svg) | ![roadmap](docs/assets/readme/roadmap.svg) |

---

## 项目定位

AspenOps 不是“让大模型随意生成 COM/VBA/Python 去控制 Aspen”的脚本包装器。它把自然语言/Agent 意图收敛为可校验的数据合同和受控执行路径：

```text
Human / Agent
→ ProcessRequirementDocument
→ ProcessDesignIR
→ Engineering Rules
→ Simulator Capability Profile
→ Compilation / Evaluation Plan
→ CasePool / Scheduler
→ Process-isolated Worker
→ Aspen Plus / HYSYS / Mock
→ Readback + Constraints + Balances
→ Evidence Bundle
→ Deterministic Handover
```

主要软件职责：

- 强类型过程意图和语义化变量；
- 工程规则、单位、范围、自由度、回流/撕裂边验证；
- Aspen Plus/HYSYS 已批准模型的语义读写；
- 独立 Windows 子进程与 COM STA 所有权；
- `CasePool`、持久缓存、批处理、singleflight、调度和优化；
- native adapter conformance 与 failure isolation；
- 运行证据、哈希、签名、撤销和可重放交付；
- Mock/离线能力用于软件资格，不冒充真实热力学/设备结果。

---

## 数学与工程合同

![数学合同](docs/assets/ai/mathematical-contracts.svg)

### 1. 组分物料衡算

对组分 \(i\)：

```math
\frac{dN_i}{dt}
=
\sum_{s\in\mathcal I}\dot n_{i,s}
-
\sum_{s\in\mathcal O}\dot n_{i,s}
+
\sum_{r\in\mathcal R}\nu_{i,r}r_rV
```

稳态：

```math
0
=
\sum_{s\in\mathcal I}\dot n_{i,s}
-
\sum_{s\in\mathcal O}\dot n_{i,s}
+
\sum_{r\in\mathcal R}\nu_{i,r}r_rV
```

求解器返回“成功”并不等价于工程衡算通过。非有限衡算数据必须单独形成 `balance_non_finite`，残差超限形成 `balance_failed`。

### 2. 能量衡算

```math
\frac{dU}{dt}
=
\dot Q-\dot W
+
\sum_{s\in\mathcal I}\dot n_s\hat h_s
-
\sum_{s\in\mathcal O}\dot n_s\hat h_s
```

实际项目仍需批准焓基准、热损失、轴功、反应热和相平衡模型。

### 3. 多层有效性门

```math
OK =
C_{comm}
\land C_{engine}
\land C_{conv}
\land C_{finite}
\land C_{constraint}
\land C_{balance}
```

约束违背度：

```math
V(x)
=
\sum_j \max(0,g_j(x)-\varepsilon_j)
+
\sum_k \max(0,|h_k(x)|-\varepsilon_k)
```

`NaN`、`Infinity`、字符串伪数值和 Boolean 数值别名均 fail closed；约束中的非有限值使用 `constraint_non_finite` 表示。证据 JSON 使用 `allow_nan=False`。

### 4. 单位与仿射换算

```math
x_t=(x_s+a_s)\frac{m_s}{m_t}-a_t
```

绝对温度合同：

```math
T_K>0
```

参数合同同时检查数值类型、有限性、物理维度、整数性、分数范围和正值范围。

### 5. 回流图与撕裂边

对物料有向图 \(G=(V,E)\) 和撕裂边集合 \(T\)：

```math
\forall C\in cycles(G),\qquad C\cap T\neq\varnothing
```

仅声明“存在 recycle”不能压制任意无关循环；撕裂边必须属于实际循环。

### 6. 精馏自由度

```math
DOF=N_c-N_s
```

其中 \(N_c\) 为独立控制/可操纵自由变量数，\(N_s\) 为独立规范数。能力 profile 必须暴露与工程规则一致的独立设计规范，避免过度规定或欠规定。

### 7. 缓存身份

```math
K =
SHA256(
schema
\Vert version
\Vert backend
\Vert runtime
\Vert model
\Vert registry
\Vert request_{physical}
)
```

展示 metadata 不改变物理身份；模型、注册表、backend、runtime 或校验语义变化必须改变缓存键。

### 8. Warm-start 轨迹

![Warm-start trajectory](docs/assets/ai/warm-start-trajectory.svg)

```math
x_{k+1}=F(x_k,u_k),\qquad y_k=G(x_k)
```

warm-start 是路径依赖计算，因此：

- 同一轨迹只能由一个 Worker 顺序执行；
- 禁止 persistent cache；
- 禁止 same-batch dedup；
- 禁止 `inflight_singleflight`；
- session/step 进入轨迹身份；
- 优化默认使用 `reset_mode='reinitialize'`，避免目标值依赖前序状态。

### 9. 约束优化

```math
\min_x J(x)=\sum_{m=1}^{M}w_m f_m(x)
```

带罚项时：

```math
J_p(x)=J(x)+\lambda V(x),\qquad \lambda\ge0
```

使用策略：先验证可行性与工程门，再比较目标值；不能用高罚系数“掩盖”收敛、衡算或非有限值失败。

### 10. 许可证约束下的并发

保守并发上限：

```math
C_{\max}\le \min(L,W)
```

其中 \(L\) 为可用 license slots，\(W\) 为允许 Worker 数。实际并发还受内存、模型驻留和 Windows 进程资源限制。

### 11. 证据绑定

```math
H_{bundle}
=
SHA256(
H_{request}
\Vert H_{results}
\Vert H_{model}
\Vert H_{registry}
\Vert H_{environment}
)
```

Ed25519 只能认证规范 manifest 字节和密钥身份，不能把软件测试提升为真实 Aspen 工程认证。

---

## Process Intent IR 与工程规则

![Process Intent IR](docs/assets/readme/process-intent-ir.svg)

Process Intent IR 用于表达：

```text
units
streams
connections
parameters
tears
constraints
design intent
```

推荐使用策略：

1. 先在 Mock/离线编译阶段验证拓扑、单位、参数合同和能力 profile。
2. 对 recycle 图显式选择 tear edge。
3. 在真实 Aspen 模型上只允许批准的语义键和批准路径。
4. 对精馏、反应器、换热器、泵/压缩机分别执行设备合同。
5. 把“模型能运行”和“工程结果被批准”作为两个独立判定。

---

## 原生适配器一致性门

![Adapter conformance](docs/assets/readme/adapter-conformance.svg)

native adapter 在写入前必须绑定：

- capability profile；
- profile SHA-256；
- adapter contract 和代码身份；
- operation/`adapter_key` 覆盖；
- topology/layout readback；
- save/reopen；
- failure isolation；
- 授权新鲜度。

## 原生失败隔离

![Native failure isolation](docs/assets/ai/native-failure-isolation.svg)

两类可证明策略：

```text
PRIVATE_CASE_DISCARD
step failure
→ discard_private_case()
→ discarded == True
```

```text
TRANSACTIONAL_ROLLBACK
token = begin_transaction()
→ steps
→ commit_transaction(token)
or
→ rollback_transaction(token)
```

清理 API 缺失、返回非 literal `True`、rollback/discard 失败或 post-write 异常都会使 Worker tainted，并触发回收，不能伪装成普通求解失败。

---

## 快速开始

要求：Python 3.11–3.13，`uv >= 0.11.16`。

```bash
git clone https://github.com/SUNHAOJUN22/AspenOps-Agent.git
cd AspenOps-Agent

uv lock --check
uv sync --frozen --extra dev --extra agent --extra signing

uv run aspenops --version
uv run aspenops demo
uv run aspenops dry-run examples/batch-request.example.json
python scripts/verify_delivery.py --output var/ci/delivery-acceptance.json
```

真实 Windows 后端：

```powershell
uv sync --frozen --extra windows --extra dev --extra agent --extra signing
uv run aspenops doctor --probe
```

Mock 是控制面和软件资格后端，不代表真实 Aspen Plus/HYSYS 的热力学、物性、设备和收敛结果。

---

## 配置与路径安全

```dotenv
ASPENOPS_BACKEND=mock
ASPENOPS_MODE=default
ASPENOPS_ALLOWED_ROOTS=
ASPENOPS_STATE_DIR=var/aspenops-state
ASPENOPS_LICENSE_SLOTS=1
ASPENOPS_MAX_WORKERS=1
ASPENOPS_MAX_RESIDENT_CASES=2
```

真实后端示例：

```dotenv
ASPENOPS_BACKEND=aspen_plus
ASPENOPS_ALLOWED_ROOTS=C:/AspenModels;C:/AspenResults
ASPENOPS_STATE_DIR=C:/AspenResults/aspenops-state
```

![Path safety](docs/assets/readme/policy-path-safety.svg)

安全策略：

- 真实 backend 不允许空 allowlist；
- 只允许绝对批准根目录；
- `..`、symlink、junction、realpath 逃逸被拒绝；
- 未知 backend/mode fail closed；
- 字符串伪 Boolean 和非有限资源预算被拒绝；
- 私钥、Token、license secrets、客户模型和生产数据不得提交仓库。

---

## 批处理、缓存与 singleflight 策略

![Cache and singleflight](docs/assets/readme/cache-singleflight.svg)

对 `reinitialize` 请求，可以使用：

- memory LRU；
- SQLite WAL persistent cache；
- same-batch dedup；
- `inflight_singleflight`。

对 warm-start 请求，上述跨请求复用全部禁用。

建议：

1. 只有确定性、重新初始化的请求才启用结果复用。
2. 失败结果只有在明确策略下才允许缓存。
3. cache identity 必须包含 backend/runtime/model/registry/physical request。
4. cache JSON 必须拒绝 `NaN`/`Infinity` 和非 object root。
5. 任何从 cache 返回的对象都必须保持深度隔离。

---

## Worker 所有权与调度恢复

![Worker ownership](docs/assets/readme/worker-ownership-recycle.svg)

一个 Worker 对应一个独立执行所有权边界：

```text
spawned process
+ COM STA
+ Automation Server
+ private case
+ sequential command stream
+ process ownership supervision
```

![Scheduler lifecycle](docs/assets/readme/scheduler-lifecycle.svg)

调度状态包括：

```text
pending
→ claimed
→ running
→ completed | failed | cancelling
→ retry_wait | dead_letter | cancelled
```

lease 过期但仍有重试预算时进入 `retry_wait`；耗尽后进入 `dead_letter`。owner fencing 和幂等 commit token 用于防止旧 Worker 发布结果。

---

## 常用操作策略

### 批处理

```bash
uv run aspenops run-batch examples/batch-request.example.json \
  --output var/aspenops-state/results.json \
  --bundle var/aspenops-state/run-bundle.zip
```

### Durable scheduler

终端 1：

```bash
uv run aspenops scheduler
```

终端 2：

```bash
JOB_ID=$(
  uv run aspenops submit examples/batch-request.example.json |
  python -c 'import json,sys; print(json.load(sys.stdin)["job_id"])'
)

uv run aspenops job "$JOB_ID"
uv run aspenops cancel "$JOB_ID" --grace-s 2
```

### 优化

```bash
uv run aspenops optimize examples/optimization-request.example.json \
  --output var/aspenops-state/optimization-result.json
```

优化阶段必须优先使用 reinitialize；不要把 warm-start 当作无状态目标函数缓存。

### MCP

```bash
uv run aspenops mcp
```

MCP 只暴露受控工具，不提供任意 Shell、Python、VBA、COM 或 Aspen Tree Path。

### Evidence

```bash
uv run aspenops verify-bundle var/aspenops-state/run-bundle.zip
```

---

## 性能使用策略

![Performance hotspot map](docs/assets/readme/performance-hotspot-map.svg)

性能优化遵循：

```text
correctness qualification
→ deterministic operation-count evidence
→ same-environment timing
→ optimization
→ regression gate
```

仓库提供：

```text
scripts/measure_cli_startup.py
scripts/measure_operation_counts.py
scripts/measure_job_store_queries.py
```

只有相同输入、相同运行环境、相同重复次数和明确统计规则下的结果才允许形成 speedup 声明。

---

## 确定性交付包

软件验收不应只交一个源码目录。`scripts/build_delivery_bundle.py` 将一个确定 Git SHA 转换为可验证移交包。

```bash
rm -rf var/delivery
uv build

uv run python scripts/build_delivery_bundle.py \
  --source-sha "$(git rev-parse HEAD)" \
  --source-date-epoch 0 \
  --include-dist \
  --output-dir var/delivery
```

生成：

```text
aspenops-source-<sha12>.zip
aspenops-sbom-<sha12>.spdx.json
aspenops-evidence-index-<sha12>.json
aspenops-delivery-manifest-<sha12>.json
SHA256SUMS
aspenops-handover-<sha12>.zip
aspenops-handover-<sha12>.zip.sha256
wheel / source distribution
```

SBOM 格式为 `SPDX-2.3`。

每个产物 \(A_i\)：

```math
h_i=SHA256(A_i)
```

清单：

```math
S=\operatorname{sort}\{(h_i,\operatorname{name}(A_i))\}
```

最终包：

```math
B=
ZIP_{deterministic}
(A_1,\ldots,A_n,Manifest,SHA256SUMS)
```

最终外部哈希：

```math
h_B=SHA256(B)
```

交付构建器采用固定 ZIP 时间戳、排序成员、规范文件权限、严格 JSON 和 `allow_nan=False`；symlink、路径逃逸、非空输出目录、异常 Git SHA、自认证真实 Aspen 状态和异常分发包都 fail closed。

校验：

```bash
cd var/delivery
sha256sum -c SHA256SUMS
sha256sum -c aspenops-handover-*.zip.sha256
```

---

## 交付验收

![Delivery acceptance](docs/assets/ai/delivery-acceptance.svg)

### A. 交付面完整性

```bash
python scripts/verify_delivery.py \
  --output var/ci/delivery-acceptance.json
```

该模式检查：

- 中英文 README；
- 27 张受治理/AI 辅助图；
- deterministic bundle；
- SBOM/manifest/SHA-256 文档；
- qualification writer；
- 4 个永久只读 workflow；
- 临时 workflow/运行心跳残留；
- 历史资格基线；
- `PENDING_REAL_ASPEN_CERTIFICATION` 边界。

### B. 当前树严格验收

当 `docs/DELIVERY_QUALIFICATION.json` 已由完整资格流程生成后：

```bash
python scripts/verify_delivery.py \
  --require-current-qualification \
  --output var/ci/delivery-acceptance-current.json
```

推荐最终软件门禁：

```bash
uv lock --check
uv sync --frozen --extra dev --extra agent --extra signing
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run python -m compileall -q src scripts tests
uv run python scripts/audit_source_tree.py
uv run pytest --cov=aspenops_nexus --cov-branch --cov-fail-under=95
uv run python scripts/run_test_order_gate.py --seed 20260728 --output-dir var/ci
uv build
```

`write_delivery_qualification.py` 只允许在完整套件无失败、无错误、**无 skipped**、至少 1200 个通过测试、分支覆盖率至少 95%、delivery verifier 为 PASS 时写出 `aspenops.delivery-qualification/v2`。

---

## 仓库结构

```text
src/aspenops_nexus/     控制面、Worker、Pool、cache、scheduler、optimization、evidence
scripts/                审计、benchmark、delivery verifier、bundle builder
tests/                  软件合同、回归、顺序独立性、交付治理
examples/               Mock、batch、optimization、Process Intent IR
docs/                   architecture、acceptance、certification、delivery bundle、visuals
.github/workflows/      四个永久只读资格 workflow
```

---

## 真实 Aspen 外部资格输入

最终真实工程资格至少需要：

1. Aspen Plus/HYSYS 产品、精确版本、bitness、ProgID；
2. 有效 license feature 和允许并发席位；
3. 固定批准模型、registry、输入和输出列表；
4. Windows、Python、CPU、内存和 runner 指纹；
5. 每个 Golden Case 的工程/科学参考值；
6. 绝对/相对容差、重复次数和 PASS 规则；
7. topology/layout/save-reopen/readback 证据；
8. 工艺、物性、设备和安全审批。

缺少这些证据时：

```text
PENDING_REAL_ASPEN_CERTIFICATION
```

必须保持不变。

---

## License

Apache-2.0 仅覆盖本仓库。Aspen Plus、Aspen HYSYS、Windows、许可证服务器、客户模型和工艺数据分别受其许可、保密和安全制度约束。
