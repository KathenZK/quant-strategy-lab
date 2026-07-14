# HYPE-30M-Keltner-Trend-Breakout

完整 family name：`HYPE-30M-Keltner-Trend-Breakout`

历史别名 / 外部版本：`K2-FQ-V2-ATRVT-OFF`

状态：`V3 registered / not promoted / not live-ready`

市场与周期：Binance USDM 永续 `HYPEUSDT`，本地 `1m` 闭合 K 线重采样为 `30m` 信号周期与 `1h` 趋势周期。

机制：`1h` EMA 趋势 regime + `30m` Keltner 突破入场，叠加低波动 ATR cap 与方向化 close-location 过滤；下一根 `30m` open 成交，固定 `10%` TP / `2.5%` SL / `hold=30`，并用 `30m ATR84` 做动态杠杆（上限 `3.0x`，无最低 floor）。

防串线警告：这是同事外部 K2/Keltner 规格的复现线，不是 `HYPE-EMA-Trend-Breakout`、`HYPE-EMA-Crossover` 或 `HYPE-15M-Multi-Indicator-Intraday` 的版本。

## 入口

- [hype-30m-keltner-trend-breakout-core-ledger.md](hype-30m-keltner-trend-breakout-core-ledger.md)
- [decision-log.md](decision-log.md)
- [specs/hype-30m-keltner-trend-breakout-v3-spec.md](specs/hype-30m-keltner-trend-breakout-v3-spec.md)
- [specs/hype-30m-keltner-trend-breakout-v2-1-spec.md](specs/hype-30m-keltner-trend-breakout-v2-1-spec.md)
- [notes/hype-30m-k2-v2-1-loss-regime-filter-optimization-2026-07-13.md](notes/hype-30m-k2-v2-1-loss-regime-filter-optimization-2026-07-13.md)
- [notes/hype-30m-k2-v2-1-rsi-macd-filter-study-2026-07-13.md](notes/hype-30m-k2-v2-1-rsi-macd-filter-study-2026-07-13.md)
- [notes/hype-30m-k2-v2-1-dynamic-atr-bracket-2026-07-10.md](notes/hype-30m-k2-v2-1-dynamic-atr-bracket-2026-07-10.md)
- [notes/hype-30m-k2-v2-full-ablation-pruned-tune-2026-07-10.md](notes/hype-30m-k2-v2-full-ablation-pruned-tune-2026-07-10.md)
- [notes/hype-30m-k2-strict-validation-gates-2026-07-10.md](notes/hype-30m-k2-strict-validation-gates-2026-07-10.md)
- [notes/hype-30m-k2-fq-v2-atrvt-off-backtest-2026-07-08.md](notes/hype-30m-k2-fq-v2-atrvt-off-backtest-2026-07-08.md)
- [scripts/research_hype_30m_k2_strict_validation_gates.py](scripts/research_hype_30m_k2_strict_validation_gates.py)
- [scripts/research_hype_30m_k2_v2_full_ablation_and_tune.py](scripts/research_hype_30m_k2_v2_full_ablation_and_tune.py)
- [scripts/research_hype_30m_k2_v2_1_dynamic_atr_bracket.py](scripts/research_hype_30m_k2_v2_1_dynamic_atr_bracket.py)
- [scripts/research_hype_30m_k2_v2_1_rsi_macd_filters.py](scripts/research_hype_30m_k2_v2_1_rsi_macd_filters.py)
- [scripts/research_hype_30m_k2_v2_1_loss_regime_filters.py](scripts/research_hype_30m_k2_v2_1_loss_regime_filters.py)
- [scripts/repair_hype_1m_standard_data_lake.py](scripts/repair_hype_1m_standard_data_lake.py)
- [scripts/research_hype_30m_k2_fq_v2_atrvt_off_backtest.py](scripts/research_hype_30m_k2_fq_v2_atrvt_off_backtest.py)

## 当前结论

`HYPE-30M-Keltner-Trend-Breakout-V3` 已登记，状态为 `registered / not promoted / not live-ready`。V3 = V2.1 + `ATR84/entry <= 1.25%` + 方向化 close location `>=65%`；刷新样本 `+6328.98% / MDD -22.68% / 胜率 67.95% / 78 笔`。start-time 与 30m phase 仍失败，不 promotion。
