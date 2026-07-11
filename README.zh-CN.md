# AspenOps Agent 1.0

**一个面向 Aspen Plus 的版本自适应、进程隔离、可测试自动化运行时。**

> Agent 负责任务规划；Aspen Plus 负责热力学与流程方程；AspenOps 负责权限、单位、执行、收敛、物理可行性和审计证据。

[English README](README.md) · [系统架构](docs/architecture.md) · [Windows 部署](docs/windows-setup.md) · [数值方法](docs/numerical-methods.md) · [安全边界](docs/security.md)

## 1. 重新定义边界

v1.0 只对 **Aspen Plus 稳态流程模拟自动化**负责，不再把尚未实现或未经实机验证的能力写进宣传：

- 不声称已经支持 HYSYS；
- 不声称已经支持 Aspen Custom Modeler 或 Aspen Dynamics；
- 不开放任意 VBA、Python、Shell 或通用 COM 反射调用；
- 不默认允许 Agent 任意拼接 Aspen Tree 路径；
- 不声称公共 Linux CI 已经测试真实 Aspen；
- 不把“COM 调用返回”“Aspen 收敛”“结果物理合理”混成一个成功状态。

这使工程能力、README 承诺和测试证据保持一致。

## 2. 核心架构

```text
Codex / Claude Code / MCP 客户端 / Python 应用
                         │ 窄接口、强类型
                         ▼
┌─────────────────────────────────────────────┐
│ SessionManager                              │
│ 目录白名单 · 会话生命周期 · JSONL 审计      │
└──────────────────────┬──────────────────────┘
                       │ 单次批量 IPC
                       ▼
┌─────────────────────────────────────────────┐
│ Spawned Worker                              │
│ 一个进程 = 一个 COM apartment = 一个 Aspen │
│ 语义注册表 · 单位 · 边界 · 回滚 · 路径缓存  │
└──────────────────────┬──────────────────────┘
                       ▼
┌─────────────────────────────────────────────┐
│ Aspen Plus Automation Server                │
│ 本机注册版本 · 流程求解 · 物性与设备模型    │
└─────────────────────────────────────────────┘
```

关键不变量：真实 Aspen COM 对象只存在于创建它的 Windows 子进程和 STA apartment 内，不跨线程共享、不跨进程序列化。

## 3. 为什么能适配新 Aspen 版本

AspenOps 不把某一个 `Apwn.Document.41.0` 写死为唯一入口，而是：

1. 支持运维人员通过 `ASPENOPS_PROGID` 显式固定版本；
2. 同时扫描 Windows 64 位和 32 位注册表中的 `Apwn.Document.*`；
3. 解析数字版本并从高到低尝试；
4. 使用 `DispatchEx` 创建独立实例；
5. 最后回退到无版本 `Apwn.Document`；
6. 输出实际创建成功的 ProgID 和 Aspen 暴露的版本属性。

```powershell
uv run aspenops doctor --probe
```

这里的逻辑是“以目标机器真实注册的 Automation Server 为准”，而不是猜测 Aspen 市场版本编号。任何新版本只有在持证 Windows 节点上跑过真实集成测试，才算完成验证。

## 4. 高效能操作 Aspen

低效做法是每个点都启动 Aspen、打开模型、求解、退出：

\[
T_{naive}\approx N(T_{start}+T_{open}+T_{solve})
\]

AspenOps 的 CasePool 为每个 Worker 建立私有模型副本，只打开一次，连续计算多个工况：

\[
T_{pool}\approx W(T_{start}+T_{open})+\frac{N}{W}T_{solve}+T_{IPC}
\]

实现包括：

- 持久 Aspen Worker；
- 每个 Worker 独立模型副本，避免并发写同一个文件；
- 每个操作点只进行一次 IPC：批量写入 -> Reinit -> Run -> 批量读取；
- 第一次找到正确 Aspen 路径后缓存；
- DOE 点按邻近关系排序，减少相邻工况跳跃；
- 超时只终止 AspenOps 自己的 Worker，不执行可能误杀别人 Aspen 会话的全局 `taskkill`；
- Worker 数量受配置、许可证、内存和稳定实例数共同约束。

## 5. 语义节点与安全写入

Agent 不直接写：

```text
\Data\Streams\FEED\Input\TEMP\MIXED
```

而是提交：

```json
{
  "key": "stream.input.temperature",
  "identifiers": {"stream": "FEED"},
  "value": 95.0,
  "unit": "C"
}
```

注册表定义候选路径、读写权限、物理量、默认单位、上下限、整数约束和验证状态。写入前完成：

1. 语义键白名单校验；
2. 标识符格式校验，阻止路径注入；
3. 读写权限校验；
4. 量纲一致性和单位换算；
5. 工程上下界校验；
6. 候选路径解析与缓存；
7. 批量写入；
8. 任一写入失败时按已保存原值逆序回滚。

Aspen Tree 路径会随模型、模块、规格方式和版本变化。仓库自带路径只作为候选模板，项目实施时必须依据 Variable Explorer 建立项目专用注册表。

## 6. 数理自洽

Aspen 求解：

\[
\mathbf F(\mathbf z,\mathbf x;\boldsymbol\theta)=\mathbf 0
\]

AspenOps 外层评价：

\[
\mathbf x\rightarrow\text{校验}\rightarrow\text{Aspen solve}
\rightarrow(\mathbf y,s,\boldsymbol\varepsilon)
\]

其中 \(s\) 为收敛状态，\(\boldsymbol\varepsilon\) 为约束和守恒残差。

守恒残差：

\[
r_b=\sum_i a_iq_i,
\qquad
\varepsilon_b=\frac{|r_b|}{\max(\sum_i|a_iq_i|,q_{min})}
\]

优化采用 Deb 可行性排序：

1. 可行解无条件优于不可行解；
2. 可行解之间比较目标值；
3. 不可行解之间比较总违反量；
4. Aspen 不收敛点以无穷违反量处理，不会被误判成“低目标值好点”。

包含：Latin Hypercube、Halton、随机和网格 DOE；安全 AST 表达式；质量/能量闭合；自适应连续求解；有界 `DE/best/1/bin` 差分进化。

## 7. 安装与验证

### 不需要 Aspen 的完整 Mock 验证

```bash
git clone https://github.com/SUNHAOJUN22/AspenOps-Agent.git
cd AspenOps-Agent
uv sync --extra dev --extra agent
uv run ruff check .
uv run mypy src/aspenops
uv run pytest
uv build
uv run aspenops demo
```

### Windows 真实 Aspen Plus

```powershell
uv sync --extra windows --extra dev
uv run aspenops doctor --probe
uv run aspenops run-case "D:\AspenModels\case.bkp" --timeout-s 1200
```

### MCP

```powershell
uv sync --extra windows --extra agent
$env:ASPENOPS_ALLOWED_ROOTS = "D:\AspenModels;D:\AspenResults"
uv run aspenops-mcp
```

MCP 只提供 9 个窄工具：系统信息、打开/关闭会话、批量读写、Reinit、Run、诊断和保存。没有任意执行代码接口。

## 8. 自动测试证据

当前 v1.0.0 本地质量门：

- Ruff 全通过；
- 22 个源码模块严格 mypy 全通过；
- 34 项测试通过；
- 1 项真实 Aspen 集成测试因当前环境不是持证 Windows 节点而按条件跳过；
- 跨平台可执行模块覆盖率 86.75%；
- 最终文档完成后再次构建 wheel、sdist 和运行 Demo。

GitHub Actions 在 Python 3.11、3.12、3.13 上重复执行。真实 Aspen 由独立的自托管 Windows 工作流验证。

## 9. 适用于 EPDM/聚合工艺时必须注意

当前后端是稳态 Aspen Plus 自动化。半连续 EPDM 中“催化剂和 ENB 初始加入、乙烯和丙烯持续进料”的过程本质上是动态质量、能量、催化剂活性和分子量分布演化问题。不能用一个稳态点冒充完整批次轨迹。

可选路线：

- 外部 Python ODE/PBE + Aspen 物性/单点流程评价；
- Aspen Custom Modeler；
- Aspen Dynamics；
- 将多个时间切片转化为受控准稳态序列，并明确其近似前提。

详见 [docs/epdm-semi-batch.md](docs/epdm-semi-batch.md)。

## 10. 已知边界

- 真实 Aspen 只能在 Windows、已安装 Aspen Plus、具备许可证时验证；
- 公共 CI 不可能证明某一商业 Aspen 补丁版本的真实行为；
- HYSYS、ACM、Dynamics 需要独立适配器与独立测试；
- 生产前必须验证项目专用节点路径、单位集和规格模式；
- 不提交客户模型、许可证、私有动力学参数或 Aspen 专有文档。
