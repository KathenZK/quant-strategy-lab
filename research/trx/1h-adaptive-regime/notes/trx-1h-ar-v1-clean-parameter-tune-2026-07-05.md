# TRX-1H-Adaptive-Regime-V1 Clean 参数联合微调 - 2026-07-05

## 结论

本轮只使用 train/validation/prefit 在 V1 全消融后的 clean 参数面选参；reused holdout 和近期分片均在候选冻结后读取，不参与排序。

- 选择规则：`strict_prefit_improvement_plus_delay_slip8_combined_all_window_gate`。
- MACD/Stoch unique configs：`200001` / `200001`；组合评估 `202500`。
- 腿级双门槛：custom score 与家族原生 priority 必须同时有效；MACD/Stoch 最终 eligible：`146902` / `88997`。
- prefit 同时收益更高、回撤更小、胜率>=55%的 pair observations：`101`。
- 完成额外一根延迟、8 bps、延迟+8 bps 三重 prefit 审计：`800`；全窗口通过：`4`。
- 冻结邻域：`177` 个 one-field variants，正收益/DD<20%/win>=50% 全窗口通过 `108`。

## V1 与冻结微调观察

| Window | V1 annual | V1 DD | V1 win | Tune annual | Tune DD | Tune win | Tune trades |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `train` | `9.1982x` | `-16.34%` | `90.77%` | `5.5179x` | `-19.00%` | `76.92%` | `52` |
| `validation` | `1.7925x` | `-19.84%` | `80.65%` | `6.5060x` | `-12.77%` | `90.32%` | `31` |
| `prefit` | `5.1894x` | `-19.84%` | `87.50%` | `5.8454x` | `-19.00%` | `81.93%` | `83` |
| `reused_holdout` | `0.8445x` | `-11.42%` | `75.00%` | `1.0074x` | `-9.81%` | `55.56%` | `9` |
| `current_full` | `4.0772x` | `-19.84%` | `86.54%` | `4.6277x` | `-19.00%` | `79.35%` | `92` |

## 冻结参数

### MACD clean

- `ema_htf` = `89`
- `roc_window` = `3`
- `macd_fast` = `12`
- `macd_slow` = `26`
- `macd_signal` = `9`
- `min_adx` = `16.0`
- `max_adx` = `24.0`
- `min_rvol` = `1.25`
- `max_atr_bps` = `200.0`
- `min_dir_roc_bps` = `-10000.0`
- `max_dist_ema_bps` = `2500.0`
- `htf_mode` = `h12`
- `require_macd_turn` = `True`
- `tp_atr` = `4.0`
- `sl_atr` = `4.0`
- `max_hold_bars` = `48`
- `cooldown_bars` = `0`
- `entry_delay_bars` = `1`
- `fixed_leverage` = `3.0`

### Stochastic clean

- `side_mode` = `both`
- `ema_htf` = `233`
- `indicator_window` = `21`
- `threshold_low` = `25.0`
- `threshold_high` = `90.0`
- `roc_window` = `3`
- `max_adx` = `24.0`
- `min_rvol` = `1.0`
- `min_dir_roc_bps` = `-300.0`
- `require_body_dir` = `True`
- `sl_atr` = `6.0`
- `trail_activation_atr` = `3.0`
- `trail_atr` = `2.0`
- `max_hold_bars` = `120`
- `cooldown_bars` = `6`
- `entry_delay_bars` = `2`
- `fixed_leverage` = `3.5`

## 延迟、成本与 reused holdout

| Scenario | Prefit annual | Prefit DD | Prefit win | Reused holdout return | Reused holdout DD | Full annual | Full DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `base` | `5.8454x` | `-19.00%` | `81.93%` | `0.18%` | `-9.81%` | `4.6277x` | `-19.00%` |
| `one_extra_bar` | `3.6947x` | `-17.71%` | `76.47%` | `8.61%` | `-7.09%` | `3.2456x` | `-17.71%` |
| `slippage_8bps` | `4.8701x` | `-19.33%` | `81.71%` | `-1.39%` | `-10.59%` | `3.9170x` | `-19.33%` |
| `one_extra_bar_slippage_8bps` | `3.3327x` | `-17.84%` | `77.38%` | `6.71%` | `-7.52%` | `2.9403x` | `-17.84%` |
| `fee15_slippage8` | `4.1469x` | `-19.87%` | `81.71%` | `-4.08%` | `-12.44%` | `3.3575x` | `-19.87%` |

## 标准近期分片

| Slice | Annual | Return | DD | Win | Trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| `last_1d` | `1.0000x` | `0.00%` | `0.00%` | `0.00%` | `0` |
| `last_7d` | `3.5092x` | `2.44%` | `-2.54%` | `100.00%` | `1` |
| `last_1m` | `1.3403x` | `2.44%` | `-2.54%` | `100.00%` | `1` |
| `last_3m` | `1.0074x` | `0.18%` | `-9.81%` | `55.56%` | `9` |
| `last_6m` | `3.2106x` | `78.25%` | `-9.81%` | `78.26%` | `23` |
| `last_1y` | `3.1199x` | `211.75%` | `-12.77%` | `81.25%` | `48` |

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
