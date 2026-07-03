# SOL-1H-Adaptive-Regime 广泛搜索 - 2026-07-03

## 结论

没有任何冻结 finalist 同时通过 full 与最近三个月 locked OOS 的三项硬门槛，当前结论为 `NO-GO / not promoted / not live-ready`。

- finalists：`700`；prefit pass：`0`；locked target pass：`0`。
- 目标：年化权益倍率 `>=10.0x`（annual return `>=900%`）、胜率 `>=50%`、最大回撤严格小于 `20%`。

## 数据质量

- Binance USD-M Futures `SOLUSDT` perpetual `1h`：`17520` 根闭合 K。
- UTC：`2024-07-03T05:00:00+00:00` 至 `2026-07-03T04:00:00+00:00`。
- missing=`0`，duplicate=`0`，funding rows=`2190`。

## 防泄漏时间切分

- warmup/raw start：`2024-07-03T05:00:00+00:00` / `2024-08-17T05:00:00+00:00`。
- train：`2024-08-17T05:00:00+00:00` 至 `2025-09-07T07:24:00+00:00`。
- validation：`2025-09-07T07:24:00+00:00` 至 `2026-04-03T05:00:00+00:00`。
- locked OOS（固定最近三个月）：`2026-04-03T05:00:00+00:00` 至 `2026-07-03T05:00:00+00:00`。
- 参数生成、打分、保留和 ensemble 仅使用 train + validation；OOS 只对冻结 finalists 解锁一次。

## 执行与成本

- 闭合 `1h` K 生成信号，下一根 open 市价入场；单仓、不加仓。
- 入场后立即具备 ATR stop/TP；同 K 双触发 stop-first；open 穿越 stop 按 open 成交。
- trailing 仅在完整 K 结束后更新，更新后的 stop 从下一根 K 生效。
- fee `0.1000%/fill`，slippage `0.0400%/fill`，另逐笔计入真实 Binance funding。

## 搜索覆盖

- curated_configs：`768`。
- random_configs：`1000000`。
- generated_configs：`1000768`。
- evaluated_configs：`618424`。
- prefit_eligible：`237263`。
- prefit_pass_observations：`0`。
- retained_single：`1200`。
- retained_ensembles：`200`。
- locked_finalists：`700`。
- locked_target_pass：`0`。
- 机制：EMA/MACD、Donchian、Bollinger、RSI、Stochastic、CCI、Williams %R、EMA pullback、Keltner、squeeze、ADX/DI、rolling VWAP、momentum、wick rejection、ATR、RVOL、4h/12h/1d regime、funding filter、fixed/risk sizing、fixed/trailing exit。

## 最佳冻结 finalist

- id：`ENS__SOL_1H_AR_R594184__SOL_1H_AR_R736318`；kind/style：`ensemble` / `donchian_break+bb_revert`。
- full：annual `2.18x`，return `330.75%`，DD `-18.86%`，win `76.60%`，trades `94`，PF `3.536`。
- locked OOS：annual `0.71x`，return `-8.09%`，DD `-16.19%`，win `50.00%`，trades `8`，PF `0.608`。
- hard gate：`False`。

## 时间切片

| Window | Annual | Return | DD | Win | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `train` | `2.49x` | `161.85%` | `-17.90%` | `78.43%` | `51` | `5.297` |
| `validation` | `2.78x` | `78.97%` | `-10.31%` | `80.00%` | `35` | `4.393` |
| `locked_holdout` | `0.71x` | `-8.09%` | `-16.19%` | `50.00%` | `8` | `0.608` |
| `full` | `2.18x` | `330.75%` | `-18.86%` | `76.60%` | `94` | `3.536` |
| `last_30d` | `1.28x` | `2.04%` | `-16.11%` | `75.00%` | `4` | `1.307` |
| `last_60d` | `0.59x` | `-8.29%` | `-16.11%` | `50.00%` | `6` | `0.589` |
| `last_90d` | `0.71x` | `-8.09%` | `-16.19%` | `50.00%` | `8` | `0.608` |
| `rolling_block_01` | `2.72x` | `8.55%` | `-5.97%` | `100.00%` | `2` | `inf` |
| `rolling_block_02` | `1.40x` | `2.81%` | `-1.81%` | `50.00%` | `2` | `19.707` |
| `rolling_block_03` | `1.12x` | `0.92%` | `-5.77%` | `50.00%` | `4` | `2.459` |
| `rolling_block_04` | `1.52x` | `3.48%` | `-4.25%` | `100.00%` | `3` | `inf` |
| `rolling_block_05` | `11.52x` | `22.23%` | `-4.54%` | `80.00%` | `5` | `25.510` |
| `rolling_block_06` | `12.45x` | `23.01%` | `-6.01%` | `100.00%` | `6` | `inf` |
| `rolling_block_07` | `1.40x` | `2.82%` | `-3.31%` | `100.00%` | `2` | `inf` |
| `rolling_block_08` | `23.85x` | `29.76%` | `-6.21%` | `100.00%` | `4` | `inf` |
| `rolling_block_09` | `25.98x` | `30.67%` | `-6.17%` | `100.00%` | `9` | `inf` |
| `rolling_block_10` | `0.43x` | `-6.69%` | `-13.75%` | `0.00%` | `1` | `0.000` |
| `rolling_block_11` | `1.04x` | `0.32%` | `-3.28%` | `50.00%` | `2` | `1.710` |
| `rolling_block_12` | `0.47x` | `-5.98%` | `-9.13%` | `50.00%` | `6` | `0.342` |
| `rolling_block_13` | `0.64x` | `-3.59%` | `-7.67%` | `50.00%` | `6` | `0.452` |
| `rolling_block_14` | `3.28x` | `10.23%` | `-7.04%` | `83.33%` | `6` | `13.685` |
| `rolling_block_15` | `6.55x` | `16.70%` | `-6.52%` | `75.00%` | `4` | `4.579` |
| `rolling_block_16` | `0.63x` | `-3.78%` | `-6.11%` | `50.00%` | `4` | `0.197` |
| `rolling_block_17` | `5.33x` | `14.74%` | `-3.02%` | `100.00%` | `4` | `inf` |
| `rolling_block_18` | `2.05x` | `6.08%` | `-3.64%` | `66.67%` | `3` | `6.313` |
| `rolling_block_19` | `2.13x` | `6.40%` | `-5.88%` | `85.71%` | `7` | `2.175` |
| `rolling_block_20` | `4.32x` | `12.77%` | `-5.32%` | `100.00%` | `6` | `inf` |
| `rolling_block_21` | `0.59x` | `-4.18%` | `-5.63%` | `33.33%` | `3` | `0.122` |
| `rolling_block_22` | `0.63x` | `-3.67%` | `-7.68%` | `50.00%` | `2` | `0.413` |
| `rolling_block_23` | `0.94x` | `-0.43%` | `-16.11%` | `66.67%` | `3` | `1.016` |

## Promotion 边界

locked hard gate 未通过，禁止标记为 candidate、paper-live、dry-run、handoff 或 live。

## 产物

- `research/sol/1h-adaptive-regime/artifacts/sol_1h_adaptive_regime_search_2026-07-03.json`
- `research/sol/1h-adaptive-regime/artifacts/sol_1h_adaptive_regime_prefit_2026-07-03.csv`
- `research/sol/1h-adaptive-regime/artifacts/sol_1h_adaptive_regime_ranking_2026-07-03.csv`
- `research/sol/1h-adaptive-regime/artifacts/sol_1h_adaptive_regime_slices_2026-07-03.csv`
- `research/sol/1h-adaptive-regime/artifacts/sol_1h_adaptive_regime_top_trades_2026-07-03.csv`
