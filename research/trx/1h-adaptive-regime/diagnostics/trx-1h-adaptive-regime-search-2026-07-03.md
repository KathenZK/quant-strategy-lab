# TRX-1H-Adaptive-Regime 广泛搜索 - 2026-07-03

## 结论

没有任何冻结 finalist 同时通过 full 与最近三个月 locked OOS 的三项硬门槛，当前结论为 `NO-GO / not promoted / not live-ready`。

- finalists：`500`；prefit pass：`0`；locked target pass：`0`。
- 目标：年化权益倍率 `>=10.0x`（annual return `>=900%`）、胜率 `>=50%`、最大回撤严格小于 `20%`。

## 数据质量

- Binance USD-M Futures `TRXUSDT` perpetual `1h`：`17520` 根闭合 K。
- UTC：`2024-07-03T06:00:00+00:00` 至 `2026-07-03T05:00:00+00:00`。
- missing=`0`，duplicate=`0`，funding rows=`2190`。

## 防泄漏时间切分

- warmup/raw start：`2024-07-03T06:00:00+00:00` / `2024-08-17T06:00:00+00:00`。
- train：`2024-08-17T06:00:00+00:00` 至 `2025-09-07T08:24:00+00:00`。
- validation：`2025-09-07T08:24:00+00:00` 至 `2026-04-03T06:00:00+00:00`。
- locked OOS（固定最近三个月）：`2026-04-03T06:00:00+00:00` 至 `2026-07-03T06:00:00+00:00`。
- 参数生成、打分、保留和 ensemble 仅使用 train + validation；OOS 只对冻结 finalists 解锁一次。

## 执行与成本

- 闭合 `1h` K 生成信号，下一根 open 市价入场；单仓、不加仓。
- 入场后立即具备 ATR stop/TP；同 K 双触发 stop-first；open 穿越 stop 按 open 成交。
- trailing 仅在完整 K 结束后更新，更新后的 stop 从下一根 K 生效。
- fee `0.1000%/fill`，slippage `0.0400%/fill`，另逐笔计入真实 Binance funding。

## 搜索覆盖

- curated_configs：`768`。
- random_configs：`300000`。
- generated_configs：`300768`。
- evaluated_configs：`109143`。
- prefit_eligible：`22298`。
- prefit_pass_observations：`0`。
- retained_single：`800`。
- retained_ensembles：`200`。
- locked_finalists：`500`。
- locked_target_pass：`0`。
- 机制：EMA/MACD、Donchian、Bollinger、RSI、Stochastic、CCI、Williams %R、EMA pullback、Keltner、squeeze、ADX/DI、rolling VWAP、momentum、wick rejection、ATR、RVOL、4h/12h/1d regime、funding filter、fixed/risk sizing、fixed/trailing exit。

## 最佳冻结 finalist

- id：`ENS__TRX_1H_AR_R123965__TRX_1H_AR_R143332`；kind/style：`ensemble` / `momentum_break+stoch_reversal`。
- full：annual `1.66x`，return `159.93%`，DD `-16.35%`，win `73.00%`，trades `100`，PF `1.877`。
- locked OOS：annual `0.74x`，return `-7.09%`，DD `-9.62%`，win `33.33%`，trades `3`，PF `0.259`。
- hard gate：`False`。

## 时间切片

| Window | Annual | Return | DD | Win | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `train` | `2.09x` | `118.18%` | `-16.35%` | `71.83%` | `71` | `2.020` |
| `validation` | `1.55x` | `28.22%` | `-15.68%` | `80.77%` | `26` | `2.011` |
| `locked_holdout` | `0.74x` | `-7.09%` | `-9.62%` | `33.33%` | `3` | `0.259` |
| `full` | `1.66x` | `159.93%` | `-16.35%` | `73.00%` | `100` | `1.877` |
| `last_30d` | `0.44x` | `-6.49%` | `-6.79%` | `0.00%` | `1` | `0.000` |
| `last_60d` | `0.64x` | `-7.09%` | `-9.62%` | `33.33%` | `3` | `0.259` |
| `last_90d` | `0.74x` | `-7.09%` | `-9.62%` | `33.33%` | `3` | `0.259` |
| `rolling_block_01` | `9.75x` | `20.57%` | `-10.62%` | `80.00%` | `5` | `3.588` |
| `rolling_block_02` | `1.48x` | `3.29%` | `-2.64%` | `100.00%` | `2` | `inf` |
| `rolling_block_03` | `0.78x` | `-1.99%` | `-10.30%` | `50.00%` | `4` | `0.855` |
| `rolling_block_04` | `1.80x` | `4.94%` | `-11.20%` | `60.00%` | `5` | `1.614` |
| `rolling_block_05` | `3.96x` | `11.96%` | `-9.45%` | `71.43%` | `7` | `2.604` |
| `rolling_block_06` | `4.92x` | `13.97%` | `-4.95%` | `83.33%` | `6` | `4.625` |
| `rolling_block_07` | `5.23x` | `14.55%` | `-9.17%` | `80.00%` | `10` | `3.026` |
| `rolling_block_08` | `0.67x` | `-3.22%` | `-4.38%` | `33.33%` | `3` | `0.273` |
| `rolling_block_09` | `7.32x` | `17.76%` | `-5.73%` | `85.71%` | `7` | `7.148` |
| `rolling_block_10` | `0.44x` | `-6.50%` | `-14.37%` | `50.00%` | `6` | `0.564` |
| `rolling_block_11` | `1.74x` | `4.68%` | `-3.55%` | `83.33%` | `6` | `2.654` |
| `rolling_block_12` | `2.21x` | `6.74%` | `-4.43%` | `75.00%` | `4` | `3.252` |
| `rolling_block_13` | `0.77x` | `-2.13%` | `-11.80%` | `66.67%` | `6` | `0.844` |
| `rolling_block_14` | `4.73x` | `13.61%` | `-3.08%` | `100.00%` | `4` | `inf` |
| `rolling_block_15` | `1.06x` | `0.47%` | `-4.49%` | `66.67%` | `3` | `1.188` |
| `rolling_block_16` | `0.25x` | `-10.78%` | `-14.99%` | `50.00%` | `4` | `0.304` |
| `rolling_block_17` | `1.91x` | `5.45%` | `-2.27%` | `100.00%` | `3` | `inf` |
| `rolling_block_18` | `3.88x` | `11.78%` | `-2.45%` | `100.00%` | `4` | `inf` |
| `rolling_block_19` | `0.64x` | `-3.62%` | `-6.57%` | `50.00%` | `2` | `0.392` |
| `rolling_block_20` | `3.50x` | `10.83%` | `-5.95%` | `83.33%` | `6` | `5.088` |
| `rolling_block_21` | `1.00x` | `0.00%` | `0.00%` | `0.00%` | `0` | `0.000` |
| `rolling_block_22` | `0.92x` | `-0.64%` | `-3.04%` | `50.00%` | `2` | `0.814` |
| `rolling_block_23` | `0.38x` | `-6.49%` | `-6.79%` | `0.00%` | `1` | `0.000` |

## Promotion 边界

locked hard gate 未通过，禁止标记为 candidate、paper-live、dry-run、handoff 或 live。

## 产物

- `research/trx/1h-adaptive-regime/artifacts/trx_1h_adaptive_regime_search_2026-07-03.json`
- `research/trx/1h-adaptive-regime/artifacts/trx_1h_adaptive_regime_prefit_2026-07-03.csv`
- `research/trx/1h-adaptive-regime/artifacts/trx_1h_adaptive_regime_ranking_2026-07-03.csv`
- `research/trx/1h-adaptive-regime/artifacts/trx_1h_adaptive_regime_slices_2026-07-03.csv`
- `research/trx/1h-adaptive-regime/artifacts/trx_1h_adaptive_regime_top_trades_2026-07-03.csv`
