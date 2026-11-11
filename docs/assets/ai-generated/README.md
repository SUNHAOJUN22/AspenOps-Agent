# 完整 AI 示意图 / Complete AI schematics

[中文主 README](../../../README.md) · [English main README](../../../README.en.md) · [历史图集 / Historical gallery](../README.md)

## 来源与用途 / Origin and purpose

本目录四幅当前科学示意图均通过真实 `image_gen.imagegen` 调用生成，保存完整原始 PNG；没有程序化几何绘图、文本覆盖、裁切、拼接或二次缩放。三个仓内图分别独立生成，七仓图由本轮共同生成任务提供。图像内可见 AI 生成标记，它们只解释软件结构、公式和工作流，不是测量数据、商业求解器输出或工程认证。

All four current figures were generated through actual `image_gen.imagegen` calls. They are complete original PNGs without programmatic drawing, text overlays, cropping, compositing or resizing. Each local figure has a separate generation call; the seven-repository figure comes from the shared generation task. Visible AI labels distinguish explanatory imagery from measurements, licensed solver output and engineering qualification.

[完整提示词 / Exact prompts](prompts.json) and [字节身份与审阅记录 / Identity and review records](manifest.json) preserve the original tool output paths, hashes, actual dimensions and review notes. The tool returned no model identifier, so the field is `null`. Generation times are reported in Asia/Shanghai using original output-file timestamps; this basis is explicit, rather than presented as a tool-supplied timestamp.

## 当前图像 / Current figures

| Figure | Actual pixels | SHA-256 of original bytes |
|---|---:|---|
| [architecture](architecture.png) | 1672 × 941 | `454469d6f8dffce2c7a26391f7bc779edc65179d8433a071a1162ba2b1a7e1e2` |
| [algorithm](algorithm.png) | 1672 × 941 | `9b34c593319b0c34558842d5c22470e7b6f1bad10a98b88131629d442933098c` |
| [roadmap](roadmap.png) | 1672 × 941 | `0acb581b0530bba0ec7b5f9409c0c7a46bc436d85df978c3a02aa78146cab12e` |
| [seven-repo-roadmap](seven-repo-roadmap.png) | 1672 × 941 | `96972f1b0966151abc38c9d784ac30cef25335a17a45bab636f2d70382405016` |

## 科学与实现边界 / Scientific and implementation boundaries

- **Architecture:** the capacity rule is the minimum of requested workers, configured maximum and declared license slots. The software does not discover licensing entitlement. Valid process IR does not authorize arbitrary simulator code. DWSIM, IDAES and Modelica/FMI execution adapters remain planned.
- **Algorithm:** search candidates are bounded but are not guaranteed feasible. The normalized objective, feasibility ordering, differential-evolution mutation and complete-generation evaluation budget map to the current implementation. Balance terms share a common unit; the scale excludes the target magnitude. Finite-value/domain/underflow checks precede the implemented absolute **OR** relative tolerance rule.
- **Local route:** every required validity gate must pass. Retained diagnostics, SHA-256 integrity and optional signatures do not establish real engineering validity on their own. Licensed Windows execution, fixed models, Golden Cases and human acceptance remain required.
- **Seven-repository route:** dotted links are proposed handoffs among independent repositories. Canonical equations apply to equilibrium at fixed N, V, T with T > 0. They provide theoretical context, not an implemented AspenOps partition-function solver or the sampling distribution of its optimizer.

三个仓内图逐张审阅；共享总路线由共同任务审阅。文字、公式和条件以[中文实现指南](../../implementation-guide.zh-CN.md)、[English implementation guide](../../implementation-guide.en.md)及链接到的源代码为精确依据。图像属于说明性材料，不能替代这些可审查定义。

All prior deterministic SVG assets remain byte-preserved in the [historical gallery](../README.md). Historical test or acceptance graphics do not certify the current source revision. Original SVG safety and maintenance checks remain applicable.
