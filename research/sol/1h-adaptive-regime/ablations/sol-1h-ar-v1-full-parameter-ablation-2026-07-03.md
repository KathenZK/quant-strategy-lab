# SOL-1H-Adaptive-Regime-V1 全参数消融 - 2026-07-03

## 结论

已覆盖 V1 `2` 条腿全部 `78` 个 StrategyConfig 字段槽，coverage missing 为 `0`。

分类结果：`{'active_tunable': 40, 'baseline_fixed_remove': 23, 'contract_fixed': 12, 'neutral_fixed_remove': 3}`。只有 `active_tunable` 进入 clean tuning surface；其余字段删除或硬编码。

one-at-a-time 变体中，严格满足 prefit 年化更高、回撤更小、胜率 >=50%、train/validation 同正且 validation DD<20% 的行数为 `8`。

## V1 基线

| Window | Annual | Return | DD | Win | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `train` | `2.4859x` | `161.85%` | `-17.90%` | `78.43%` | `51` | `5.297` |
| `validation` | `2.7805x` | `78.97%` | `-10.31%` | `80.00%` | `35` | `4.393` |
| `prefit` | `2.5852x` | `368.64%` | `-18.86%` | `79.07%` | `86` | `4.906` |
| `reused_holdout` | `0.7129x` | `-8.09%` | `-16.19%` | `50.00%` | `8` | `0.608` |
| `current_full` | `2.1786x` | `330.75%` | `-18.86%` | `76.60%` | `94` | `3.536` |

## 全字段覆盖与删参分类

| Component | Field | Baseline | Classification | Variants | Component equal | Merged equal | Strict improve |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `leg1_donchian_break` | `band_k` | `1.5` | `baseline_fixed_remove` | `11` | `11` | `11` | `0` |
| `leg1_donchian_break` | `cooldown_bars` | `12` | `active_tunable` | `7` | `0` | `0` | `0` |
| `leg1_donchian_break` | `ema_fast` | `89` | `baseline_fixed_remove` | `5` | `5` | `5` | `0` |
| `leg1_donchian_break` | `ema_htf` | `377` | `active_tunable` | `4` | `0` | `0` | `0` |
| `leg1_donchian_break` | `ema_slow` | `144` | `baseline_fixed_remove` | `2` | `2` | `2` | `0` |
| `leg1_donchian_break` | `entry_delay_bars` | `1` | `contract_fixed` | `2` | `0` | `0` | `0` |
| `leg1_donchian_break` | `exit_kind` | `fixed` | `contract_fixed` | `1` | `0` | `0` | `0` |
| `leg1_donchian_break` | `fixed_leverage` | `1.5` | `active_tunable` | `10` | `0` | `0` | `0` |
| `leg1_donchian_break` | `htf_mode` | `none` | `active_tunable` | `3` | `0` | `0` | `0` |
| `leg1_donchian_break` | `indicator_window` | `12` | `active_tunable` | `6` | `0` | `0` | `0` |
| `leg1_donchian_break` | `macd_fast` | `21` | `active_tunable` | `3` | `0` | `0` | `0` |
| `leg1_donchian_break` | `macd_signal` | `9` | `active_tunable` | `2` | `0` | `0` | `0` |
| `leg1_donchian_break` | `macd_slow` | `55` | `active_tunable` | `3` | `0` | `0` | `0` |
| `leg1_donchian_break` | `max_adx` | `100.0` | `active_tunable` | `4` | `0` | `0` | `0` |
| `leg1_donchian_break` | `max_aligned_funding_bps` | `1.0` | `active_tunable` | `5` | `2` | `2` | `0` |
| `leg1_donchian_break` | `max_atr_bps` | `10000.0` | `active_tunable` | `6` | `2` | `2` | `0` |
| `leg1_donchian_break` | `max_dist_ema_bps` | `10000.0` | `active_tunable` | `7` | `0` | `0` | `0` |
| `leg1_donchian_break` | `max_hold_bars` | `6` | `active_tunable` | `13` | `0` | `0` | `0` |
| `leg1_donchian_break` | `max_leverage` | `1.0` | `baseline_fixed_remove` | `8` | `8` | `8` | `0` |
| `leg1_donchian_break` | `min_adx` | `36.0` | `active_tunable` | `9` | `0` | `0` | `0` |
| `leg1_donchian_break` | `min_atr_bps` | `100.0` | `active_tunable` | `7` | `0` | `0` | `0` |
| `leg1_donchian_break` | `min_dir_roc_bps` | `50.0` | `active_tunable` | `9` | `0` | `0` | `0` |
| `leg1_donchian_break` | `min_rvol` | `1.0` | `active_tunable` | `7` | `0` | `0` | `0` |
| `leg1_donchian_break` | `name` | `SOL_1H_AR_R594184` | `contract_fixed` | `1` | `1` | `1` | `0` |
| `leg1_donchian_break` | `pullback_atr` | `-0.25` | `baseline_fixed_remove` | `7` | `7` | `7` | `0` |
| `leg1_donchian_break` | `require_body_dir` | `False` | `neutral_fixed_remove` | `1` | `1` | `1` | `0` |
| `leg1_donchian_break` | `require_macd_turn` | `True` | `active_tunable` | `1` | `0` | `0` | `0` |
| `leg1_donchian_break` | `risk_fraction` | `0.005` | `baseline_fixed_remove` | `9` | `9` | `9` | `0` |
| `leg1_donchian_break` | `roc_threshold_bps` | `200.0` | `baseline_fixed_remove` | `7` | `7` | `7` | `0` |
| `leg1_donchian_break` | `roc_window` | `3` | `active_tunable` | `6` | `0` | `0` | `0` |
| `leg1_donchian_break` | `side_mode` | `long` | `contract_fixed` | `2` | `0` | `0` | `0` |
| `leg1_donchian_break` | `sizing_kind` | `fixed` | `contract_fixed` | `1` | `0` | `0` | `0` |
| `leg1_donchian_break` | `sl_atr` | `5.0` | `active_tunable` | `10` | `2` | `2` | `3` |
| `leg1_donchian_break` | `style` | `donchian_break` | `contract_fixed` | `1` | `0` | `0` | `0` |
| `leg1_donchian_break` | `threshold_high` | `65.0` | `baseline_fixed_remove` | `13` | `13` | `13` | `0` |
| `leg1_donchian_break` | `threshold_low` | `30.0` | `baseline_fixed_remove` | `13` | `13` | `13` | `0` |
| `leg1_donchian_break` | `tp_atr` | `3.0` | `active_tunable` | `12` | `0` | `0` | `0` |
| `leg1_donchian_break` | `trail_activation_atr` | `1.5` | `baseline_fixed_remove` | `7` | `7` | `7` | `0` |
| `leg1_donchian_break` | `trail_atr` | `3.0` | `baseline_fixed_remove` | `9` | `9` | `9` | `0` |
| `leg2_bb_revert` | `band_k` | `2.0` | `active_tunable` | `11` | `0` | `0` | `0` |
| `leg2_bb_revert` | `cooldown_bars` | `24` | `active_tunable` | `7` | `0` | `0` | `0` |
| `leg2_bb_revert` | `ema_fast` | `144` | `baseline_fixed_remove` | `6` | `6` | `6` | `0` |
| `leg2_bb_revert` | `ema_htf` | `89` | `active_tunable` | `4` | `2` | `2` | `0` |
| `leg2_bb_revert` | `ema_slow` | `233` | `baseline_fixed_remove` | `1` | `1` | `1` | `0` |
| `leg2_bb_revert` | `entry_delay_bars` | `1` | `contract_fixed` | `2` | `0` | `0` | `0` |
| `leg2_bb_revert` | `exit_kind` | `trailing` | `contract_fixed` | `1` | `0` | `0` | `1` |
| `leg2_bb_revert` | `fixed_leverage` | `2.5` | `active_tunable` | `10` | `0` | `0` | `0` |
| `leg2_bb_revert` | `htf_mode` | `none` | `active_tunable` | `3` | `0` | `0` | `0` |
| `leg2_bb_revert` | `indicator_window` | `72` | `active_tunable` | `5` | `0` | `0` | `0` |
| `leg2_bb_revert` | `macd_fast` | `12` | `baseline_fixed_remove` | `3` | `3` | `3` | `0` |
| `leg2_bb_revert` | `macd_signal` | `9` | `baseline_fixed_remove` | `2` | `2` | `2` | `0` |
| `leg2_bb_revert` | `macd_slow` | `26` | `baseline_fixed_remove` | `3` | `3` | `3` | `0` |
| `leg2_bb_revert` | `max_adx` | `24.0` | `active_tunable` | `8` | `0` | `0` | `0` |
| `leg2_bb_revert` | `max_aligned_funding_bps` | `1.0` | `active_tunable` | `5` | `1` | `1` | `0` |
| `leg2_bb_revert` | `max_atr_bps` | `200.0` | `active_tunable` | `6` | `0` | `0` | `0` |
| `leg2_bb_revert` | `max_dist_ema_bps` | `750.0` | `active_tunable` | `7` | `5` | `5` | `0` |
| `leg2_bb_revert` | `max_hold_bars` | `96` | `active_tunable` | `13` | `7` | `7` | `0` |
| `leg2_bb_revert` | `max_leverage` | `1.5` | `baseline_fixed_remove` | `8` | `8` | `8` | `0` |
| `leg2_bb_revert` | `min_adx` | `16.0` | `active_tunable` | `5` | `0` | `0` | `0` |
| `leg2_bb_revert` | `min_atr_bps` | `0.0` | `active_tunable` | `7` | `1` | `1` | `0` |
| `leg2_bb_revert` | `min_dir_roc_bps` | `-10000.0` | `active_tunable` | `9` | `0` | `0` | `0` |
| `leg2_bb_revert` | `min_rvol` | `1.0` | `active_tunable` | `7` | `0` | `0` | `0` |
| `leg2_bb_revert` | `name` | `SOL_1H_AR_R736318` | `contract_fixed` | `1` | `1` | `1` | `0` |
| `leg2_bb_revert` | `pullback_atr` | `0.25` | `baseline_fixed_remove` | `7` | `7` | `7` | `0` |
| `leg2_bb_revert` | `require_body_dir` | `False` | `neutral_fixed_remove` | `1` | `1` | `1` | `0` |
| `leg2_bb_revert` | `require_macd_turn` | `False` | `active_tunable` | `1` | `0` | `0` | `0` |
| `leg2_bb_revert` | `risk_fraction` | `0.03` | `baseline_fixed_remove` | `9` | `9` | `9` | `0` |
| `leg2_bb_revert` | `roc_threshold_bps` | `75.0` | `baseline_fixed_remove` | `7` | `7` | `7` | `0` |
| `leg2_bb_revert` | `roc_window` | `24` | `neutral_fixed_remove` | `6` | `6` | `6` | `0` |
| `leg2_bb_revert` | `side_mode` | `both` | `contract_fixed` | `2` | `0` | `0` | `0` |
| `leg2_bb_revert` | `sizing_kind` | `fixed` | `contract_fixed` | `1` | `0` | `0` | `0` |
| `leg2_bb_revert` | `sl_atr` | `2.5` | `active_tunable` | `10` | `0` | `0` | `0` |
| `leg2_bb_revert` | `style` | `bb_revert` | `contract_fixed` | `1` | `0` | `0` | `0` |
| `leg2_bb_revert` | `threshold_high` | `65.0` | `baseline_fixed_remove` | `13` | `13` | `13` | `0` |
| `leg2_bb_revert` | `threshold_low` | `35.0` | `baseline_fixed_remove` | `12` | `12` | `12` | `0` |
| `leg2_bb_revert` | `tp_atr` | `1.25` | `baseline_fixed_remove` | `12` | `12` | `12` | `0` |
| `leg2_bb_revert` | `trail_activation_atr` | `1.0` | `active_tunable` | `7` | `0` | `0` | `0` |
| `leg2_bb_revert` | `trail_atr` | `0.75` | `active_tunable` | `9` | `0` | `0` | `4` |

## 选择边界

- 删参只依据 V1 代码语义与路径等价性；不使用 reused holdout 决定保留字段。
- 后续微调只读取 train、validation 与 prefit；reused holdout 已解锁，只作冻结候选复用审计。
- V1 身份不因 clean surface 或微调而改变；除非用户另行登记，不创建新版本号。

## 机器证据

- `artifacts/sol_1h_ar_v1_full_ablation_2026-07-03.json`
- `artifacts/sol_1h_ar_v1_full_ablation_rows_2026-07-03.csv`
- `artifacts/sol_1h_ar_v1_full_ablation_fields_2026-07-03.csv`

复现：

```bash
uv run python research/sol/1h-adaptive-regime/scripts/research_sol_1h_ar_v1_full_ablation.py
```
