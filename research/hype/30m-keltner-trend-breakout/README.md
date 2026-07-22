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
- [V3 最新有效性审计](diagnostics/hype-30m-keltner-v3-latest-validity-2026-07-21.md)
- [specs/hype-30m-keltner-trend-breakout-v3-spec.md](specs/hype-30m-keltner-trend-breakout-v3-spec.md)
- [specs/hype-30m-keltner-trend-breakout-v2-1-spec.md](specs/hype-30m-keltner-trend-breakout-v2-1-spec.md)
- [ablations/hype-30m-k2-v3-full-parameter-ablation-timeframe-robustness-2026-07-17.md](ablations/hype-30m-k2-v3-full-parameter-ablation-timeframe-robustness-2026-07-17.md)
- [notes/hype-30m-k2-v2-1-loss-regime-filter-optimization-2026-07-13.md](notes/hype-30m-k2-v2-1-loss-regime-filter-optimization-2026-07-13.md)
- [notes/hype-30m-k2-v2-full-ablation-pruned-tune-2026-07-10.md](notes/hype-30m-k2-v2-full-ablation-pruned-tune-2026-07-10.md)
- [notes/hype-30m-k2-strict-validation-gates-2026-07-10.md](notes/hype-30m-k2-strict-validation-gates-2026-07-10.md)

## 当前结论

`HYPE-30M-Keltner-Trend-Breakout-V3` 已登记；最新 clean prospective 为正但只有 2 笔。多周期迁移与 30m 非原生相位门禁仍失败，保持 `registered / not promoted / not live-ready`；完整证据以主账为准。
