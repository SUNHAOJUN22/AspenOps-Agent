<div align="center">

# AspenOps 1.0

## 为 Aspen 建立一层可验证、可并发、可审计的“执行操作系统”

### Codex / Claude Code → 语义工艺意图 → 隔离执行 → Aspen 求解 → 工程判定 → 可复现实验证据

**不是 GUI 宏。不是几行 `Tree.FindNode()`。不是让大模型直接碰 COM。**  
**AspenOps 是 AI Agent 与工业流程模拟器之间的确定性控制平面。**

[English](README.en.md) · [Architecture](docs/architecture.md) · [Windows Setup](docs/windows-setup.md) · [Performance](docs/performance.md) · [Certification](docs/certification.md) · [Security](SECURITY.md)

[![CI](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/ci.yml/badge.svg)](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11--3.13-3776AB)
![Version](https://img.shields.io/badge/version-1.0.0-111827)
![License](https://img.shields.io/badge/license-Apache--2.0-0F766E)
![Aspen](https://img.shields.io/badge/Aspen-Plus%20%7C%20HYSYS-005A9C)
![Agent](https://img.shields.io/badge/Agent-Codex%20%7C%20Claude%20Code-6B4EFF)

</div>

---

## 一句话定义

> **AspenOps 1.0 把 Aspen Plus / Aspen HYSYS 从一个有状态、会阻塞、版本敏感、许可证受限的桌面模拟器，变成一个能够被 Codex、Claude Code、MCP 客户端和 Python 工作流安全调用的确定性计算引擎。**

它建立的不是“自然语言遥控器”，而是一套完整的执行语义：

```text
Agent 决定研究什么
Aspen 求解热力学与流程方程
AspenOps 决定操作是否允许、单位是否正确、运行是否收敛、结果是否物理可信、证据是否可复现
```

---

## 为什么传统 Aspen 自动化远远不够

最常见的 Aspen Python 脚本通常只有四步：

```python
app = Dispatch("Apwn.Document.XX.0")
app.InitFromArchive2(case)
app.Tree.FindNode(path).Value = x
app.Engine.Run2()
```

这段代码可以演示 COM，却没有解决生产自动化中的核心问题：

- Aspen 版本升级后 ProgID 变化；
- COM 对象不能安全跨线程、跨进程传递；
- `Run2()` 返回不等于流程收敛；
- Aspen 阻塞时 Python 线程无法可靠中止；
- 不同工况互相污染，热启动产生路径依赖；
- LLM 可以拼接任意 Tree Path，存在误写和越权风险；
- 单位错误可能得到“数值正常但物理错误”的结果；
- 并行数超过许可证、内存或模型稳定上限后，吞吐量反而下降；
- 模型、注册表、输入和输出没有内容哈希，结果无法追溯；
- 公共 CI 没有 Aspen，代码经常处于“README 可运行、实际不可验证”的状态。

AspenOps 1.0 的目标就是一次性解决这些问题。

---

# 系统架构

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Codex / Claude Code / MCP Client                        │
│        只表达工艺变量、DOE、约束、目标和结果需求；不接触原始 COM             │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │ typed MCP / CLI / JSON
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AspenOps Control Plane                              │
│                                                                             │
│  Path Policy   Semantic Registry   Unit Algebra   Bounds   Dry Run          │
│  Job Store     Content Cache       Evidence Bundle   Audit   Certification  │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │ one batched RPC per point
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Persistent CasePool                                 │
│                                                                             │
│   ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐        │
│   │ Worker 0         │   │ Worker 1         │   │ Worker N         │        │
│   │ private process  │   │ private process  │   │ private process  │        │
│   │ COM STA          │   │ COM STA          │   │ COM STA          │        │
│   │ private case copy│   │ private case copy│   │ private case copy│        │
│   │ one Aspen session│   │ one Aspen session│   │ one Aspen session│        │
│   └────────┬─────────┘   └────────┬─────────┘   └────────┬─────────┘        │
└────────────┼──────────────────────┼──────────────────────┼──────────────────┘
             │                      │                      │
             ▼                      ▼                      ▼
       Aspen Plus / HYSYS     Aspen Plus / HYSYS     Aspen Plus / HYSYS
```

### 不可破坏的架构不变量

1. **一个 COM 对象只属于一个 Windows 子进程和一个 STA apartment。**
2. **Agent 只调用语义变量，不构造原始 Aspen Tree Path。**
3. **每个 Worker 使用源模型的私有副本，绝不覆盖主模型。**
4. **一次工况通过一次 IPC 完成重置、批量写入、求解、批量读取和工程校验。**
5. **超时只终止 AspenOps 自己创建的 Worker，不执行全机范围的 `taskkill`。**
6. **通信成功、引擎返回、数值收敛、工艺可行和守恒闭合是五个不同状态。**
7. **Mock CI 证明控制平面，不冒充真实 Aspen 物理认证。**

---

# 面向最新 Aspen 版本的兼容策略

AspenOps 不把某个 `Apwn.Document.N.0` 写死成“最新版本”，也不维护容易过期的营销版本对照表。

启动时它会：

1. 若设置 `ASPENOPS_PROGID`，优先使用操作员明确指定的 ProgID；
2. 同时扫描 64 位与 32 位 Windows Registry View；
3. 枚举所有 `Apwn.Document.*` 注册项；
4. 对数字版本进行解析并按从新到旧排序；
5. 使用 `DispatchEx` 逐个建立隔离 Automation Server；
6. 最后尝试无版本的 `Apwn.Document`；
7. 将实际成功的 ProgID、应用暴露的版本属性和能力写入运行证据。

HYSYS 使用同样的运行时发现策略：版本化 `HYSYS.Application.*` → 无版本 `HYSYS.Application`。

因此，**只要未来 Aspen 版本继续注册兼容的 COM Automation Server，AspenOps 就会优先发现本机最新注册版本，而不需要先修改源码。**

但“能够发现并调用”与“经过某一版本认证”是两个概念。正式认证必须在装有目标 Aspen 版本、有效许可证和批准案例的 Windows 主机上运行真实资格测试。项目不会虚构这一证据。

```powershell
uv run aspenops doctor --probe
```

---

# 数理逻辑：AspenOps 到底在判定什么

## 1. 模拟器不是普通函数

稳态流程模拟本质上求解隐式非线性系统：

\[
\mathbf{F}(\mathbf{z},\mathbf{x};\boldsymbol{\theta})=\mathbf{0},
\]

其中：

- \(\mathbf{x}\)：外部操纵变量，例如温度、压力、回流比、塔板数；
- \(\mathbf{z}\)：Aspen 内部状态，例如相平衡、流股状态、设备内部变量；
- \(\boldsymbol{\theta}\)：物性方法、组分、反应参数和模型结构；
- \(\mathbf{F}\)：物料衡算、能量衡算、相平衡和单元操作方程。

AspenOps 将一次运行定义为事务：

\[
\mathcal{E}:\mathbf{x}
\rightarrow \text{validate}
\rightarrow \text{reset}
\rightarrow \text{write}
\rightarrow \text{solve}
\rightarrow \text{read}
\rightarrow \text{verify}
\rightarrow (\mathbf{y},\mathcal{S},\mathcal{D}),
\]

其中 \(\mathcal{S}\) 是分层状态，\(\mathcal{D}\) 是证据与诊断。

## 2. 结果有效性的五重门

AspenOps 不使用一个含糊的 `success=True`。最终有效性定义为：

\[
S_{valid}=
S_{transport}
\land S_{engine}
\land S_{convergence}
\land S_{constraints}
\land S_{balances}.
\]

分别表示：

- `communication_ok`：Worker 协议完整，响应与请求 ID 一致；
- `engine_ok`：Aspen 求解调用正常返回；
- `converged`：状态节点、错误信息和引擎状态没有给出失败证据；
- `feasible`：所有用户定义的工艺约束通过；
- `balance_residuals`：守恒残差在容差内。

只有这五层全部通过，`ok` 才为 `true`。

## 3. 守恒判据

对任意配置的守恒关系：

\[
r_b=\sum_{i=1}^{m}a_iq_i-q_{expected},
\]

绝对残差为：

\[
\varepsilon_{abs}=|r_b|,
\]

归一化残差为：

\[
\varepsilon_{rel}=
\frac{|r_b|}
{\max\left(\sum_i|a_iq_i|,q_{floor}\right)}.
\]

当绝对或相对判据足以证明残差可忽略时通过：

\[
\varepsilon_{abs}\le\tau_{abs}
\quad\lor\quad
\varepsilon_{rel}\le\tau_{rel}.
\]

采用“或”是为了避免微小流量由于分母接近零而被相对误差错误拒绝，同时也避免大流量只依赖宽松绝对误差。

## 4. 约束违反量

对不等式 \(g_j(\mathbf{x},\mathbf{y})\le 0\)，定义：

\[
v_j=\max(0,g_j).
\]

AspenOps 保存每个约束的实际值、阈值、容差与违反量，而不仅保存一个布尔值。该数据可直接用于 Deb feasibility rules、多目标优化、贝叶斯优化或代理模型训练。

## 5. 独立重复认证

同一模型和输入从独立模型副本重复运行 \(R\) 次。对任意输出 \(y_k\)：

\[
|y_k^{(r)}-y_k^{(0)}|\le\tau_{abs}
\quad\lor\quad
\frac{|y_k^{(r)}-y_k^{(0)}|}
{\max(|y_k^{(r)}|,|y_k^{(0)}|,1)}
\le\tau_{rel}.
\]

这能够发现：

- 隐藏热启动依赖；
- 模型状态污染；
- 缓存键错误；
- 随机初始化或求解器不稳定；
- 读取到旧结果；
- 自动化层非确定性。

---

# 高性能设计

## 1. 为什么持久 Worker 池比逐点启动快

朴素执行：

\[
T_{naive}\approx N(T_{start}+T_{open}+T_{solve}+T_{read}).
\]

AspenOps 持久 CasePool：

\[
T_{pool}\approx
W(T_{start}+T_{open})+
\frac{N_{unique}}{W}(T_{solve}+T_{verify})+
T_{IPC}+T_{schedule}.
\]

真正的加速来自：

- Aspen 只启动一次；
- 模型只打开一次；
- 每个点只跨一次 IPC；
- 相同物理请求在调度前去重；
- 可复现工况使用内容寻址缓存；
- 多个 Worker 使用私有模型并行；
- 到达点数或寿命阈值后自动回收 Worker，控制长时间 COM 泄漏。

## 2. 并发不是越大越好

有效 Worker 数为：

\[
W_{effective}=\min
\left(
W_{configured},
W_{license},
W_{memory},
W_{stability}
\right).
\]

AspenOps 明确把许可证席位放入并发上限：

```text
ASPENOPS_LICENSE_SLOTS=2
ASPENOPS_MAX_WORKERS=8
```

实际只启动 2 个 Worker。

推荐从 1 个 Worker 开始，使用真实模型测量：

- Aspen 启动与打开耗时；
- 单点平均与 P95 求解时间；
- 每个实例内存；
- 许可证等待；
- Worker 运行多少点后稳定性下降；
- 并发增加后的吞吐量拐点。

## 3. 动态任务领取

Aspen 工况耗时通常高度不均匀。固定把点平均切成 \(W\) 个块会造成长尾 Worker 拖慢全批次。AspenOps 使用共享任务队列：空闲 Worker 动态领取下一工况，从而降低 makespan。

## 4. 内容寻址缓存

缓存键不是“输入变量字典”这么简单，而是：

\[
K=H(
V_{runtime},
B,
H(M),
H(R),
Q_{physical}
),
\]

其中：

- \(V_{runtime}\)：AspenOps 运行时 Schema 与版本；
- \(B\)：后端类型；
- \(H(M)\)：模型文件 SHA-256；
- \(H(R)\)：语义注册表 SHA-256；
- \(Q_{physical}\)：去除标签后真正影响求解的请求。

因此：

- 模型改变，缓存自动失效；
- Tree Path 注册表改变，缓存自动失效；
- 运行时语义改变，缓存自动失效；
- `point_index`、显示名称和实验标签不会制造假缓存未命中。

默认只缓存通过的、从重初始化状态得到的结果。热启动结果不进入确定性缓存。

---

# 安全模型：让 Agent 有能力，但没有任意权力

## 语义注册表

Agent 发送：

```json
{
  "key": "stream.input.temperature",
  "identifiers": {"stream": "FEED"},
  "value": 95.0,
  "unit": "C"
}
```

项目注册表解析为候选路径：

```text
\Data\Streams\FEED\Input\TEMP\MIXED
\Data\Streams\FEED\Input\TEMP
```

每个语义变量声明：

- 读写权限；
- 原生单位和物理量维度；
- 下限、上限与整数约束；
- 必需标识符；
- 后端类型；
- 候选 Tree Path 或 HYSYS Spreadsheet locator；
- 验证状态与工程说明。

标识符只允许安全字符。反斜线、模板语法和路径穿越式输入会在调用 Aspen 之前被拒绝。

## HYSYS Spreadsheet Contract

HYSYS 对象模型广泛、复杂且版本敏感。AspenOps 1.0 默认采用项目拥有的 Spreadsheet 桥：

1. 工程师在 HYSYS case 内建立专用 Spreadsheet；
2. 将允许读取、写入和判定收敛的变量绑定到单元格；
3. 在注册表中定义 `spreadsheet` 与 `cell`；
4. Agent 只访问这些语义变量。

这比向 LLM 暴露完整 `Flowsheet.Operations`、流股对象和任意方法调用更可控，也更容易跨版本验证。

## 明确不提供

MCP Server 不提供：

- 任意 Shell；
- 任意 Python；
- VBA 执行；
- `eval`；
- 通用 `call_com_method`；
- 任意 Tree Path 写入；
- 全机 Aspen 进程终止；
- 自动覆盖源模型。

---

# 快速开始

## 跨平台控制平面验证

无需 Aspen：

```bash
git clone https://github.com/SUNHAOJUN22/AspenOps-Agent.git
cd AspenOps-Agent
uv sync --extra dev --extra agent

uv run aspenops demo
uv run aspenops benchmark --points 24 --workers 1,2,4
uv run aspenops certify examples/batch-request.example.json --repeats 3
```

完整质量门：

```bash
uv run ruff check .
uv run mypy src
uv run pytest --cov=aspenops_nexus --cov-report=term-missing
uv build
uv run python scripts/check_mcp.py
```

## Windows + Aspen Plus

```powershell
git clone https://github.com/SUNHAOJUN22/AspenOps-Agent.git
cd AspenOps-Agent
powershell -ExecutionPolicy Bypass -File scripts/setup_windows.ps1
```

`.env` 示例：

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
ASPENOPS_VISIBLE=0
```

诊断本机 Automation Server：

```powershell
uv run aspenops doctor --probe
```

验证请求而不启动 Aspen：

```powershell
uv run aspenops dry-run D:/AspenModels/request.json
```

运行并生成证据包：

```powershell
uv run aspenops run-batch D:/AspenModels/request.json `
  --output D:/AspenResults/results.json `
  --bundle D:/AspenResults/run-bundle.zip
```

验证证据包没有被篡改：

```powershell
uv run aspenops verify-bundle D:/AspenResults/run-bundle.zip
```

---

# 标准请求

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
        },
        {
          "key": "block.input.reflux_ratio",
          "identifiers": {"block": "COL1"},
          "value": 2.5,
          "unit": "1"
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
    },
    {
      "key": "block.output.reboiler_duty",
      "identifiers": {"block": "COL1"},
      "unit": "kW"
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
        },
        {
          "key": "waste.mass_flow",
          "identifiers": {"stream": "WASTE"},
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

---

# Codex 原生使用

仓库包含 `.codex/config.toml`。进入项目后：

```powershell
codex mcp list
```

推荐任务指令：

```text
只通过 AspenOps 操作 Aspen。
先调用 system_info，随后读取案例语义注册表并 dry-run。
将 200 点 Latin Hypercube DOE 提交为后台任务；不得构造原始 Tree Path。
仅把 communication_ok、engine_ok、converged、feasible 和守恒判据全部通过的点
纳入结果表。返回不可行点的违反量、运行证据包路径和模型/注册表哈希。
```

工具顺序：

```text
system_info
→ list_semantic_variables
→ dry_run_request
→ submit_batch
→ job_status
→ job_result
→ verify_evidence_bundle
```

---

# Claude Code 原生使用

仓库根目录包含 `.mcp.json`：

```powershell
claude mcp list
```

`CLAUDE.md` 定义了项目级操作契约。Claude Code 不应该自己生成 `win32com` 脚本绕过 AspenOps。

---

# 后台任务与耐久状态

长任务写入 SQLite WAL 作业库：

```text
pending → running → completed
                  ↘ failed
pending → cancelled
running + service restart → interrupted
```

任务拥有：

- `job_id`；
- 规范化请求哈希；
- 创建、开始、结束与更新时间；
- Worker owner；
- 取消请求；
- 结果与证据包位置；
- 失败原因。

服务重启后，遗留的 `running` 任务会被标记为 `interrupted`，不会静默伪装成成功。

---

# 证据包

每次运行可生成 ZIP：

```text
manifest.json
request.json
results.json
environment.json
README.txt
```

`manifest.json` 包含：

- AspenOps 版本和 Runtime Schema；
- 请求 SHA-256；
- 结果 SHA-256；
- 模型 SHA-256；
- 注册表 SHA-256；
- 结果数量；
- 全部工况是否通过。

这使工艺模拟从“某个人电脑上跑过一次”变成可以进入实验记录、模型治理、审计和 CI/CD 的可验证计算对象。

---

# DOE、优化与代理模型

项目内置：

- Latin Hypercube；
- bounded grid；
- nearest-neighbor ordering；
- 有界 `DE/best/1/bin` 差分进化；
- Deb-style feasibility ordering；
- 确定性随机种子。

推荐工作流：

```text
小规模真实 Aspen DOE
→ 检查失败区域与守恒
→ 训练带可行域分类器的代理模型
→ 在代理模型上进行大规模搜索
→ 将 Pareto / 最优候选返回 Aspen 复核
→ 独立重复认证
```

不要让强化学习或进化算法在没有缓存、超时、失败惩罚和许可证控制的情况下无限直接调用 Aspen。

---

# 测试与发布门禁

公共 CI 在 Python 3.11、3.12、3.13 上执行：

```text
Ruff
strict mypy
Pytest + coverage
wheel/sdist build
Mock end-to-end demo
MCP surface verification
```

真实 Aspen 通过单独的自托管 Windows 工作流认证：

```text
.github/workflows/windows-aspen-certification.yml
```

资格案例应满足：

- 非保密；
- 在 Aspen GUI 中已经稳定收敛；
- 输入输出范围覆盖典型工况；
- 注册表路径经 Variable Explorer 人工核验；
- 包含至少一个物料或能量守恒；
- 包含至少一个产品或设备约束；
- 可从独立模型副本重复运行；
- 记录目标 Aspen 版本、ProgID 和许可证环境。

---

# 诚实边界

AspenOps 1.0 当前明确支持：

- Aspen Plus 稳态案例的 COM 自动化；
- HYSYS 的安全 Spreadsheet Bridge；
- Codex / Claude Code 的本地 STDIO MCP；
- 后台批处理、缓存、并发、超时、验证、认证和证据。

它不宣称：

- 公共 Linux CI 已经运行真实 Aspen；
- 任意 Aspen 版本、任意模块、任意模型无需资格测试即可兼容；
- `Run2()` 返回即代表热力学和工程结果正确；
- HYSYS 全对象模型已经以统一方式封装；
- Aspen Dynamics、ACM、完整 PBE/动态模型已经由稳态后端原生覆盖；
- LLM 可以替代物性方法选择、反应机理、设备设计规范和工程审查。

这种边界不是缺点，而是可信工业软件必须具备的证据纪律。

---

# 仓库结构

```text
src/aspenops_nexus/
  compat.py                 最新注册 COM Server 的运行时发现
  registry.py               语义变量、单位、边界、路径防注入
  units.py                  显式工程单位代数
  worker.py                 spawn 进程、STA、协议关联、硬超时
  pool.py                   持久 CasePool、动态调度、回收、去重
  scheduler.py              SQLite WAL 耐久后台作业
  evaluation.py             五重状态、约束和守恒残差
  cache.py                  内容寻址结果缓存
  certification.py          独立重复认证
  provenance.py             防篡改运行证据包
  optimizer.py              约束感知差分进化
  design.py                 DOE 与工况排序
  mcp_server.py             窄接口 MCP Server
  backends/
    aspen_plus.py           Aspen Plus COM adapter
    hysys.py                HYSYS Spreadsheet adapter
    mock.py                 跨平台确定性测试后端

tests/                      单元、集成、故障边界与调度测试
examples/                   请求、注册表和 Mock 案例
docs/                       架构、性能、认证、安全和 Windows 部署
.github/workflows/           公共 CI 与真实 Aspen 自托管认证
```

---

# 许可证与专有数据

代码采用 Apache-2.0。

Aspen Plus、Aspen HYSYS、模型文件、物性数据库、供应商文档和许可证仍受各自条款约束。不要向公开仓库提交：

- 客户 `.bkp`、`.apw`、`.apwz`、`.hsc`；
- 专有动力学和物性参数；
- 许可证文件；
- 账号、Token、内部路径或网络信息；
- 包含商业工艺数据的证据包。

---

<div align="center">

## Let agents design the experiment. Let Aspen solve the physics. Let AspenOps enforce the truth.

**AspenOps 1.0 — deterministic process simulation for the agentic era.**

</div>
