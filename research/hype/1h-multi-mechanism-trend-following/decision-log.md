# HYPE-1H-Multi-Mechanism-Trend-Following Decision Log

## 2026-07-22 — 建立独立家族并先冻结样本外

决定建立 `HYPE-1H-Multi-Mechanism-Trend-Following`，只复用数据基础设施，不继承现有 HYPE 1h 家族的策略身份、参数或结论。任何搜索前先冻结最近三个月 locked OOS；证据见 [数据冻结报告](diagnostics/hype-1h-mmtf-data-freeze-2026-07-22.md)。

## 2026-07-22 — 登记 V1 原始基线但不 promotion

`48,000` 个 prefit-only 候选没有联合通过硬门槛；登记最强稳健 time-series momentum 原始边界为 `HYPE-1H-Multi-Mechanism-Trend-Following-V1`，状态保持 `registered diagnostic baseline / NO-GO / not promoted / not live-ready`。证据见 [V1 广搜报告](diagnostics/hype-1h-mmtf-v1-broad-search-2026-07-22.md) 与 [V1 规格](specs/hype-1h-mmtf-v1-original-baseline-spec.md)。

## 2026-07-22 — 登记 V2 clean-equivalent

全组件消融证明 8 个槽为机制选择、fixed-disabled 或 path-equal；删除后 V2 与 V1 的逐笔 SHA256 完全相同，故登记 `HYPE-1H-Multi-Mechanism-Trend-Following-V2` 为 clean-equivalent，状态不变。证据见 [消融报告](ablations/hype-1h-mmtf-v1-full-ablation-2026-07-22.md) 与 [V2 规格](specs/hype-1h-mmtf-v2-clean-equivalent-spec.md)。

## 2026-07-22 — 冻结 V3 并完成一次性 OOS 揭示，最终 NO-GO

V3 在 `60,000` 个 clean-surface 候选与 14 个滚动窗口后冻结；唯一一次 locked OOS 揭示未过年化、回撤和最低交易数，且 K+2、8bps 与 shifted-phase 失败。登记 V3 但保持 `HARD-GATE-FAILED / NO-GO / not promoted / not live-ready`，禁止据本次 OOS 追参；证据见 [最终审计](diagnostics/hype-1h-mmtf-v3-final-audit-2026-07-22.md)。
