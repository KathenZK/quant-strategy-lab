# TRX-1H-Adaptive-Regime-V1 Clean 参数联合微调 - 2026-07-05

## 结论

本轮只使用 train/validation/prefit 在 V1 全消融后的 clean 参数面选参；reused holdout 和近期分片均在候选冻结后读取，不参与排序。

- 选择规则：`strict_prefit_improvement_then_robust_score`。
- MACD/Stoch unique configs：`2001` / `2001`；组合评估 `2500`。
- prefit 同时收益更高、回撤更小、胜率>=55%的 pair observations：`4`。
- 完成额外一根延迟、8 bps、延迟+8 bps 三重 prefit 审计：`50`；全窗口通过：`0`。
- 冻结邻域：`177` 个 one-field variants，正收益/DD<20%/win>=50% 全窗口通过 `131`。

## V1 与冻结微调观察

| Window | V1 annual | V1 DD | V1 win | Tune annual | Tune DD | Tune win | Tune trades |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `train` | `9.1982x` | `-16.34%` | `90.77%` | `8.9133x` | `-13.92%` | `89.06%` | `64` |
| `validation` | `1.7925x` | `-19.84%` | `80.65%` | `2.4312x` | `-15.12%` | `83.87%` | `31` |
| `prefit` | `5.1894x` | `-19.84%` | `87.50%` | `5.6566x` | `-15.12%` | `87.37%` | `95` |
| `reused_holdout` | `0.8445x` | `-11.42%` | `75.00%` | `0.8061x` | `-11.80%` | `75.00%` | `8` |
| `current_full` | `4.0772x` | `-19.84%` | `86.54%` | `4.3666x` | `-15.12%` | `86.41%` | `103` |

## 冻结参数

### MACD clean

- `ema_htf` = `377`
- `roc_window` = `12`
- `macd_fast` = `34`
- `macd_slow` = `89`
- `macd_signal` = `13`
- `min_adx` = `12.0`
- `max_adx` = `28.0`
- `min_rvol` = `1.5`
- `max_atr_bps` = `200.0`
- `min_dir_roc_bps` = `-100.0`
- `max_dist_ema_bps` = `1000.0`
- `htf_mode` = `h12`
- `require_macd_turn` = `True`
- `tp_atr` = `2.0`
- `sl_atr` = `4.0`
- `max_hold_bars` = `168`
- `cooldown_bars` = `3`
- `entry_delay_bars` = `1`
- `fixed_leverage` = `4.0`

### Stochastic clean

- `side_mode` = `long`
- `ema_htf` = `55`
- `indicator_window` = `21`
- `threshold_low` = `25.0`
- `threshold_high` = `85.0`
- `roc_window` = `3`
- `max_adx` = `30.0`
- `min_rvol` = `1.0`
- `min_dir_roc_bps` = `-200.0`
- `require_body_dir` = `True`
- `sl_atr` = `5.0`
- `trail_activation_atr` = `3.0`
- `trail_atr` = `1.25`
- `max_hold_bars` = `168`
- `cooldown_bars` = `24`
- `entry_delay_bars` = `2`
- `fixed_leverage` = `3.0`

## 延迟、成本与 reused holdout

| Scenario | Prefit annual | Prefit DD | Prefit win | Reused holdout return | Reused holdout DD | Full annual | Full DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `base` | `5.6566x` | `-15.12%` | `87.37%` | `-5.23%` | `-11.80%` | `4.3666x` | `-15.12%` |
| `one_extra_bar` | `2.6279x` | `-34.46%` | `84.62%` | `-3.06%` | `-17.19%` | `2.2734x` | `-34.46%` |
| `slippage_8bps` | `3.4833x` | `-20.06%` | `84.04%` | `-20.60%` | `-24.72%` | `2.6097x` | `-24.72%` |
| `one_extra_bar_slippage_8bps` | `2.0896x` | `-34.84%` | `82.22%` | `-4.36%` | `-17.30%` | `1.8503x` | `-34.84%` |
| `fee15_slippage8` | `2.8672x` | `-22.27%` | `84.04%` | `-22.86%` | `-25.84%` | `2.1707x` | `-27.31%` |

## 标准近期分片

| Slice | Annual | Return | DD | Win | Trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| `last_1d` | `1.0000x` | `0.00%` | `0.00%` | `0.00%` | `0` |
| `last_7d` | `1.0000x` | `0.00%` | `0.00%` | `0.00%` | `0` |
| `last_1m` | `0.2469x` | `-10.85%` | `-11.80%` | `50.00%` | `4` |
| `last_3m` | `0.8061x` | `-5.23%` | `-11.80%` | `75.00%` | `8` |
| `last_6m` | `1.3889x` | `17.68%` | `-11.80%` | `77.78%` | `18` |
| `last_1y` | `1.9980x` | `99.70%` | `-15.12%` | `84.00%` | `50` |

## 研究边界

- 该结果是 V1 clean surface 的 tuned observation，不自动登记为 V1.1/V2。
- reused holdout 已在 V1 初始研究中揭盲，只能做冻结后失败审计，不能作为 fresh OOS。
- 只有在新增 forward trades 和生产 runner 证据存在后，才允许讨论 candidate/paper-live/live。

## 机器证据

- `artifacts/trx_1h_ar_v1_clean_tune_2026-07-05.json`
- `artifacts/trx_1h_ar_v1_tune_macd_pool_2026-07-05.csv`
- `artifacts/trx_1h_ar_v1_tune_stoch_pool_2026-07-05.csv`
- `artifacts/trx_1h_ar_v1_tune_pairs_2026-07-05.csv`
- `artifacts/trx_1h_ar_v1_tune_selected_trades_2026-07-05.csv`
- `artifacts/trx_1h_ar_v1_tune_selected_slices_2026-07-05.csv`
- `artifacts/trx_1h_ar_v1_tune_neighborhood_2026-07-05.csv`

复现：

```bash
uv run python research/trx/1h-adaptive-regime/scripts/research_trx_1h_ar_v1_clean_tune.py
```
