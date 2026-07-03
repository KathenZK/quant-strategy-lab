# ETH-1H-Adaptive-Regime 广泛搜索 - 2026-07-03

## 结论

没有任何冻结 finalist 同时通过 full 与最近三个月 locked OOS 的三项硬门槛，当前结论为 `NO-GO / not promoted / not live-ready`。

- finalists：`700`；prefit pass：`0`；locked target pass：`0`。
- 目标：年化权益倍率 `>=10.0x`（annual return `>=900%`）、胜率 `>=50%`、最大回撤严格小于 `20%`。

## 数据质量

- Binance USD-M Futures `ETHUSDT` perpetual `1h`：`17520` 根闭合 K。
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
- random_configs：`600000`。
- generated_configs：`600768`。
- evaluated_configs：`343795`。
- prefit_eligible：`126636`。
- prefit_pass_observations：`0`。
- retained_single：`1200`。
- retained_ensembles：`200`。
- locked_finalists：`700`。
- locked_target_pass：`0`。
- 机制：EMA/MACD、Donchian、Bollinger、RSI、Stochastic、CCI、Williams %R、EMA pullback、Keltner、squeeze、ADX/DI、rolling VWAP、momentum、wick rejection、ATR、RVOL、4h/12h/1d regime、funding filter、fixed/risk sizing、fixed/trailing exit。

## 最佳冻结 finalist

- id：`ENS__ETH_1H_AR_R594637__ETH_1H_AR_R087976`；kind/style：`ensemble` / `bb_break+rsi_reversal`。
- full：annual `2.25x`，return `356.15%`，DD `-20.87%`，win `67.89%`，trades `109`，PF `2.316`。
- locked OOS：annual `0.52x`，return `-15.05%`，DD `-20.87%`，win `14.29%`，trades `7`，PF `0.154`。
- hard gate：`False`。

## 时间切片

| Window | Annual | Return | DD | Win | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `train` | `2.82x` | `199.08%` | `-16.29%` | `72.46%` | `69` | `2.598` |
| `validation` | `2.80x` | `79.54%` | `-11.43%` | `69.70%` | `33` | `2.922` |
| `locked_holdout` | `0.52x` | `-15.05%` | `-20.87%` | `14.29%` | `7` | `0.154` |
| `full` | `2.25x` | `356.15%` | `-20.87%` | `67.89%` | `109` | `2.316` |
| `last_30d` | `0.36x` | `-8.10%` | `-14.39%` | `33.33%` | `3` | `0.264` |
| `last_60d` | `0.59x` | `-8.21%` | `-14.50%` | `25.00%` | `4` | `0.261` |
| `last_90d` | `0.52x` | `-15.05%` | `-20.87%` | `14.29%` | `7` | `0.154` |
| `rolling_block_01` | `1.03x` | `0.27%` | `-2.48%` | `100.00%` | `1` | `inf` |
| `rolling_block_02` | `0.75x` | `-2.29%` | `-10.57%` | `40.00%` | `5` | `0.819` |
| `rolling_block_03` | `2.75x` | `8.67%` | `-6.42%` | `50.00%` | `4` | `2.448` |
| `rolling_block_04` | `7.54x` | `18.04%` | `-6.55%` | `62.50%` | `8` | `6.293` |
| `rolling_block_05` | `1.65x` | `4.22%` | `-5.42%` | `100.00%` | `2` | `inf` |
| `rolling_block_06` | `0.25x` | `-10.86%` | `-13.98%` | `57.14%` | `7` | `0.467` |
| `rolling_block_07` | `3.57x` | `11.02%` | `-10.90%` | `66.67%` | `6` | `2.890` |
| `rolling_block_08` | `15.27x` | `25.09%` | `-1.01%` | `100.00%` | `5` | `inf` |
| `rolling_block_09` | `0.84x` | `-1.43%` | `-15.80%` | `57.14%` | `7` | `0.987` |
| `rolling_block_10` | `6.59x` | `16.75%` | `-9.21%` | `87.50%` | `8` | `3.081` |
| `rolling_block_11` | `1.73x` | `4.61%` | `-3.19%` | `100.00%` | `5` | `inf` |
| `rolling_block_12` | `14.35x` | `24.46%` | `-9.36%` | `75.00%` | `8` | `6.688` |
| `rolling_block_13` | `12.57x` | `23.11%` | `-3.69%` | `100.00%` | `3` | `inf` |
| `rolling_block_14` | `3.50x` | `10.84%` | `-2.95%` | `100.00%` | `2` | `inf` |
| `rolling_block_15` | `1.19x` | `1.46%` | `-9.57%` | `60.00%` | `5` | `1.196` |
| `rolling_block_16` | `2.33x` | `7.18%` | `-7.92%` | `60.00%` | `5` | `2.492` |
| `rolling_block_17` | `1.65x` | `4.18%` | `-7.36%` | `80.00%` | `5` | `1.828` |
| `rolling_block_18` | `0.44x` | `-6.44%` | `-7.50%` | `0.00%` | `1` | `0.000` |
| `rolling_block_19` | `20.96x` | `28.39%` | `-4.64%` | `85.71%` | `7` | `57.187` |
| `rolling_block_20` | `7.65x` | `18.19%` | `-5.74%` | `55.56%` | `9` | `4.582` |
| `rolling_block_21` | `0.42x` | `-6.92%` | `-10.87%` | `0.00%` | `3` | `0.000` |
| `rolling_block_22` | `1.00x` | `0.00%` | `0.00%` | `0.00%` | `0` | `0.000` |
| `rolling_block_23` | `0.29x` | `-8.10%` | `-14.39%` | `33.33%` | `3` | `0.264` |

## Promotion 边界

locked hard gate 未通过，禁止标记为 candidate、paper-live、dry-run、handoff 或 live。

## 产物

- `research/eth/1h-adaptive-regime/artifacts/eth_1h_adaptive_regime_search_2026-07-03.json`
- `research/eth/1h-adaptive-regime/artifacts/eth_1h_adaptive_regime_prefit_2026-07-03.csv`
- `research/eth/1h-adaptive-regime/artifacts/eth_1h_adaptive_regime_ranking_2026-07-03.csv`
- `research/eth/1h-adaptive-regime/artifacts/eth_1h_adaptive_regime_slices_2026-07-03.csv`
- `research/eth/1h-adaptive-regime/artifacts/eth_1h_adaptive_regime_top_trades_2026-07-03.csv`
