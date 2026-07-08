# Binance-1D-Turtle-Breakout

本目录记录 Binance USD-M Futures `BTCUSDT`、`ETHUSDT`、`HYPEUSDT` 日线 20/10 turtle breakout 诊断。

## 当前状态

- 状态：`explore / not promoted`。
- 数据：Binance `/fapi/v1/klines` USD-M Futures `1d` 已收盘 UTC 日K。
- 规则：收盘价突破前 20 根日K最高价时收盘买入；持仓后收盘价跌破前 10 根日K最低价时收盘卖出。
- 最新诊断：`diagnostics/binance-1d-turtle-breakout-2026-06-27.md`。
- 固定 1x 结论：2025-06-27 至 2026-06-26 的一年窗口内三标的策略净收益均为负；`HYPEUSDT -26.04%`，`BTCUSDT -26.40%`，`ETHUSDT -45.61%`。
- 动态仓位结论：最佳均来自以前 10 日低点做风险定仓的低暴露模型，`HYPEUSDT -0.49%`、`BTCUSDT -3.31%`、`ETHUSDT -3.33%`；改善主要来自平均仓位降至约 `1.28%`、`3.28%`、`2.44%`，不是信号收益变好。
- 主要限制：same-day close fill 只能作为诊断口径，不能直接视为 live-executable 成交模型。

## 复现入口

- 脚本：`scripts/research_binance_1d_turtle_breakout.py`
- 诊断报告：`diagnostics/`
- 结果与证据：`artifacts/`
