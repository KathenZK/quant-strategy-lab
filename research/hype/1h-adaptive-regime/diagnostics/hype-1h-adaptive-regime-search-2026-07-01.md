# HYPE-1H-Adaptive-Regime 广泛搜索 - 2026-07-01

## 结论

本轮没有找到同时通过 full 与 locked holdout 硬门槛的策略，结论为 `NO-GO / not promoted`。

- 最终 finalists：`400`；prefit 命中：`0`；locked target 命中：`0`。
- 目标：年化权益倍率 `>= 10.0x`、胜率 `>= 50%`、最大回撤 `> -20%`。
- 年化倍率按复合净值计算；`10.0x` 对应 annual return `+900%`。

## 数据质量

- Binance USD-M Futures `HYPEUSDT` `1h`：`9526` 根。
- UTC：`2025-05-30T10:00:00+00:00` 至 `2026-07-01T07:00:00+00:00`。
- missing=`0`，duplicate=`0`，raw/normalized 日分区均为 `398`。
- funding rows：`2380`。

## 防泄漏时间切分

- train：`2025-07-14T10:00:00+00:00` 至 `2026-01-23T23:18:00+00:00`。
- validation：`2026-01-23T23:18:00+00:00` 至 `2026-04-13T03:39:00+00:00`。
- locked holdout：`2026-04-13T03:39:00+00:00` 至 `2026-07-01T08:00:00+00:00`。
- 随机搜索、排序和 ensemble 组合只读取 train + validation 指标；locked holdout 只对冻结 finalists 解锁一次。

## 执行与成本

- 已闭合 `1h` K 生成信号，默认下一根 open 市价入场。
- 成交后立即生效的 ATR bracket；trailing 仅在一根 K 完全闭合后更新，更新后的 stop 从下一根 K 生效。
- 同 K TP/SL 双触发按 stop-first；stop 被 open 穿越时按 open 市价退出。
- fee `0.1000%/fill`，slippage `0.0400%/fill`，另逐笔计入 Binance 历史 funding。

## 搜索覆盖

- curated_configs：`768`。
- random_configs：`120000`。
- generated_configs：`120768`。
- evaluated_configs：`70411`。
- prefit_eligible：`29494`。
- prefit_pass_observations：`0`。
- retained_single：`500`。
- evaluated_ensemble_pairs：`1225`。
- retained_ensembles：`200`。
- locked_finalists：`400`。
- locked_target_pass：`0`。
- 指标/机制：EMA、MACD、Donchian、Bollinger、RSI、Stochastic、CCI、Williams %R、EMA pullback、Keltner、squeeze、ADX/DI、rolling VWAP、momentum、wick rejection、ATR、RVOL、4h/12h/1d regime 和 funding filter。

## 最佳冻结 finalist

- id：`HYPE_1H_AR_R171480`。
- kind/style：`single` / `bb_break`。
- full：annual `2.02x`，return `96.42%`，DD `-15.74%`，win `59.49%`，trades `79`，PF `1.913`。
- locked holdout：annual `5.74x`，return `46.03%`，DD `-7.82%`，win `66.67%`，trades `18`，PF `4.660`。
- target pass：`False`。

## 最佳 finalist 时间切片

| Window | Annual | Return | DD | Win | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `train` | `1.14x` | `7.06%` | `-15.74%` | `52.50%` | `40` | `1.182` |
| `validation` | `2.86x` | `25.63%` | `-7.01%` | `66.67%` | `21` | `2.378` |
| `locked_holdout` | `5.74x` | `46.03%` | `-7.82%` | `66.67%` | `18` | `4.660` |
| `full` | `2.02x` | `96.42%` | `-15.74%` | `59.49%` | `79` | `1.913` |
| `last_30d` | `8.02x` | `18.64%` | `-5.05%` | `100.00%` | `6` | `inf` |
| `last_60d` | `13.94x` | `54.16%` | `-5.05%` | `84.62%` | `13` | `13.507` |
| `last_90d` | `4.89x` | `47.88%` | `-12.95%` | `63.64%` | `22` | `3.501` |
| `rolling_block_01` | `0.32x` | `-8.87%` | `-14.54%` | `28.57%` | `7` | `0.426` |
| `rolling_block_02` | `5.01x` | `14.16%` | `-3.75%` | `83.33%` | `6` | `24.341` |
| `rolling_block_03` | `1.03x` | `0.22%` | `-6.07%` | `42.86%` | `7` | `1.064` |
| `rolling_block_04` | `3.28x` | `10.25%` | `-9.32%` | `60.00%` | `5` | `2.713` |
| `rolling_block_05` | `0.28x` | `-9.86%` | `-12.35%` | `42.86%` | `7` | `0.493` |
| `rolling_block_06` | `1.21x` | `1.56%` | `-6.17%` | `50.00%` | `4` | `1.326` |
| `rolling_block_07` | `3.83x` | `11.66%` | `-2.87%` | `80.00%` | `5` | `11.262` |
| `rolling_block_08` | `5.11x` | `14.34%` | `-6.03%` | `70.00%` | `10` | `3.410` |
| `rolling_block_09` | `1.43x` | `2.98%` | `-7.01%` | `66.67%` | `9` | `1.367` |
| `rolling_block_10` | `0.68x` | `-3.12%` | `-10.39%` | `33.33%` | `9` | `0.728` |
| `rolling_block_11` | `21.67x` | `28.74%` | `-5.05%` | `80.00%` | `5` | `10.144` |
| `rolling_block_12` | `8.64x` | `13.81%` | `-3.06%` | `100.00%` | `5` | `inf` |

## Promotion 边界

当前没有策略通过 locked hard gate，因此不得标记为 candidate、paper-live、dry-run、handoff 或 live。

## 产物

- Summary：`research/hype/1h-adaptive-regime/artifacts/hype_1h_adaptive_regime_search_2026-07-01.json`
- Prefit：`research/hype/1h-adaptive-regime/artifacts/hype_1h_adaptive_regime_prefit_2026-07-01.csv`
- Ranking：`research/hype/1h-adaptive-regime/artifacts/hype_1h_adaptive_regime_ranking_2026-07-01.csv`
- Slices：`research/hype/1h-adaptive-regime/artifacts/hype_1h_adaptive_regime_slices_2026-07-01.csv`
- Top trades：`research/hype/1h-adaptive-regime/artifacts/hype_1h_adaptive_regime_top_trades_2026-07-01.csv`
