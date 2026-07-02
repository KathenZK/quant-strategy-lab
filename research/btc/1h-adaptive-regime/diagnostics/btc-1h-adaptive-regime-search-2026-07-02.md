# BTC-1H-Adaptive-Regime 广泛搜索 - 2026-07-02

## 结论

没有任何冻结 finalist 同时通过 full 与最近三个月 locked OOS 的三项硬门槛，当前结论为 `NO-GO / not promoted / not live-ready`。

- finalists：`450`；prefit pass：`0`；locked target pass：`0`。
- 目标：年化权益倍率 `>=10.0x`（annual return `>=900%`）、胜率 `>=50%`、最大回撤严格小于 `20%`。

## 数据质量

- Binance USD-M Futures `BTCUSDT` perpetual `1h`：`17520` 根闭合 K。
- UTC：`2024-07-02T10:00:00+00:00` 至 `2026-07-02T09:00:00+00:00`。
- missing=`0`，duplicate=`0`，funding rows=`2190`。

## 防泄漏时间切分

- warmup/raw start：`2024-07-02T10:00:00+00:00` / `2024-08-16T10:00:00+00:00`。
- train：`2024-08-16T10:00:00+00:00` 至 `2025-09-06T12:24:00+00:00`。
- validation：`2025-09-06T12:24:00+00:00` 至 `2026-04-02T10:00:00+00:00`。
- locked OOS（固定最近三个月）：`2026-04-02T10:00:00+00:00` 至 `2026-07-02T10:00:00+00:00`。
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
- evaluated_configs：`131565`。
- prefit_eligible：`41898`。
- prefit_pass_observations：`0`。
- retained_single：`600`。
- retained_ensembles：`200`。
- locked_finalists：`450`。
- locked_target_pass：`0`。
- 机制：EMA/MACD、Donchian、Bollinger、RSI、Stochastic、CCI、Williams %R、EMA pullback、Keltner、squeeze、ADX/DI、rolling VWAP、momentum、wick rejection、ATR、RVOL、4h/12h/1d regime、funding filter、fixed/risk sizing、fixed/trailing exit。

## 最佳冻结 finalist

- id：`ENS__BTC_1H_AR_R199379__BTC_1H_AR_R130259`；kind/style：`ensemble` / `keltner_break+cci_reversal`。
- full：annual `1.94x`，return `246.95%`，DD `-42.73%`，win `64.21%`，trades `95`，PF `1.765`。
- locked OOS：annual `0.17x`，return `-35.74%`，DD `-42.73%`，win `38.46%`，trades `13`，PF `0.304`。
- hard gate：`False`。

## 时间切片

| Window | Annual | Return | DD | Win | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `train` | `2.58x` | `172.05%` | `-15.13%` | `68.00%` | `50` | `2.372` |
| `validation` | `3.33x` | `98.46%` | `-18.68%` | `68.75%` | `32` | `2.406` |
| `locked_holdout` | `0.17x` | `-35.74%` | `-42.73%` | `38.46%` | `13` | `0.304` |
| `full` | `1.94x` | `246.95%` | `-42.73%` | `64.21%` | `95` | `1.765` |
| `last_30d` | `0.03x` | `-25.04%` | `-35.71%` | `33.33%` | `6` | `0.309` |
| `last_60d` | `0.15x` | `-26.66%` | `-35.71%` | `45.45%` | `11` | `0.391` |
| `last_90d` | `0.17x` | `-35.74%` | `-42.73%` | `38.46%` | `13` | `0.304` |
| `rolling_block_01` | `0.88x` | `-1.03%` | `-15.13%` | `33.33%` | `3` | `1.047` |
| `rolling_block_02` | `2.35x` | `7.28%` | `-9.82%` | `50.00%` | `4` | `2.063` |
| `rolling_block_03` | `7.67x` | `18.21%` | `-7.72%` | `85.71%` | `7` | `5.452` |
| `rolling_block_04` | `1.13x` | `1.04%` | `-6.55%` | `33.33%` | `3` | `1.199` |
| `rolling_block_05` | `0.58x` | `-4.40%` | `-14.63%` | `60.00%` | `5` | `0.618` |
| `rolling_block_06` | `134.75x` | `49.59%` | `-8.27%` | `83.33%` | `6` | `11.489` |
| `rolling_block_07` | `235.03x` | `56.59%` | `-8.68%` | `100.00%` | `8` | `inf` |
| `rolling_block_08` | `0.68x` | `-3.07%` | `-13.66%` | `50.00%` | `4` | `0.693` |
| `rolling_block_09` | `1.29x` | `2.10%` | `-1.26%` | `100.00%` | `1` | `inf` |
| `rolling_block_10` | `0.88x` | `-1.02%` | `-6.16%` | `33.33%` | `3` | `0.921` |
| `rolling_block_11` | `1.39x` | `2.76%` | `-5.05%` | `100.00%` | `2` | `inf` |
| `rolling_block_12` | `2.04x` | `6.01%` | `-4.70%` | `66.67%` | `3` | `2.397` |
| `rolling_block_13` | `0.27x` | `-10.22%` | `-10.40%` | `0.00%` | `1` | `0.000` |
| `rolling_block_14` | `1.17x` | `1.33%` | `-4.92%` | `66.67%` | `3` | `1.781` |
| `rolling_block_15` | `35.49x` | `34.06%` | `-9.19%` | `85.71%` | `7` | `8.884` |
| `rolling_block_16` | `0.60x` | `-4.12%` | `-18.68%` | `50.00%` | `6` | `0.885` |
| `rolling_block_17` | `2.04x` | `6.05%` | `-5.36%` | `66.67%` | `3` | `2.526` |
| `rolling_block_18` | `6.83x` | `17.09%` | `-7.33%` | `100.00%` | `4` | `inf` |
| `rolling_block_19` | `8.96x` | `19.74%` | `-15.31%` | `60.00%` | `5` | `2.696` |
| `rolling_block_20` | `1.35x` | `2.48%` | `-14.93%` | `50.00%` | `4` | `1.324` |
| `rolling_block_21` | `0.20x` | `-12.38%` | `-12.83%` | `0.00%` | `2` | `0.000` |
| `rolling_block_22` | `0.06x` | `-20.86%` | `-25.43%` | `57.14%` | `7` | `0.333` |
| `rolling_block_23` | `0.33x` | `-7.33%` | `-19.97%` | `25.00%` | `4` | `0.513` |

## Promotion 边界

locked hard gate 未通过，禁止标记为 candidate、paper-live、dry-run、handoff 或 live。

## 产物

- `research/btc/1h-adaptive-regime/artifacts/btc_1h_adaptive_regime_search_2026-07-02.json`
- `research/btc/1h-adaptive-regime/artifacts/btc_1h_adaptive_regime_prefit_2026-07-02.csv`
- `research/btc/1h-adaptive-regime/artifacts/btc_1h_adaptive_regime_ranking_2026-07-02.csv`
- `research/btc/1h-adaptive-regime/artifacts/btc_1h_adaptive_regime_slices_2026-07-02.csv`
- `research/btc/1h-adaptive-regime/artifacts/btc_1h_adaptive_regime_top_trades_2026-07-02.csv`
