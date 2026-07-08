# HYPE-30M-Keltner-Trend-Breakout

完整 family name：`HYPE-30M-Keltner-Trend-Breakout`

历史别名 / 外部版本：`K2-FQ-V2-ATRVT-OFF`

状态：`explore / not promoted / not live-ready`

市场与周期：Binance USDM 永续 `HYPEUSDT`，本地 `1m` 闭合 K 线重采样为 `30m` 信号周期与 `1h` 趋势周期。

机制：`1h` EMA 趋势 regime + `30m` Keltner 突破入场，下一根 `30m` open 成交，固定 `10%` TP / `2.5%` SL / `hold=30`，并用 `30m ATR96` 做 1.0x-3.0x 动态杠杆。

防串线警告：这是同事外部 K2/Keltner 规格的复现线，不是 `HYPE-EMA-Trend-Breakout`、`HYPE-EMA-Crossover` 或 `HYPE-15M-Multi-Indicator-Intraday` 的版本。

## 入口

- [hype-30m-keltner-trend-breakout-core-ledger.md](hype-30m-keltner-trend-breakout-core-ledger.md)
- [decision-log.md](decision-log.md)
- [notes/hype-30m-k2-fq-v2-atrvt-off-backtest-2026-07-08.md](notes/hype-30m-k2-fq-v2-atrvt-off-backtest-2026-07-08.md)
- [scripts/research_hype_30m_k2_fq_v2_atrvt_off_backtest.py](scripts/research_hype_30m_k2_fq_v2_atrvt_off_backtest.py)

## 当前结论

本仓库独立复现与外部验收数字基本对账成功：剔除最新一笔 `2026-07-05` 开仓的 time exit 后，单相位 6 bps/side 收益对齐到 `+7698.66% / 113 笔`；继续结算到 `2026-07-06 23:59 UTC` 后为 `+7516.88% / 114 笔`。该策略仍保持 `explore / not promoted / not live-ready`，因为高杠杆、样本截止敏感、funding/止损滑点/live-executable 审计尚未完成。
