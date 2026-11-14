# 当前 AI 示意图与历史图集 / Current AI schematics and historical gallery

[中文 README](../../README.md) · [English README](../../README.en.md) · [验收合同 / Acceptance](../../README_ACCEPTANCE.md)

本页是四幅当前原生 AI 图像的入口及旧图追溯索引。四幅 PNG 均由图像生成工具完整生成，未用代码绘图或文字覆盖；英文图内标签由中英文图注解释。图像说明软件关系和科学背景，不提供测量、真实模拟器执行或工程资格证据。

This index separates four current native AI schematics from retained historical assets. Every current PNG is a complete imagegen raster without programmatic drawing or text overlays. Shared English labels have bilingual explanations. These figures describe software and scientific context; they do not establish measurements, real-engine execution or engineering qualification.

## 当前图像 / Current figures

### 1. 执行架构 / Execution architecture

![AI-generated architecture: intent, governed execution, isolated workers and evidence / AI 生成的意图、执行、隔离与证据架构](ai-generated/architecture.png)

意图通过声明检查后进入唯一运行时；每个 Worker 使用私有模型，结果须逐点核验。开放反应衡算是物理背景，不是软件自行提供的物性模型。

Intent passes declared checks before reaching the single runtime. Workers own private models; results require per-point acceptance. Open-reaction balances provide physical context, not an internally implemented property model. [Source / 实现](../../src/aspenops_nexus/pool.py)

### 2. 数值与搜索 / Numerics and search

![AI-generated algorithm: dimensional observations, normalized objectives, bounded search and acceptance / AI 生成的数值与有界搜索算法](ai-generated/algorithm.png)

单位转换、目标归一化、预算与容差应按 README 的精确文本读取。搜索终点是待核验候选；DE 种群不是 Boltzmann 系综。

Read the precise unit, normalization, budget and tolerance definitions in the main README. Search yields a scoped candidate; DE populations are not Boltzmann ensembles. [Optimizer / 优化器](../../src/aspenops_nexus/optimizer.py) · [Acceptance / 接受门](../../src/aspenops_nexus/evaluation.py)

### 3. 简洁技术路线 / Concise technical route

![AI-generated route: discovery, binding, dry run, queued execution and evidence verification / AI 生成的简洁技术路线](ai-generated/roadmap.png)

遵循 `system_info` → `list_semantic_variables` → `dry_run_request` → `submit_batch` → `job_status` / `job_result` → `verify_evidence_bundle`。图中范围符号由实际模型声明，不是通用温度或压力许可。

Follow the ordered tool sequence above. Symbolic bounds come from the actual model, not universal permitted temperature or pressure ranges. [MCP contract / MCP 合同](../../src/aspenops_nexus/mcp_server.py)

### 4. 七仓总路线 / Seven-repository route

![AI-generated seven-repository overview: proposed handoffs and physical context / AI 生成的七仓建议交接与物理背景总路线](ai-generated/seven-repo-roadmap.png)

七仓独立，虚线交接尚非统一运行时。正则系综、过渡态理论和协方差近似是有条件的科学背景；README 定义本仓实际实现与未实现边界。

Repositories remain independent; dashed handoffs are proposed. Canonical ensembles, transition-state theory and covariance approximations have explicit scientific assumptions and are not evidence of implemented integration. The README defines this repository's implementation boundary.

[精确提示词、来源及 SHA-256 / Exact prompts, provenance and SHA-256](ai-generated/README.md)

## 历史工程图 / Historical engineering figures

以下二十三幅确定性 SVG 以普通链接保留，继续接受原安全、可访问性及实现标记检查。它们不属于本轮 AI 图像，不证明当前提交通过测试。历史文件的布局规则与当前 PNG 分开维护。

These twenty-three deterministic SVGs remain ordinary links, governed by their original safety, accessibility and implementation-marker tests. They are not current AI-generated rasters or proof of qualification for the current commit.

| 主题 / Topic | 历史链接 / Historical links |
|---|---|
| 架构与入口 / Architecture and interfaces | [控制面 / Control plane](readme/hero-architecture.svg) · [Agent stages](readme/agent-pipeline.svg) · [CLI / MCP](readme/cli-mcp-workflow.svg) · [MCP lifecycle](readme/mcp-runtime-lifecycle.svg) |
| 模型与权限 / Models and authority | [Process Intent](readme/process-intent-ir.svg) · [Backend capabilities](readme/backend-capabilities.svg) · [Adapter conformance](readme/adapter-conformance.svg) · [Policy / paths](readme/policy-path-safety.svg) |
| 执行与恢复 / Execution and recovery | [COM isolation](readme/com-isolation.svg) · [Worker ownership](readme/worker-ownership-recycle.svg) · [Scheduler lifecycle](readme/scheduler-lifecycle.svg) · [Durable paths](readme/durable-path-portability.svg) |
| 数值与性能 / Numerics and performance | [Validity gates](readme/validity-gates.svg) · [Optimization lifecycle](readme/optimization-lifecycle.svg) · [Cache / singleflight](readme/cache-singleflight.svg) · [Startup paths](readme/cold-warm-startup.svg) · [Performance measurement](readme/performance-hotspot-map.svg) |
| 证据与资格 / Evidence and qualification | [Evidence chain](readme/evidence-chain.svg) · [Evidence integrity](readme/evidence-integrity.svg) · [Test matrix](readme/test-matrix.svg) · [Licensed certification](readme/licensed-certification.svg) |
| 用途与规划 / Uses and planning | [Industrial scenarios](readme/industrial-scenarios.svg) · [Historical roadmap](readme/roadmap.svg) |

### 历史验收与其他版本 / Earlier acceptance and versions

- [Delivery acceptance](ai/delivery-acceptance.svg) · [Mathematical contracts](ai/mathematical-contracts.svg) · [Native failure isolation](ai/native-failure-isolation.svg) · [Warm-start trajectory](ai/warm-start-trajectory.svg)
- [Chinese hero](readme-vnext/hero.zh-CN.svg) · [English hero](readme-vnext/hero.en.svg)
- [Chinese architecture](atlas-v2/architecture-zh.svg) · [English architecture](atlas-v2/architecture-en.svg) · [Acceptance map](acceptance/final-acceptance-map.svg)
- [Earlier Chinese AI bitmap](vision-zh.png) · [Earlier English AI bitmap](vision-en.png)

旧位图保留来源身份，旧 SVG 保留技术合同；主 README 和本页仅嵌入四幅当前原生 AI PNG。/ Earlier bitmaps retain provenance and SVGs retain technical contracts; only the four current native AI PNGs are embedded here and in the main READMEs.
