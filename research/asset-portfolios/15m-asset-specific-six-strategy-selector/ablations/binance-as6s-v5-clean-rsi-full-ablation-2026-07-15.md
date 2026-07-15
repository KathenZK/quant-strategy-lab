# BIN-15M-AS6S V5 HYPE clean-RSI全组件消融（2026-07-15）

严格使用 `ts < 2026-07-14T09:00Z`；未读取未来OOS，未修改V5。

- 变体（含基线）：`10`
- 三场景精确无变化：`4`，即 `remove_max_atr, remove_rvol_min, remove_h1, remove_rsi14_band`。
- 除10个显式Config字段外，已补测固定MACD方向和固定ATR96上限。
- `remove_stop_diagnostic` 与 `remove_max_hold_diagnostic` 不可promotion。
- RSI crossing及其窗口/阈值是机制本体，进入clean-surface微调，不用零交易伪消融代替。

结构化结果：[`binance_as6s_v5_clean_rsi_full_ablation_2026-07-15.json`](../artifacts/binance_as6s_v5_clean_rsi_full_ablation_2026-07-15.json)。
