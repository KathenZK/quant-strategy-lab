# HYPE-6H-RS4-Regime-Switch 独立复现诊断 2026-06-26

Family id：`HYPE-6H-RS4-Regime-Switch`。本报告复现同事 HTML 中的 RS4 规则，但使用本仓库标准数据湖的 Binance HYPEUSDT 永续 `5m` 闭合 K 聚合为 `6h`。因此它只能审计 Binance/canonical 近期段，不能直接证明 HTML 声称的 Bybit 2024-12 全史表现。

## 数据口径与质量

- 数据：Binance HYPEUSDT perpetual `5m` normalized OHLCV，覆盖 `2025-05-30 10:30:00+00:00` 到 `2026-06-26 04:15:00+00:00`，共 `112822` 根。
- 质量检查：缺失 5m bar `0`，重复 ts `0`，非 closed `0`，非法 OHLC `0`。
- 聚合：完整 `6h` bar `1566` 根，覆盖 `2025-05-30 12:00:00+00:00` 到 `2026-06-25 18:00:00+00:00`；丢弃不完整 6h group `2` 个。
- raw-normalized：checked `True`，passed `True`，raw 5m files `393`。
- funding：`2197` rows，覆盖 `2025-05-30 12:00:00+00:00` 到 `2026-06-01 00:00:00+00:00`；OHLCV 超出 funding 的区间按 0 funding 处理，6 月后半段需补齐后复核。

## 策略口径

- 信号：6h 收盘计算，第下一根 6h 开盘成交；成本为手续费 `4.5bps` + 滑点 `5.0bps` 单边。
- v10：`range3d <= 12%`，MACD(8,21,5) histogram；空头 1 根负柱，做多 2 根正柱；MFEu 只延迟空仓信号，不延迟反向信号。
- melt-leg：`range3d > 12%` 且 `ER20 >= 0.35`，只做多，收盘突破前 20 根高点入场，跌破前 10 根低点或 gate 失效退出。
- 资金费：按 6h 持仓区间内 funding_rate 求和，正 funding 对多头扣减、对空头增加。

## 主要结果

- 全样本 RS4(w=1)：收益 `624.06%`，Sharpe `3.12`，最大回撤 `-29.77%`。
- 全样本 v10 单腿：收益 `338.98%`，最大回撤 `-26.09%`；melt 单腿：收益 `67.58%`，最大回撤 `-19.67%`。
- canonical 截止 2026-05-15：RS4(w=1) 收益 `318.06%`，最大回撤 `-29.77%`。
- 2026-05 暴涨月：v10 `-3.44%`，melt `21.05%`，RS4(w=1) `16.89%`。
- HTML 生成后近似前向段（2026-06-10 后）：RS4(w=1) `19.08%`，melt `4.35%`。

## Walk-Forward 与消融

- 150d train / 21d test 滚动 OOS：RS4(w=1) `267.08%`，正窗口 `10/12`，最差窗口 `-6.49%`。
- 去掉 ER20 的 melt 消融：全样本回撤 `-39.29%`；双向 melt 消融：全样本回撤 `-35.99%`；去掉 Donchian：全样本回撤 `-29.31%`。

## 结论

这次 Binance 近期段复现没有支持 RS4 作为候选策略：组合收益/回撤没有达到机制叙述要求。
但拟合风险仍高：melt-leg 的 ER20 是明显承重墙，删掉后风险显著恶化，说明收益高度依赖少数状态过滤。
HTML 生成后的短前向段为正，但时间太短，不能抵消单币、少事件、无 Bybit 全史复核的问题。

当前状态：`diagnostic only / not promoted`。若要继续，下一步应补 Bybit 2024-12 全史或交易所交叉数据，并把订单重启状态、资金费精确结算和 live runner 状态机复现纳入审计。

## 保留证据

- JSON summary：`research/hype/6h-rs4-regime-switch/artifacts/hype_6h_rs4_backtest_summary.json`
- metrics CSV：`research/hype/6h-rs4-regime-switch/artifacts/hype_6h_rs4_metrics.csv`
- WF windows：`research/hype/6h-rs4-regime-switch/artifacts/hype_6h_rs4_walk_forward_windows.csv`
- trades：`research/hype/6h-rs4-regime-switch/artifacts/hype_6h_rs4_trades.csv`
- equity：`research/hype/6h-rs4-regime-switch/artifacts/hype_6h_rs4_equity.csv`
