# HYPE-30M-Keltner-Trend-Breakout

完整 family name：`HYPE-30M-Keltner-Trend-Breakout`

历史别名 / 外部版本：`K2-FQ-V2-ATRVT-OFF`

状态：`V2.1 registered / not promoted / not live-ready`

市场与周期：Binance USDM 永续 `HYPEUSDT`，本地 `1m` 闭合 K 线重采样为 `30m` 信号周期与 `1h` 趋势周期。

机制：`1h` EMA 趋势 regime + `30m` Keltner 突破入场，下一根 `30m` open 成交，固定 `10%` TP / `2.5%` SL / `hold=30`，并用 `30m ATR96` 做 1.0x-3.0x 动态杠杆。

防串线警告：这是同事外部 K2/Keltner 规格的复现线，不是 `HYPE-EMA-Trend-Breakout`、`HYPE-EMA-Crossover` 或 `HYPE-15M-Multi-Indicator-Intraday` 的版本。

## 入口

- [hype-30m-keltner-trend-breakout-core-ledger.md](hype-30m-keltner-trend-breakout-core-ledger.md)
- [decision-log.md](decision-log.md)
- [specs/hype-30m-keltner-trend-breakout-v2-1-spec.md](specs/hype-30m-keltner-trend-breakout-v2-1-spec.md)
- [notes/hype-30m-k2-v2-1-dynamic-atr-bracket-2026-07-10.md](notes/hype-30m-k2-v2-1-dynamic-atr-bracket-2026-07-10.md)
- [notes/hype-30m-k2-v2-full-ablation-pruned-tune-2026-07-10.md](notes/hype-30m-k2-v2-full-ablation-pruned-tune-2026-07-10.md)
- [notes/hype-30m-k2-strict-validation-gates-2026-07-10.md](notes/hype-30m-k2-strict-validation-gates-2026-07-10.md)
- [notes/hype-30m-k2-fq-v2-atrvt-off-backtest-2026-07-08.md](notes/hype-30m-k2-fq-v2-atrvt-off-backtest-2026-07-08.md)
- [scripts/research_hype_30m_k2_strict_validation_gates.py](scripts/research_hype_30m_k2_strict_validation_gates.py)
- [scripts/research_hype_30m_k2_v2_full_ablation_and_tune.py](scripts/research_hype_30m_k2_v2_full_ablation_and_tune.py)
- [scripts/research_hype_30m_k2_v2_1_dynamic_atr_bracket.py](scripts/research_hype_30m_k2_v2_1_dynamic_atr_bracket.py)
- [scripts/repair_hype_1m_standard_data_lake.py](scripts/repair_hype_1m_standard_data_lake.py)
- [scripts/research_hype_30m_k2_fq_v2_atrvt_off_backtest.py](scripts/research_hype_30m_k2_fq_v2_atrvt_off_backtest.py)

## 当前结论

`HYPE-30M-Keltner-Trend-Breakout-V2.1` 已登记：`+4638.01% / MDD -25.84% / 胜率 56.64%`。433 个 ATR10/ATR84 动态 TP/SL 配置没有任何一个同时实现更高胜率、更低 MDD和足够收益保留，因此 V2.1 继续冻结固定 `TP=10% / SL=2.5%`。Gate 3/6/7 仍失败；状态为 `registered / not promoted / not live-ready`。
