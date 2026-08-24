# HYPE-1D-MA7-ABT-V1 首日保护与相位/起跑点审计（2026-08-06）

- 对象：冻结 V1 第 `041` 组多空配置，Binance USD-M `HYPEUSDT` `1d`，数据 `2025-05-31` → `2026-08-05 UTC`（432 日，含前瞻延伸段）；费用 `0.001/fill`、滑点 `4 bps/fill`、事件级 funding。
- 性质：诊断审计，不改变 V1 身份与参数；补齐主账记录的"多头首日保护 + 相位/起跑点"两项审计缺口。

## 结论

1. **多头首日保护（历史上未咬合，契约缺口保留）**：8 笔多头的首持仓日盘中 MAE 最差 `-4.40%`（`0.76x ATR7`），中位 `-2.42%`；假设首日挂 `1.0/1.5/2.0/3.0x ATR7` 硬止损，历史零触发。即"多头首日无 hard stop"在已实现历史中从未造成损失，但首日尾部风险仍无上界，live-readiness 契约缺口不因此关闭。
2. **相位检查项（已检查，不作单独裁决）**：24 个小时级日界相位中 23 个有效（相位 8 因湖终点 `07:00` 缺 terminal bar 属数据边缘，非策略失败）。相位 0（UTC 日界）`+286.99%` 一枝独秀；相邻相位 1/2 为 `+75.06%/+61.44%`；全网格中位 `+26.94%`，17 个相位为正、6 个为负（最差 `-26.40%`），最差相位 MDD `-62.82%`。结果说明 V1 收益对交易所原生日界敏感，应降低历史收益点估计的置信度并交由前瞻观察验证；按 2026-08-06 修订后的统一治理口径，它不构成独立 `not live-ready` blocker。
3. **起跑点审计（通过）**：相位 0 下前 60 个日级起跑点全期净收益全部为正（`+218.89%` ~ `+301.72%`，中位 `+269.56%`），起跑点稳健。

## 状态影响

- V1 维持 `registered / not promoted / not live-ready`。
- 两项待补审计从"未做"转为"已做"：起跑点通过；首日保护历史证据良性但契约缺口保留；相位已作为非强制检查项披露，仅降低证据置信度。
- 后续唯一路径仍是[前瞻观察协议](../specs/hype-1d-ma7-abt-v1-prospective-observation-protocol-2026-08-06.md)的样本积累；不得据本审计在已揭示历史上调参或换相位。

## 证据

- [审计脚本](../scripts/audit_hype_1d_ma7_abt_v1_protection_phase.py)
- [机器摘要](../artifacts/hype_1d_v1_protection_phase_audit_2026-08-06_summary.json) · [首日明细](../artifacts/hype_1d_v1_protection_phase_audit_2026-08-06_first_day.csv) · [相位网格](../artifacts/hype_1d_v1_protection_phase_audit_2026-08-06_phases.csv) · [起跑点网格](../artifacts/hype_1d_v1_protection_phase_audit_2026-08-06_starts.csv)
- [家族主账](../hype-1d-ma7-abt-core-ledger.md)
