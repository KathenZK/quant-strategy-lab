# SOL-1H-Adaptive-Regime 高胜率硬目标搜索 - 2026-07-07

## 结论

没有任何冻结 finalist 同时通过 full 与最近三个月 reused holdout 的三项硬门槛，本轮结论为 `NO-GO / not promoted / not live-ready`。

- finalists：`450`；prefit pass：`0`；reused-holdout target pass：`0`；同时通过 last-1y 硬形状的 finalists：`0`。
- 目标：年化权益倍率 `>= 10.0x`（annual return `>= 900%`）、胜率 `>= 80%`、最大回撤严格小于 `20%`。

## OOS 状态声明

- 最近三个月窗口已在 2026-07-03 的 V1 广搜揭盲，本轮属于 reused holdout，不是新鲜 locked OOS。
- 本轮选择、打分、保留和 ensemble 仍只使用 train + validation；reused holdout 只对冻结 finalists 评估一次，不参与选择。
- 即使命中硬门槛，也必须先补新鲜 forward 数据与 live-executable 审计，才能讨论 promotion。

## 数据质量

- Binance USD-M Futures `SOLUSDT` perpetual `1h`：`17520` 根闭合 K（冻结研究帧，与 V1 相同）。
- UTC：`2024-07-03T05:00:00+00:00` 至 `2026-07-03T04:00:00+00:00`。
- missing=`0`，duplicate=`0`，funding rows=`2190`。

## 时间切分

- train：`2024-08-17T05:00:00+00:00` 至 `2025-09-07T07:24:00+00:00`。
- validation：`2025-09-07T07:24:00+00:00` 至 `2026-04-03T05:00:00+00:00`。
- reused holdout（最近三个月，V1 已揭盲）：`2026-04-03T05:00:00+00:00` 至 `2026-07-03T05:00:00+00:00`。

## 执行与成本

- 闭合 `1h` K 生成信号，下一根 open 市价入场；单仓、不加仓。
- 入场后立即具备 ATR stop/TP；同 K 双触发 stop-first；open 穿越 stop 按 open 成交。
- trailing 仅在完整 K 结束后更新，更新后的 stop 从下一根 K 生效。
- fee `0.1000%/fill`，slippage `0.0400%/fill`，另逐笔计入真实 Binance funding。

## 搜索覆盖

- curated_configs：`768`。
- random_configs：`600000`。
- generated_configs：`600768`。
- evaluated_configs：`370589`。
- prefit_eligible：`141925`。
- prefit_pass_observations：`0`。
- retained_single：`600`。
- retained_ensembles：`200`。
- holdout_finalists：`450`。
- reused_holdout_target_pass：`0`。
- last_1y_hard_pass_among_target_pass：`0`。
- 打分向高胜率倾斜：win-rate 奖励封顶 `90%`，低于 `80%` 逐项罚分；机制面与 V1 广搜相同。

## 最佳冻结 finalist

- id：`ENS__SOL_1H_AR_HW_R132002__SOL_1H_AR_HW_R243705`；kind/style：`ensemble` / `donchian_break+vwap_revert`。
- full：annual `2.07x`，return `290.00%`，DD `-17.41%`，win `93.91%`，trades `115`，PF `3.907`。
- reused holdout：annual `0.70x`，return `-8.53%`，DD `-15.69%`，win `66.67%`，trades `6`，PF `0.398`。
- hard gate：`False`。

## 标准近期分片（锚定数据集末端，仅审计不选参）

| Window | Annual | Return | DD | Win | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `last_1d` | `1.00x` | `0.00%` | `0.00%` | `0.00%` | `0` | `0.000` |
| `last_7d` | `0.00x` | `-12.46%` | `-15.69%` | `33.33%` | `3` | `0.080` |
| `last_1m` | `0.34x` | `-8.53%` | `-15.69%` | `66.67%` | `6` | `0.398` |
| `last_3m` | `0.70x` | `-8.53%` | `-15.69%` | `66.67%` | `6` | `0.398` |
| `last_6m` | `1.03x` | `1.72%` | `-17.29%` | `86.96%` | `23` | `1.128` |
| `last_1y` | `1.60x` | `60.19%` | `-17.41%` | `92.31%` | `52` | `2.561` |

## 时间切片（引擎标准窗口）

| Window | Annual | Return | DD | Win | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `train` | `2.66x` | `181.26%` | `-17.41%` | `95.65%` | `69` | `7.384` |
| `validation` | `2.08x` | `51.59%` | `-17.29%` | `95.00%` | `40` | `3.426` |
| `locked_holdout` | `0.70x` | `-8.53%` | `-15.69%` | `66.67%` | `6` | `0.398` |
| `full` | `2.07x` | `290.00%` | `-17.41%` | `93.91%` | `115` | `3.907` |
| `last_30d` | `0.34x` | `-8.53%` | `-15.69%` | `66.67%` | `6` | `0.398` |
| `last_60d` | `0.58x` | `-8.53%` | `-15.69%` | `66.67%` | `6` | `0.398` |
| `last_90d` | `0.70x` | `-8.53%` | `-15.69%` | `66.67%` | `6` | `0.398` |
| `rolling_block_01` | `2.16x` | `6.53%` | `-10.23%` | `100.00%` | `4` | `inf` |
| `rolling_block_02` | `3.02x` | `9.50%` | `-6.08%` | `100.00%` | `5` | `inf` |
| `rolling_block_03` | `1.69x` | `4.38%` | `-9.08%` | `100.00%` | `2` | `inf` |
| `rolling_block_04` | `4.20x` | `12.50%` | `-12.75%` | `100.00%` | `5` | `inf` |
| `rolling_block_05` | `6.49x` | `16.60%` | `-3.45%` | `100.00%` | `10` | `inf` |
| `rolling_block_06` | `3.12x` | `9.79%` | `-3.95%` | `100.00%` | `5` | `inf` |
| `rolling_block_07` | `4.42x` | `12.97%` | `-8.77%` | `84.62%` | `13` | `2.723` |
| `rolling_block_08` | `7.17x` | `17.56%` | `-13.00%` | `93.75%` | `16` | `2.838` |
| `rolling_block_09` | `1.00x` | `0.00%` | `0.00%` | `0.00%` | `0` | `0.000` |
| `rolling_block_10` | `1.14x` | `1.10%` | `-0.62%` | `100.00%` | `1` | `inf` |
| `rolling_block_11` | `1.50x` | `3.39%` | `-9.73%` | `100.00%` | `2` | `inf` |
| `rolling_block_12` | `3.99x` | `12.04%` | `-5.39%` | `100.00%` | `5` | `inf` |
| `rolling_block_13` | `1.45x` | `3.11%` | `-17.41%` | `100.00%` | `1` | `inf` |
| `rolling_block_14` | `2.36x` | `7.29%` | `-3.23%` | `100.00%` | `4` | `inf` |
| `rolling_block_15` | `5.13x` | `14.37%` | `-2.69%` | `100.00%` | `8` | `inf` |
| `rolling_block_16` | `2.27x` | `6.96%` | `-9.02%` | `87.50%` | `8` | `2.962` |
| `rolling_block_17` | `1.59x` | `3.87%` | `-2.68%` | `100.00%` | `3` | `inf` |
| `rolling_block_18` | `1.64x` | `4.14%` | `-1.15%` | `100.00%` | `3` | `inf` |
| `rolling_block_19` | `1.00x` | `0.03%` | `-17.29%` | `90.00%` | `10` | `1.092` |
| `rolling_block_20` | `2.21x` | `6.74%` | `-4.38%` | `100.00%` | `4` | `inf` |
| `rolling_block_21` | `1.00x` | `0.00%` | `0.00%` | `0.00%` | `0` | `0.000` |
| `rolling_block_22` | `1.00x` | `0.00%` | `0.00%` | `0.00%` | `0` | `0.000` |
| `rolling_block_23` | `0.27x` | `-8.53%` | `-15.69%` | `66.67%` | `6` | `0.398` |

## Promotion 边界

reused-holdout hard gate 未通过，禁止标记为 candidate、paper-live、dry-run、handoff 或 live。

## 产物

- `research/sol/1h-adaptive-regime/artifacts/sol_1h_ar_high_win_search_2026-07-07.json`
- `research/sol/1h-adaptive-regime/artifacts/sol_1h_ar_high_win_prefit_2026-07-07.csv`
- `research/sol/1h-adaptive-regime/artifacts/sol_1h_ar_high_win_ranking_2026-07-07.csv`
- `research/sol/1h-adaptive-regime/artifacts/sol_1h_ar_high_win_slices_2026-07-07.csv`
- `research/sol/1h-adaptive-regime/artifacts/sol_1h_ar_high_win_top_trades_2026-07-07.csv`

复现：

```bash
uv run python research/sol/1h-adaptive-regime/scripts/research_sol_1h_ar_high_win_target_search.py
```
