# HYPE-6H-RS4 简化版回测 2026-06-28

本报告接受全参数消融后的精简建议：保留 RS4 核心机制，固定 Donchian 与 ATR 参数为机制常量，并从 MFEu 状态机中移除两个近似死参数：`first_flat_exemption` 与 `breakeven_guard`。

## 简化内容

- 保留：`range_window=12`、`range_threshold=12%`、`MACD(8,21,5)`、`long_persist=2`、`MFE trigger/giveback=2.0/1.5 ATR`、`ER20>=0.35`、`long-only`、`Donchian 20/10`、`w=1.0`。
- 移除：`first_flat_exemption`，不再对第一次空仓信号做额外豁免。
- 移除：`breakeven_guard`，因为在当前收盘判断/次根开盘成交口径下此前消融完全无影响。
- 固定不调：`donchian_entry`、`donchian_exit`、`atr_window`；它们仍作为机制常量存在，不再作为搜索参数。

## 全样本对比

| strategy | total_return | delta_return | max_drawdown | delta_max_drawdown | sharpe | trade_count |
| --- | --- | --- | --- | --- | --- | --- |
| baseline | 624.06% | 0.00% | -29.77% | 0.00% | 3.12 | 128 |
| simplified_no_first_flat_exemption | 624.48% | 0.42% | -29.77% | 0.00% | 3.14 | 128 |
| simplified_final | 624.48% | 0.42% | -29.77% | 0.00% | 3.14 | 128 |

## 简化版固定时间片

| slice | total_return | delta_return | max_drawdown | delta_max_drawdown | trade_count | exposure |
| --- | --- | --- | --- | --- | --- | --- |
| full | 624.48% | 0.42% | -29.77% | 0.00% | 128 | 0.51 |
| early_2025_05_30_to_2025_09_01 | 24.47% | 0.22% | -28.60% | 0.00% | 34 | 0.48 |
| mid_2025_09_01_to_2025_12_01 | 91.63% | 0.80% | -8.58% | -0.00% | 24 | 0.38 |
| late_2025_12_01_to_2026_03_01 | 33.42% | -2.55% | -18.80% | -2.24% | 31 | 0.43 |
| spring_2026_03_01_to_2026_06_01 | 63.03% | 2.21% | -17.96% | 0.00% | 34 | 0.75 |
| post_funding_gap_2026_06_01_latest | 39.64% | 0.00% | -8.03% | 0.00% | 5 | 0.41 |
| may_2026 | 18.49% | 1.60% | -13.24% | -0.00% | 7 | 0.65 |

## 简化版月度与 21 天稳定性

- 正月份：`11/14`；最差月 `-12.61%`；中位月收益 `17.73%`。
- 正 21 天窗口：`15/19`；最差 21 天 `-7.86%`；中位 21 天收益 `13.19%`。

## 结论

简化版与基线几乎等价，说明删掉的两个 MFEu 参数不是收益承重墙，可以从正式规格中移除。
但这只是参数精简，不改变上一份报告的状态判断：RS4 仍是 `diagnostic only / not promoted`，原因是 Bybit 全史、完整 funding、跨交易所和 live runner 状态机审计仍未完成。

## 保留证据

- summary JSON：`research/hype/6h-rs4-regime-switch/artifacts/hype_6h_rs4_simplified_backtest_summary_2026-06-28.json`
- metrics CSV：`research/hype/6h-rs4-regime-switch/artifacts/hype_6h_rs4_simplified_backtest_metrics_2026-06-28.csv`
- slice CSV：`research/hype/6h-rs4-regime-switch/artifacts/hype_6h_rs4_simplified_backtest_slices_2026-06-28.csv`
- rolling 21d CSV：`research/hype/6h-rs4-regime-switch/artifacts/hype_6h_rs4_simplified_backtest_rolling21d_2026-06-28.csv`
