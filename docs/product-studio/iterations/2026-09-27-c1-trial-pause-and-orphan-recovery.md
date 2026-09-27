# C1 暂停门禁、独立审查与中断 Job 恢复

- 状态：`Closed`
- 日期：2026-09-27
- 所属阶段：Phase C
- 工作包：C1.2

## 背景

本地主链路恢复 Gate 已通过，但 C1 真实体验验证按负责人要求继续暂缓。此前暂停只存在于台账文字，Product Studio 仍可能在满足软件前置条件后启动 C1；同时 reviewer 输入默认带有占位名，且上次进程中断后处于 `running` 的 Execution Job 没有明确恢复命令。

## 实施

1. **C1 真实试用暂停门禁**
   - API 支持 `PSYTEARDOWN_C1_TRIAL_ENABLED` / `create_app(c1_trial_enabled=...)`。默认关闭。
   - `/api/v1/c1-policy` 返回 `trial_state` 与状态说明。
   - C1 envelope 启动在服务端拒绝暂停状态，UI 明确显示“当前暂缓”。
   - 测试用显式 `c1_trial_enabled=True`，不改变生产默认。
2. **EvidenceReview reviewer 边界**
   - reviewer 不再预填 `named-reviewer`。
   - 服务端拒绝常见占位 reviewer，并继续拒绝 host 本人和自动化主体。
   - 这仍是身份声明校验，不是现实身份认证。
3. **Execution Job 中断恢复**
   - 新增 recovery API：只有 `running` Job 且调用方明确确认 orphaned，才可回到 `queued`。
   - 工作区恢复入口覆盖 `running` execution，先恢复再运行，避免静默重复启动。
   - 状态仍不能证明旧子进程已退出；恢复操作必须显式确认。

## 验证

- C1 API / execution recovery / OpenAPI contract targeted tests passed。
- 前端测试与 production build passed。
- 真实 C1 试用没有启动，本批没有参与者数据，也没有提升 Outcome Evidence。

## 遗留

- `trial_enabled` 是本地/运维开关，不是身份、权限或多租户治理。
- execution recovery 不能检测并杀掉未知的旧进程；部署级 OS/container 隔离仍未完成。
- reviewer 的“具名”仍是输入边界，不是身份系统。
