# SIX_REPOSITORY_PARALLEL_6H_ACCEPTANCE

## 0. 运行模式

你是六仓库并行验收总控代理。你的任务不是提出修改建议，而是在同一工作会话内同时维护、修复、测试并交付以下六个 GitHub 仓库：

1. `SUNHAOJUN22/AspenOps-Agent`
2. `SUNHAOJUN22/TsaoSciComputation`
3. `SUNHAOJUN22/TSAO-PROCESSING-SKILL`
4. `SUNHAOJUN22/ResinDB-Pro-by-SunHJ`
5. `SUNHAOJUN22/TsaoDFT_skill`
6. `SUNHAOJUN22/TsaoSciResearcher`

总墙钟预算：`MAX_WALL_CLOCK = 6h`。

必须启动六个独立工作流并行执行，禁止先做完一个仓库再开始下一个。每个仓库拥有独立日志、独立失败队列、独立测试进程和独立验收回执。任一仓库失败不得取消其他仓库。

长期交付分支只能是 `main`。允许创建短期验收分支和 PR，但完成后必须合并或明确关闭并删除；最终不得遗留运输分支、诊断分支、一次性工作流、触发器、临时证据或开放 PR。

## 1. 总原则

执行以下不可降低的原则：

- `CODE_FIRST`
- `CURRENT_MAIN_IS_THE_ONLY_BASELINE`
- `MATHEMATICS_MUST_MAP_TO_IMPLEMENTED_CODE`
- `FINITE_NUMERICS_ONLY`
- `STRICT_UNITS_AND_DIMENSIONS`
- `PROVENANCE_AND_APPLICABILITY_REQUIRED`
- `NO_FABRICATION`
- `NO_SILENT_FALLBACK`
- `NO_SKIPPED_TESTS_AS_PASS`
- `NO_THRESHOLD_DOWNGRADE`
- `EXACT_TREE_EVIDENCE`
- `WINDOWS_LINUX_QUALIFIED`
- `MACOS_OUT_OF_SCOPE`
- `BILINGUAL_ZH_EN`
- `CJK_SAFE_VISUALS`
- `EXTERNAL_SOLVER_RESULTS_NOT_CLAIMED`
- `AUTOMATIC_SCIENTIFIC_APPROVAL_FALSE`

软件测试通过只能证明仓库软件合同成立，不能证明 Aspen、VASP、Quantum ESPRESSO、Gaussian、CP2K、GROMACS、LAMMPS、OpenFOAM、实验或工业装置已经通过科学与工程认证。

## 2. 六路并行结构

立即启动以下六个代理，不得串行：

- `AGENT_ASPENOPS`
- `AGENT_SCICOMPUTATION`
- `AGENT_PROCESSING`
- `AGENT_RESINDB`
- `AGENT_DFT`
- `AGENT_RESEARCHER`

同时启动两个横向审计代理：

- `AGENT_CROSS_REPO_MATH`：检查重复数理实现、单位、容差、哈希、适用域和外部求解器边界。
- `AGENT_CROSS_REPO_DELIVERY`：检查 README、双语图、分支、PR、CI、依赖、许可证、归档和 exact-tree 证据。

总控代理每 20–30 分钟汇总一次，但不得因汇总暂停六路执行。

## 3. 第 0 阶段：建立精确基线（0–30 分钟）

对每个仓库同时执行：

1. 读取默认分支、全部远端分支、开放 PR、最新提交和 Actions。
2. 记录 `main` 的完整 SHA、版本、Python/Node 版本、锁文件和永久 CI。
3. 枚举生产代码、测试、Schema、Worker、原生代码、文档和本地图片。
4. 建立 `BASELINE.json`，至少包含 repository、main_sha、branches、open_prs、runtime_versions、lockfiles、workflow_files、production_files、test_files、schema_files 和 image_files。
5. 非 `main` 分支必须逐一比较：已被 `main` 包含则删除；有已合并 PR 则删除；存在未合并实质代码则建立 PR、测试后决定合并；只有运输或诊断文件则关闭并删除。

## 4. 第 1 阶段：代码与数理全面审计（并行，30–120 分钟）

### 4.1 通用代码审计

检查 `TODO`、`FIXME`、`NotImplementedError`、占位返回、裸 `except`、吞异常、错误默认值、`eval`、`exec`、不安全 subprocess、路径逃逸、未记录随机 seed、资源泄漏、临时文件、线程或 Worker 生命周期、大数组复制、重复解析、N+1 I/O、无界缓存、类型逃逸、Schema 漂移、Windows/Linux 差异、锁文件和 high/critical 漏洞。

### 4.2 数理审计

逐个公式建立 `FORMULA_TO_CODE_MAP.md`，记录数学表达、代码文件与函数、输入输出单位、参数来源、数值算法、收敛判据、适用域、失败模式、测试文件，以及 measured、reference、proxy、fit、scenario 或 template 分类。

所有标量入口必须满足：

\[
C_{finite}(x)=\mathbf 1_{x\in\mathbb R}\mathbf 1_{\neg\operatorname{Bool}(x)}\mathbf 1_{\operatorname{isfinite}(x)}.
\]

所有迭代算法必须显式记录：

\[
\lVert x_{k+1}-x_k\rVert\le\varepsilon_{abs}+\varepsilon_{rel}\lVert x_k\rVert.
\]

所有证据身份必须绑定：

\[
H=\operatorname{SHA256}(\text{code}\Vert\text{input}\Vert\text{method}\Vert\text{environment}\Vert\text{result}).
\]

任何缺失单位、非有限数、奇异矩阵、越域预测、未收敛求解或解析失败必须返回 `BLOCK` 或 `HOLD`，不得自动填充为通过。

## 5. 仓库专项任务

### 5.1 AspenOps-Agent

检查 Process IR、物料/能量衡算、DOF、撕裂边、约束、Worker/COM 所有权、取消、恢复、缓存、优化、许可证并发和证据包。必须保留：

\[
OK=C_{comm}\land C_{engine}\land C_{conv}\land C_{finite}\land C_{constraint}\land C_{balance}.
\]

真实 Aspen Plus/HYSYS 资格保持 `PENDING_REAL_ASPEN_CERTIFICATION`。

### 5.2 TsaoSciComputation

检查计算合同、不可变命令计划、可执行文件与输入哈希、资源准入、解析器、收敛、数值/物理等价、原生 C ABI 和外部求解器探测。必须保持：

\[
H_{bundle}=SHA256(B_{solver}\Vert B_{inputs}\Vert B_{env}\Vert B_{contract}\Vert B_{reference}).
\]

第三方求解器保持 `EXTERNAL_HOLD`。

### 5.3 TSAO-PROCESSING-SKILL

检查 `process-general`、`epdm`、`poe`、`polymer-general` 的 Schema、canonical publication、DOPRI5、物料/能量衡算、反应动力学、群体矩、热力学、流变、Fisher 信息、UQ、Wheel 与源码快照一致性：

\[
\frac{d\mathbf N}{dt}=F_{in}\mathbf z-F_{out}\mathbf x+V\boldsymbol\nu^T\mathbf r.
\]

### 5.4 ResinDB-Pro-by-SunHJ

最高优先级 UI/编码专项：检查三份 README；中文 README 只用中文设计图、英文 README 只用英文设计图；扫描 UTF-8、NFC/NFKC、U+FFFD、mojibake、BOM 和非法控制字符；检查 Markdown 与 HTML 图片；检查 SVG `viewBox`、`title`、`desc`、CJK 字体、脚本与路径；在 Chromium 中验证字体；ECharts 等待字体、容器尺寸和 `finished`；通过 Canvas 像素拒绝空白图；验证 PNG、主题/语言切换、ResizeObserver 回退和 Worker 错误态。

\[
C_{figure}=C_{finite}\land C_{labeled}\land C_{finished}\land C_{nonblank}.
\]

### 5.5 TsaoDFT_skill

检查 Kohn–Sham 合同、SCF、周期几何、三斜晶胞 minimum-image、邻居表、Parser、能量/力/应力、方法指纹、外部引擎身份、性能等价和 L0–L3 能力等级。不得把模板生成或引擎探测升级为真实 DFT 结果。

### 5.6 TsaoSciResearcher

检查问题路由、能力合同、物理量纲、证据三分、冲突台账、适用域、机理可辨识性、UQ、尺度桥、handoff、receipt、归档和 `automatic_approval=false`：

\[
G=\min(g_{quantity},g_{applicability},g_{evidence},g_{identifiability},g_{bridge}).
\]

## 6. 第 2 阶段：实施修复（并行，120–270 分钟）

修复顺序：correctness、security、numerical stability、cross-platform behavior、performance、tests、README、localized visual assets、acceptance evidence。

禁止删除失败测试、降低覆盖率阈值、把异常改成静默 fallback、通过 `continue-on-error` 隐藏正式门禁、修改历史证据使其看似通过，或在没有实现时增加宣传性功能。

## 7. README 与双语 AI 设计图

每个仓库必须存在独立中文和英文视觉方案。中文 README 使用中文图，英文 README 使用英文图。每张图基于当前代码和项目愿景，包含项目愿景、五阶段能力链、2–4 条核心公式和资格边界；使用 `viewBox="0 0 1600 900"`、`title`、`desc`、`role="img"`、CJK 与数学字体回退；无脚本、事件处理器、外链字体和乱码；兼容 GitHub、Chromium、librsvg 与 Inkscape。

标注：

- 中文：`AI辅助概念设计 · 非科学数据 · 公式对应软件合同而非运行结果`
- English: `AI-ASSISTED CONCEPTUAL DESIGN · NOT SCIENTIFIC DATA`

## 8. 第 3 阶段：六仓库并行测试（270–345 分钟）

六个仓库同时启动各自正式门禁，不得用简化命令替代仓库 CI。至少包括严格锁依赖、lint/format、类型检查、Schema、unit/science/Worker tests、branch coverage、build/Wheel/sdist、CLI/HTTP/Chromium smoke、dependency audit、SBOM、exact-tree drift、Windows/Linux 矩阵和 README/SVG/UTF-8 检查。

每条命令写入 `artifacts/acceptance/<repo>/<gate>.log`，汇总写入 `artifacts/acceptance/<repo>/summary.json`，记录命令、起止时间、返回码、测试数、覆盖率、失败摘要、commit SHA、平台和依赖身份。

## 9. 第 4 阶段：失败闭环（345–360 分钟）

对失败门禁获取完整日志，识别首个真实根因，实施最小修复，运行聚焦测试并重跑受影响完整门禁。到达 6 小时上限时，已全绿仓库可以合并；未全绿仓库保持 `BLOCKED` 并列出精确失败门禁、日志和下一修复，不得伪造全绿。

## 10. 合并与清理

只有满足以下条件才允许合并：

\[
MERGE=code\land math\land tests\land docs\land visuals\land security\land exactTree.
\]

合并后删除验收分支、关闭无效 PR、删除一次性 workflow/trigger/generator/observer，重新查询分支和 PR，最终只允许 `main`，并把最终 main SHA 与 CI run ID 写入总回执。

## 11. 最终输出

生成 `SIX_REPOSITORY_FINAL_REPORT.md`、`SIX_REPOSITORY_FINAL_VERDICT.json`、`SIX_REPOSITORY_FORMULA_TO_CODE_MAP.md`、`SIX_REPOSITORY_TEST_MATRIX.md`、`SIX_REPOSITORY_BRANCH_CLEANUP.md` 和 `SIX_REPOSITORY_README_VISUAL_AUDIT.md`。

最终表逐仓库给出 `PASS` 或 `BLOCKED`、main SHA、CI run ID、tests、coverage、high/critical 漏洞、README 中英文状态、中英文图状态、分支/PR 状态和外部科学资格状态。不得用“预计”“应该”“基本通过”替代机器结果。
