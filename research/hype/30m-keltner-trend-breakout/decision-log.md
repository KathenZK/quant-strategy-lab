# HYPE-30M-Keltner-Trend-Breakout Decision Log

## 2026-07-08：建线

结论：将同事外部规格 `K2-FQ-V2-ATRVT-OFF` 作为独立 `HYPE-30M-Keltner-Trend-Breakout` 研究线复现，不继承或提升任何既有 HYPE 家族状态。

证据：[README.md](README.md)，[scripts/research_hype_30m_k2_fq_v2_atrvt_off_backtest.py](scripts/research_hype_30m_k2_fq_v2_atrvt_off_backtest.py)。

## 2026-07-08：回测复现

结论：独立回测与外部验收基本对账成功，但继续结算到 `2026-07-06 23:59 UTC` 后新增一笔亏损 time exit，单相位 6 bps/side 从外部验收等价的 `+7698.66% / 113 笔`降至 `+7516.88% / 114 笔`；策略保持 `explore / not promoted / not live-ready`。

证据：[notes/hype-30m-k2-fq-v2-atrvt-off-backtest-2026-07-08.md](notes/hype-30m-k2-fq-v2-atrvt-off-backtest-2026-07-08.md)。

## 2026-07-10：严格门禁

结论：按手续费 `0.001/fill`、不利滑点 `0.0004/fill`、实际 funding 与项目 Gate 0–7 重跑后，数据质量前置及 Gate 3/5/6/7 失败，Gate 4/live-executable 未完成；30m 非原生相位中位 CAGR 仅为原生相位的 `7.70%`，不得登记正式版本或推进 runner。

证据：[notes/hype-30m-k2-strict-validation-gates-2026-07-10.md](notes/hype-30m-k2-strict-validation-gates-2026-07-10.md)。

## 2026-07-10：数据修复与门禁复跑

结论：Binance FAPI 确认 `2026-06-25 08:46 UTC` 的 cache 终值正确；已补齐 407 个日分区的完整 raw/normalized `1m` data lake、补 `vwap` 并实现 cache/lake 零差异对拍。复跑后数据质量前置通过且交易结果不变；Gate 3/5/6/7 仍失败，策略状态不变。

证据：[notes/hype-30m-k2-strict-validation-gates-2026-07-10.md](notes/hype-30m-k2-strict-validation-gates-2026-07-10.md)，[scripts/repair_hype_1m_standard_data_lake.py](scripts/repair_hype_1m_standard_data_lake.py)。

## 2026-07-10：V2 全参数消融与精简微调

结论：移除 `close-vs-slow`、opposite-regime 排除和最低杠杆 floor，微调 `slow 48→44`、`slope lag 4→5`、`leverage ATR 96→84`、`ATR target 3.0%→2.7%` 后，得到 `+4638.01% / MDD -25.84% / 胜率 56.64%`，收益保留 `96.09%`；保留为 `PRUNED-TUNED` 观察值，但 Gate 3/6/7 仍失败，不登记正式版本、不推进 runner。

证据：[notes/hype-30m-k2-v2-full-ablation-pruned-tune-2026-07-10.md](notes/hype-30m-k2-v2-full-ablation-pruned-tune-2026-07-10.md)。
