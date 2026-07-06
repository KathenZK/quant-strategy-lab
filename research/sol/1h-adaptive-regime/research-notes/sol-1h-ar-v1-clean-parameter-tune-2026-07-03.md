# SOL-1H-Adaptive-Regime-V1 Clean 参数微调 - 2026-07-03

## 结论

选择规则：`strict_higher_return_lower_dd_moderate_win_k2_slip8_robust`。调参只使用 train/validation/prefit；reused holdout 在冻结后读取。

- 每腿随机样本：`250000`；组合评估：`160000`；严格收益更高且回撤更小观察：`936`。
- 严格改善候选：`600`；同时通过 K+2/8 bps prefit 稳健门槛：`395`。

## V1 与冻结微调观察

| Window | V1 annual | V1 DD | V1 win | Tune annual | Tune DD | Tune win | Tune trades |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `train` | `2.4859x` | `-17.90%` | `78.43%` | `6.4788x` | `-18.81%` | `86.21%` | `29` |
| `validation` | `2.7805x` | `-10.31%` | `80.00%` | `4.5171x` | `-16.84%` | `84.62%` | `13` |
| `prefit` | `2.5852x` | `-18.86%` | `79.07%` | `5.7104x` | `-18.81%` | `85.71%` | `42` |
| `reused_holdout` | `0.7129x` | `-16.19%` | `50.00%` | `0.1607x` | `-42.87%` | `0.00%` | `3` |
| `current_full` | `2.1786x` | `-18.86%` | `76.60%` | `3.5535x` | `-42.87%` | `80.00%` | `45` |

## 冻结 clean 参数

### Leg 1

- `cooldown_bars` = `48`
- `ema_htf` = `233`
- `fixed_leverage` = `5.0`
- `htf_mode` = `h4`
- `indicator_window` = `72`
- `macd_fast` = `21`
- `macd_signal` = `9`
- `macd_slow` = `55`
- `max_adx` = `36.0`
- `max_aligned_funding_bps` = `8.0`
- `max_atr_bps` = `300.0`
- `max_dist_ema_bps` = `10000.0`
- `max_hold_bars` = `18`
- `min_adx` = `8.0`
- `min_atr_bps` = `125.0`
- `min_dir_roc_bps` = `-200.0`
- `min_rvol` = `0.0`
- `require_macd_turn` = `False`
- `roc_window` = `3`
- `sl_atr` = `5.0`
- `tp_atr` = `2.0`

### Leg 2

- `band_k` = `1.25`
- `cooldown_bars` = `24`
- `ema_htf` = `89`
- `fixed_leverage` = `4.0`
- `htf_mode` = `h12`
- `indicator_window` = `72`
- `max_adx` = `32.0`
- `max_aligned_funding_bps` = `10000.0`
- `max_atr_bps` = `600.0`
- `max_dist_ema_bps` = `200.0`
- `max_hold_bars` = `18`
- `min_adx` = `16.0`
- `min_atr_bps` = `125.0`
- `min_dir_roc_bps` = `-300.0`
- `min_rvol` = `0.6`
- `require_macd_turn` = `True`
- `sl_atr` = `2.0`
- `trail_activation_atr` = `2.0`
- `trail_atr` = `0.5`

## 延迟与成本审计

| Scenario | Prefit annual | Prefit DD | Prefit win | Reused OOS annual | Reused OOS DD | Full annual | Full DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `base_k1` | `5.7104x` | `-18.81%` | `85.71%` | `0.1607x` | `-42.87%` | `3.5535x` | `-42.87%` |
| `delay_k2` | `3.9124x` | `-25.00%` | `76.19%` | `0.0945x` | `-45.28%` | `2.3857x` | `-45.28%` |
| `delay_k3` | `4.2019x` | `-27.01%` | `78.57%` | `0.1092x` | `-47.03%` | `2.5873x` | `-47.03%` |
| `slip_8bps` | `5.3073x` | `-19.27%` | `85.71%` | `0.1553x` | `-43.24%` | `3.3198x` | `-43.24%` |
| `slip_12bps` | `4.9316x` | `-19.73%` | `85.71%` | `0.1500x` | `-43.61%` | `3.1009x` | `-43.61%` |
| `fee12_slip8` | `5.0804x` | `-19.72%` | `85.71%` | `0.1515x` | `-43.60%` | `3.1860x` | `-43.60%` |
| `double_cost` | `4.2622x` | `-21.51%` | `83.33%` | `0.1373x` | `-45.03%` | `2.7004x` | `-45.03%` |

## 研究边界

- 这是 V1 clean surface 的 tuned observation，不自动登记为 V1.1/V2。
- reused holdout 已在 V1 登记时解锁，不是新鲜 OOS，不能参与选择或删参。
- 只有同时满足收益改善、回撤改善、适中胜率、延迟/成本稳健性与新增 forward trades，才允许讨论 promotion。

## 机器证据

- `artifacts/sol_1h_ar_v1_clean_tune_2026-07-03.json`
- `artifacts/sol_1h_ar_v1_tune_leg_pool_2026-07-03.csv`
- `artifacts/sol_1h_ar_v1_tune_strategies_2026-07-03.csv`
- `artifacts/sol_1h_ar_v1_tune_selected_trades_2026-07-03.csv`

复现：

```bash
uv run python research/sol/1h-adaptive-regime/scripts/research_sol_1h_ar_v1_clean_tune.py
```
