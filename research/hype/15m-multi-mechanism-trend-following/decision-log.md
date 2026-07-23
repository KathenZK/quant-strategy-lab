# HYPE-15M-MMTF Decision Log

## 2026-07-22 — 建立独立 15m 多机制纯趋势家族

决定：本任务比较多个纯趋势机制并要求 V1 冻结、全接线消融与 clean tune，机制边界不同于任何单一 EMA、Keltner、Pullback、MII 或 1h 家族，因此建立 `HYPE-15M-Multi-Mechanism-Trend-Following`。当前保持 `explore / not promoted / not live-ready`，锁定 OOS 揭示前不得使用其绩效选型。

## 2026-07-22 — 登记 V1 原始基线

决定：48,000 组 prefit/validation 广搜没有硬目标通过项；将满足冻结样本门槛且联合距离最小的双向 Keltner 配置登记为 `HYPE-15M-MMTF-V1 registered / not promoted / not live-ready`，随后只在 locked OOS 之前做全接线消融。证据：[广搜报告](diagnostics/hype-15m-mmtf-v1-broad-search-2026-07-22.md)与[V1 规格](specs/hype-15m-mmtf-v1-original-baseline-spec.md)。

## 2026-07-22 — 登记 V2 clean-equivalent 与 V3 tuned freeze

决定：根据全接线消融删除 dormant 表面，登记逐笔等价的 V2；随后只调优有效参数并登记 V3。locked OOS 在 V3 config/code hash 冻结前未访问。证据：[消融](ablations/hype-15m-mmtf-v1-full-ablation-2026-07-22.md)与[clean tune](diagnostics/hype-15m-mmtf-v2-clean-tune-2026-07-22.md)。

## 2026-07-22 — V3 最终硬门槛失败，停止本冻结线

决定：一次性 locked OOS、8bps、K+2 与 phase 均失败；V3 保持 `registered / HARD-GATE-FAILED / not promoted / not live-ready`。不在已揭示 OOS 上继续调参，且因无 runner 不进入 promotion review。证据：[最终审计](diagnostics/hype-15m-mmtf-v3-final-audit-2026-07-22.md)。
