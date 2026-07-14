# AspenOps 状态机规范

本文件对应 `src/aspenops_nexus/state_machines.py`。状态名使用大写稳定枚举；重复提交同一目标状态属于显式幂等操作，不创建新的状态转换。任何未列出的跨状态转换必须失败关闭。

## 通用规则

- 转换必须绑定对象 ID、当前版本、操作者、时间戳、correlation ID 与证据引用。
- 数据库写入使用 `WHERE current_state=? AND version=?` 或等价原子条件。
- 终态不可被普通业务调用改写。
- crash recovery 只能依据持久化 owner/lease/heartbeat；进程启动不得无条件重写其他实例的活动状态。
- 同一转换的幂等重放返回原结果，不重复触发 Aspen、审批或证据发布。
- 禁止将 Python 函数正常返回解释为 Aspen 收敛，禁止将收敛解释为物理认证。

## Job

初态：`PENDING`。

```text
PENDING → CLAIMED → RUNNING → SUCCEEDED
   │          │          ├→ FAILED
   │          │          ├→ CANCELLED
   │          │          ├→ TIMED_OUT
   │          │          └→ INTERRUPTED
   │          ├→ FAILED | CANCELLED | TIMED_OUT | INTERRUPTED
   └→ CANCELLED
```

前置条件：claim 必须由数据库单条原子操作完成，并写入 owner 与 lease；`CLAIMED→RUNNING` 仅允许当前 owner；成功发布要求 `RUNNING`、owner 匹配、未请求取消。终态为 `SUCCEEDED/FAILED/CANCELLED/TIMED_OUT/INTERRUPTED`。lease 到期仅将活动任务恢复为 `INTERRUPTED`，不得覆盖真实成功证据。

## Worker

初态：`NEW`。合法主路径：`NEW→STARTING→READY↔BUSY→RECYCLING→STOPPING→STOPPED`。启动、执行和关闭均可进入 `FAILED`。一个 Worker Process 只能拥有一个 COM STA、一个 Aspen 实例和一个私有模型副本。COM 对象不得跨线程、跨进程或进入 Queue。

Worker recycle 前置条件由 `max_tasks/max_age/max_rss/max_failures` 中任一门触发；当前实现已覆盖任务数和年龄，RSS 与失败次数仍为待实现项。

## Session

初态：`CREATED`。合法路径：`CREATED→OPENING→OPEN→CLOSING→CLOSED`；打开、使用或关闭失败进入 `FAILED`。`CLOSED` 和 `FAILED` 为终态。会话关闭必须尝试优雅释放，再仅终止自身拥有的子进程，禁止全局 `taskkill`。

## Aspen Case

初态：`STAGED`。模型副本 Hash 在 `STAGED` 固化。`OPENING→OPEN→SOLVING→SOLVED→VALIDATING→CERTIFIED→CLOSED` 为认证路径。`SOLVED→SOLVING` 只允许同一会话内显式重复实验；warm state 身份必须与冷启动身份不同。`FAILED/CLOSED` 为终态。

`CERTIFIED` 必须同时具有：通信、engine return、收敛、约束、守恒、重复性和 Evidence 完整性证据。Mock 永远不能进入真实物理 `CERTIFIED`。

## Certification Run

初态：`PENDING`。若缺少 licensed Windows host、资格模型或 Registry Hash，则 `PENDING→BLOCKED`。运行后只能到 `PASSED/FAILED/BLOCKED`。`PASSED` 不等于 Release 可发布；Release 还需 Portable CI、审计覆盖、PDF 与版本一致性门禁。

## Evidence Bundle

初态：`BUILDING`。文件列表和 Hash 完整后 `BUILDING→SEALED`；Manifest 验证后 `SEALED→VERIFIED`。任何缺失、额外隐藏文件、Hash 不符或路径逃逸进入 `CORRUPT`。`VERIFIED/CORRUPT` 为终态，Bundle 不可原地修改。

## Surrogate Model

初态：`DRAFT`。`DRAFT→VALIDATING→ACTIVE` 后方可路由。适用域、漂移、不确定性或 Manifest 失败可进入 `DRIFTED/BLOCKED`；重新验证后可恢复 `ACTIVE`。`RETIRED` 为终态。超域不得静默裁剪，必须回退 Aspen 或阻断。

## Approval Request

初态：`PENDING`。可到 `APPROVED/REJECTED/EXPIRED`。`APPROVED` 不是永久终态：绑定的 request、model、registry、prediction、constraints、balances 或 commit 任一 Hash 改变时，必须 `APPROVED→INVALIDATED`。失效审批不得重放。

## 验证

```bash
python scripts/verify_state_machines.py
pytest tests/test_state_machines.py
```

机器检查确保：初态已声明、转换目标存在、终态无出边、所有非终态至少有一个出口，以及非法终态回跳被拒绝。
