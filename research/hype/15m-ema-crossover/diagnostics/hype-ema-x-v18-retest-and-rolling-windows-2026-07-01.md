# HYPE-EMA-X-V18 复测与滚动窗口回测 2026-07-01

## 结论

- 数据切片：Binance HYPEUSDT perpetual `15m`，`2025-05-30 10:30:00+00:00` 至 `2026-06-01 03:00:00+00:00`，本次强制截断到 `2026-06-01 03:00:00+00:00`，共 `35203` 根 K 线。
- 成本：`trade_cost=0.00085`，`slippage=0.0005`；信号收盘确认、下一根 open 成交；1h 指标 resample 后 `shift(1)`。
- V18 基线 365D：收益 `+3861.48%`，最大回撤 `-19.44%`，胜率 `+90.91%`，交易 `33` 笔，late `7` 笔。
- 本复测当时未改变 promotion 状态；2026-07-08 后续确认 V18 已进入 quant-runner `dry-run / forward-test required`，以家族主账和 [../forward-tracking/README.md](../forward-tracking/README.md) 为准。

## V18 基线与最近窗口

| kind | window | return | max_dd | sharpe | trades | late_trades | win_rate | exit_reasons |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline | 365D | +3861.48% | -19.44% | 4.765596511826483 | 33 | 7 | +90.91% | {"hard_swing96": 4, "warning_confirm_osc": 10, "warning_confirm_volume": 19} |
| recent | 7D | +0.00% | +0.00% | 0.0 | 0 | 0 | +0.00% | {} |
| recent | 30D | +152.13% | -19.44% | 8.769686383612502 | 4 | 1 | +100.00% | {"warning_confirm_osc": 1, "warning_confirm_volume": 3} |
| recent | 90D | +348.68% | -19.44% | 6.454856392789537 | 9 | 1 | +100.00% | {"warning_confirm_osc": 2, "warning_confirm_volume": 7} |
| recent | 180D | +1021.61% | -19.44% | 5.502773142989945 | 19 | 2 | +89.47% | {"hard_swing96": 3, "warning_confirm_osc": 6, "warning_confirm_volume": 10} |
| recent | 365D | +3861.48% | -19.44% | 4.765596511826483 | 33 | 7 | +90.91% | {"hard_swing96": 4, "warning_confirm_osc": 10, "warning_confirm_volume": 19} |

## 滚动窗口汇总

| window | slices | positive_return_slices | negative_return_slices | median_return | min_return | max_return | median_max_dd | worst_max_dd | median_trades | zero_trade_slices |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 30D | 13 | 12 | 1 | +25.81% | -5.33% | +158.79% | -13.58% | -19.44% | 3.0 | 0 |
| 90D | 11 | 11 | 0 | +117.44% | +38.91% | +375.14% | -16.29% | -19.44% | 8.0 | 0 |
| 180D | 8 | 8 | 0 | +338.59% | +138.50% | +1021.61% | -19.09% | -19.44% | 16.5 | 0 |
| 365D | 2 | 2 | 0 | +3913.82% | +3861.48% | +3966.16% | -19.44% | -19.44% | 33.0 | 0 |

## 信号计数

- `base_bars`: `1006`
- `filtered_base_bars`: `912`
- `add_bars`: `0`
- `total_bars`: `912`

## 保留证据

- 汇总 CSV：`../artifacts/hype_ema_x_v18_retest_summary_2026-07-01.csv`
- 滚动窗口 CSV：`../artifacts/hype_ema_x_v18_retest_rolling_windows_2026-07-01.csv`
- 交易明细 CSV：`../artifacts/hype_ema_x_v18_retest_trades_2026-07-01.csv`
- 交易归因 CSV：`../artifacts/hype_ema_x_v18_retest_trade_attribution_2026-07-01.csv`
- JSON：`../artifacts/hype_ema_x_v18_retest_2026-07-01.json`

## 注意事项

- 滚动窗口使用固定步长向前推进；每个窗口只截取到该窗口终点之前的数据，避免窗口终点之后 K 线影响结果。
- 低频策略的短窗口交易数很少，`7D/30D` 结果主要用于暴露空窗和路径风险，不应单独视为 promotion 证据。
