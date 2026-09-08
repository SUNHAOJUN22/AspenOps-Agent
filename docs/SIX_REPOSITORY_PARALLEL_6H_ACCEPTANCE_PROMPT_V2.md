# SIX_REPOSITORY_PARALLEL_6H_ACCEPTANCE_V2

> 本文件是可直接交给代码代理、CI 编排器或人工验收团队执行的总控 Prompt。它补充 V1，重点解决 **current-main 精确绑定、六路真并行、六小时真实活动测试计时、README/双语视觉回写、失败闭环和机器回执**。

## 1. 总任务

在同一验收会话内并行维护、修复、测试并交付以下六个仓库：

1. `SUNHAOJUN22/AspenOps-Agent`
2. `SUNHAOJUN22/TsaoSciComputation`
3. `SUNHAOJUN22/TSAO-PROCESSING-SKILL`
4. `SUNHAOJUN22/ResinDB-Pro-by-SunHJ`
5. `SUNHAOJUN22/TsaoDFT_skill`
6. `SUNHAOJUN22/TsaoSciResearcher`

长期分支只允许 `main`。六个仓库必须同时启动，分别维护日志、失败队列、证据目录和判定；一个仓库失败不得取消其他仓库。

## 2. 不可降低的执行合同

```text
CODE_FIRST
CURRENT_MAIN_SHA_BOUND
EXACT_TREE_EVIDENCE
MATHEMATICS_MUST_MAP_TO_IMPLEMENTED_CODE
FINITE_NUMERICS_ONLY
STRICT_UNITS_AND_DIMENSIONS
NO_FABRICATION
NO_SILENT_FALLBACK
NO_SKIPPED_TESTS_AS_PASS
NO_THRESHOLD_DOWNGRADE
NO_SLEEP_TIME_AS_TEST_TIME
BILINGUAL_ZH_EN
CJK_SAFE_VISUALS
WINDOWS_LINUX_QUALIFIED
EXTERNAL_SOLVER_RESULTS_NOT_CLAIMED
AUTOMATIC_SCIENTIFIC_APPROVAL_FALSE
```

软件 PASS 只能证明仓库的软件、数值合同、文档和交付工件满足已声明门禁；不得据此声称 Aspen、Gaussian、VASP、Quantum ESPRESSO、CP2K、GROMACS、LAMMPS、OpenFOAM、实验或工业装置已完成外部科学资格。

## 3. 精确绑定 current-main

每个仓库在开始时执行：

```bash
git fetch origin main --prune
TESTED_SHA=$(git rev-parse origin/main)
git checkout --detach "$TESTED_SHA"
git diff --exit-code
git status --porcelain=v1
```

记录：repository、tested_sha、tree_hash、trigger_actor、workflow_run_id、run_attempt、runner_os、runtime、lockfile_hash、开始时间。

验收期间若 `origin/main` 发生变化：

```text
RESULT = STALE_MAIN
```

旧运行可以保留为归档证据，但不得成为新 HEAD 的 PASS。

## 4. 六路并行阶段

### 4.1 0–30 分钟：基线与分支

并行读取默认分支、全部远端分支、开放 PR、最新提交、永久 Actions、锁文件、版本、生产代码、测试、Schema、Worker、原生代码、文档和图片。生成每仓库 `BASELINE.json`。

非 `main` 分支按下列顺序处理：

1. 内容已包含于 `main`：删除；
2. 已合并 PR 的残留：删除；
3. 仅运输、诊断、一次性触发文件：关闭并删除；
4. 有未合并实质代码：比较、测试、合并或明确 BLOCK；
5. 最终重新查询，必须只剩 `main`。

### 4.2 30–120 分钟：代码、数学与安全审计

检查占位实现、裸异常、吞异常、动态执行、路径逃逸、命令注入、随机种子、资源泄漏、临时文件、线程/Worker 生命周期、重复解析、大数组复制、N+1 I/O、无界缓存、类型逃逸、Schema 漂移、Windows/Linux 差异、锁文件和 high/critical 漏洞。

建立公式到代码映射：

```text
公式 → 实现文件/函数 → 输入/输出单位 → 参数来源 → 算法
→ 收敛条件 → 适用域 → 失败模式 → 测试 → 证据等级
```

共同数值门：

\[
C_{finite}(x)=\mathbf 1_{x\in\mathbb R}\mathbf 1_{\neg\operatorname{Bool}(x)}\mathbf 1_{\operatorname{isfinite}(x)}
\]

\[
\lVert x_{k+1}-x_k\rVert\le\varepsilon_{abs}+\varepsilon_{rel}\lVert x_k\rVert
\]

\[
H=\operatorname{SHA256}(\text{code}\Vert\text{input}\Vert\text{method}\Vert\text{environment}\Vert\text{result})
\]

缺失单位、非有限值、奇异矩阵、未收敛、解析失败、越域或证据身份不完整必须 `BLOCK`/`HOLD`。

### 4.3 120–270 分钟：实施修复

修复优先级固定为：

```text
correctness → security → numerical stability → cross-platform
→ performance → tests → README → localized visuals → acceptance evidence
```

禁止删除失败测试、降低阈值、使用 `continue-on-error` 掩盖正式门、把异常变成静默 fallback、改写历史结果或宣传未实现功能。

## 5. 仓库专项门禁

### AspenOps-Agent

检查 Process IR、单位、DOF、循环/撕裂边、物料与能量衡算、约束、COM/Worker 所有权、取消与恢复、缓存、优化、许可证并发和证据包。

\[
OK=C_{comm}\land C_{engine}\land C_{conv}\land C_{finite}\land C_{constraint}\land C_{balance}
\]

外部状态保持 `PENDING_REAL_ASPEN_CERTIFICATION`。

### TsaoSciComputation

检查 calculation contract、不可变命令计划、可执行文件/输入哈希、资源准入、Parser、收敛、数值/物理等价、C ABI 和求解器探测。

\[
H_{bundle}=SHA256(B_{solver}\Vert B_{inputs}\Vert B_{env}\Vert B_{contract}\Vert B_{reference})
\]

第三方求解器保持 `EXTERNAL_HOLD`。

### TSAO-PROCESSING-SKILL

检查四个 Skill、Schema、canonical publication、DOPRI5、物料/能量衡算、动力学、群体矩、热力学、流变、Fisher、UQ、Wheel 和源码快照。

\[
\frac{d\mathbf N}{dt}=F_{in}\mathbf z-F_{out}\mathbf x+V\boldsymbol\nu^{\mathsf T}\mathbf r
\]

### ResinDB-Pro-by-SunHJ

执行 UTF-8、NFC、U+FFFD、mojibake、控制字符、三份 README、Markdown/HTML 图片、SVG XML/安全/字体/语言、ECharts `finished`、Canvas 非空、PNG、主题/语言切换、ResizeObserver 和 Worker 错误态检查。

\[
C_{figure}=C_{finite}\land C_{labeled}\land C_{finished}\land C_{nonblank}
\]

中文 README 只能引用中文主视觉，英文 README 只能引用英文主视觉；双语索引页可以同时引用二者。

### TsaoDFT_skill

检查 Kohn–Sham/SCF 合同、周期几何、三斜晶胞 minimum image、邻居表、Parser、能量/力/应力、方法指纹、引擎身份、数值等价与 L0–L3 等级。探测或模板不得升级为真实 DFT 结果。

### TsaoSciResearcher

检查路由、能力合同、量纲、证据三分、冲突台账、适用域、可辨识性、UQ、尺度桥、handoff、receipt、归档及 `automatic_approval=false`。

\[
G=\min(g_{quantity},g_{applicability},g_{evidence},g_{identifiability},g_{bridge})
\]

## 6. README 与双语设计图

基于当前代码生成或更新中英文 README，不得先画图后反推功能。每个语言版本包含：定位、架构、代码能力、数理合同、使用策略、安装、测试、证据边界、路线图和责任边界。

中文 README 使用中文 SVG；英文 README 使用英文 SVG。每张主视觉必须：

```text
viewBox="0 0 1600 900"
role="img"
非空 title 与 desc
无 script、事件处理器、foreignObject、外链字体和远程资源
显式 CJK/数学字体回退
2–4 条与代码对应的公式
明确 AI-assisted conceptual / not scientific data
```

所有文本按 UTF-8 写入并做 NFC 检查；出现 U+FFFD、mojibake、非法控制字符、缺图、空白图或语言串扰即失败。

## 7. 270–345 分钟：正式门禁与六小时活动测试

先完整运行各仓库永久 CI 等价门禁一次。随后在同一 immutable `TESTED_SHA` 上重复非变异、确定性的正式回归周期。

六小时定义为：

\[
T_{active}=\sum_{i=1}^{n}(t_{i,end}^{mono}-t_{i,start}^{mono})\ge21600\;s
\]

只累计真实测试命令执行的单调时钟时间。依赖安装、排队、artifact 上传、日志整理、`sleep` 和等待均不得计入。

由于单个 GitHub Actions job 有时限，允许拆成两个顺序阶段；阶段间必须传递并校验 `tested_sha`、`active_ns`、cycle count、失败摘要和证据哈希。任何周期失败立即使该仓库 `FAIL`，不得继续累积为 PASS。

每个仓库输出：

```text
artifacts/acceptance/<repo>/baseline.json
artifacts/acceptance/<repo>/gate-results.json
artifacts/acceptance/<repo>/active-soak-ledger.jsonl
artifacts/acceptance/<repo>/formula-to-code-map.md
artifacts/acceptance/<repo>/readme-visual-audit.json
artifacts/acceptance/<repo>/final-verdict.json
```

## 8. 345–360 分钟：失败闭环

获取完整日志，定位第一个真实根因；实施最小修复；先跑聚焦测试，再跑受影响的完整门禁。到达时限仍未全绿时保留 `BLOCKED`，列明命令、返回码、日志、SHA 和剩余风险，不得用“基本通过”替代机器结果。

## 9. 自动执行与账本

由各仓库默认分支上的持久 workflow 接收同一所有者命令：

```text
/run-current-main-six-hour-v2
```

workflow 必须限制触发者为仓库所有者，读取触发瞬间 `main`，在 issue 中写入 `RUNNING`、run URL、tested SHA、目标活动纳秒数；结束后写入 `PASS`、`FAIL` 或 `STALE_MAIN`。聊天或人工报告在运行结束前只能写 `TRIGGERED/RUNNING`，不得提前宣布 PASS。

## 10. 最终判定

\[
MERGE=code\land math\land tests\land docs\land visuals\land security\land exactTree
\]

最终生成六仓库总报告、机器 JSON、公式映射、测试矩阵、分支清理、README/视觉审计和外部资格边界。逐仓库给出当前 main SHA、run ID、测试数、覆盖率、漏洞、README/图状态、分支/PR 状态与 `PASS/BLOCKED/STALE_MAIN`；不得使用模糊结论。