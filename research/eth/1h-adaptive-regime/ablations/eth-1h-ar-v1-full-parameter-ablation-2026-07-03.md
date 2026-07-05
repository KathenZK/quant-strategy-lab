# ETH-1H-Adaptive-Regime-V1 全参数消融 - 2026-07-03

## 结论

已覆盖 V1 两条腿全部 `78` 个 StrategyConfig 字段槽，BB breakout `39` 个、RSI `39` 个，coverage missing 为 `0`。

分类结果：`{'active_tunable': 29, 'baseline_fixed_remove': 30, 'contract_fixed': 12, 'neutral_fixed_remove': 3, 'path_fixed_remove': 4}`。其中 baseline fixed、neutral fixed 与 path fixed 字段从后续 clean tuning surface 移除；contract fixed 字段保留为实现常量，不进入搜索。

one-at-a-time 变体中，严格满足 prefit 年化更高、回撤更小、胜率 >=50%、train/validation 同正且 validation DD<20% 的行数为 `15`。

## V1 基线

| Window | Annual | Return | DD | Win | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `train` | `2.8190x` | `199.08%` | `-16.29%` | `72.46%` | `69` | `2.598` |
| `validation` | `2.7959x` | `79.54%` | `-11.43%` | `69.70%` | `33` | `2.922` |
| `prefit` | `2.8109x` | `436.97%` | `-16.29%` | `71.57%` | `102` | `2.697` |
| `reused_holdout` | `0.5196x` | `-15.05%` | `-20.87%` | `14.29%` | `7` | `0.154` |
| `current_full` | `2.2462x` | `356.15%` | `-20.87%` | `67.89%` | `109` | `2.316` |

## 全字段覆盖与删参分类

| Component | Field | Baseline | Classification | Variants | Component equal | Merged equal | Prefit strict improve |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `bb_break` | `band_k` | `2.0` | `active_tunable` | `4` | `0` | `0` | `0` |
| `bb_break` | `cooldown_bars` | `0` | `neutral_fixed_remove` | `3` | `0` | `0` | `0` |
| `bb_break` | `ema_fast` | `13` | `baseline_fixed_remove` | `2` | `2` | `2` | `0` |
| `bb_break` | `ema_htf` | `89` | `active_tunable` | `3` | `0` | `0` | `0` |
| `bb_break` | `ema_slow` | `34` | `baseline_fixed_remove` | `3` | `3` | `3` | `0` |
| `bb_break` | `entry_delay_bars` | `1` | `contract_fixed` | `2` | `0` | `0` | `0` |
| `bb_break` | `exit_kind` | `fixed` | `contract_fixed` | `1` | `0` | `0` | `0` |
| `bb_break` | `fixed_leverage` | `2.5` | `active_tunable` | `4` | `0` | `0` | `0` |
| `bb_break` | `htf_mode` | `none` | `baseline_fixed_remove` | `3` | `0` | `0` | `0` |
| `bb_break` | `indicator_window` | `72` | `active_tunable` | `2` | `0` | `0` | `0` |
| `bb_break` | `macd_fast` | `12` | `baseline_fixed_remove` | `2` | `2` | `2` | `0` |
| `bb_break` | `macd_signal` | `9` | `baseline_fixed_remove` | `2` | `2` | `2` | `0` |
| `bb_break` | `macd_slow` | `26` | `baseline_fixed_remove` | `2` | `2` | `2` | `0` |
| `bb_break` | `max_adx` | `100.0` | `neutral_fixed_remove` | `3` | `1` | `1` | `0` |
| `bb_break` | `max_aligned_funding_bps` | `2.0` | `active_tunable` | `4` | `0` | `0` | `0` |
| `bb_break` | `max_atr_bps` | `250.0` | `path_fixed_remove` | `4` | `4` | `4` | `0` |
| `bb_break` | `max_dist_ema_bps` | `750.0` | `active_tunable` | `4` | `0` | `0` | `0` |
| `bb_break` | `max_hold_bars` | `18` | `active_tunable` | `4` | `0` | `0` | `1` |
| `bb_break` | `max_leverage` | `3.0` | `baseline_fixed_remove` | `2` | `2` | `2` | `0` |
| `bb_break` | `min_adx` | `16.0` | `active_tunable` | `5` | `0` | `0` | `0` |
| `bb_break` | `min_atr_bps` | `75.0` | `active_tunable` | `4` | `0` | `0` | `0` |
| `bb_break` | `min_dir_roc_bps` | `-200.0` | `active_tunable` | `4` | `2` | `2` | `2` |
| `bb_break` | `min_rvol` | `2.0` | `active_tunable` | `4` | `0` | `0` | `0` |
| `bb_break` | `name` | `ETH_1H_AR_V1_BB_BREAK` | `contract_fixed` | `1` | `1` | `1` | `0` |
| `bb_break` | `pullback_atr` | `0.25` | `baseline_fixed_remove` | `2` | `2` | `2` | `0` |
| `bb_break` | `require_body_dir` | `False` | `baseline_fixed_remove` | `1` | `1` | `1` | `0` |
| `bb_break` | `require_macd_turn` | `False` | `baseline_fixed_remove` | `1` | `0` | `0` | `0` |
| `bb_break` | `risk_fraction` | `0.015` | `baseline_fixed_remove` | `3` | `3` | `3` | `0` |
| `bb_break` | `roc_threshold_bps` | `50.0` | `baseline_fixed_remove` | `2` | `2` | `2` | `0` |
| `bb_break` | `roc_window` | `12` | `active_tunable` | `3` | `3` | `3` | `0` |
| `bb_break` | `side_mode` | `long` | `contract_fixed` | `2` | `0` | `0` | `0` |
| `bb_break` | `sizing_kind` | `fixed` | `contract_fixed` | `1` | `0` | `0` | `0` |
| `bb_break` | `sl_atr` | `2.5` | `active_tunable` | `4` | `0` | `0` | `0` |
| `bb_break` | `style` | `bb_break` | `contract_fixed` | `1` | `0` | `0` | `0` |
| `bb_break` | `threshold_high` | `85.0` | `baseline_fixed_remove` | `2` | `2` | `2` | `0` |
| `bb_break` | `threshold_low` | `40.0` | `baseline_fixed_remove` | `2` | `2` | `2` | `0` |
| `bb_break` | `tp_atr` | `3.0` | `active_tunable` | `5` | `0` | `0` | `0` |
| `bb_break` | `trail_activation_atr` | `0.75` | `baseline_fixed_remove` | `3` | `3` | `3` | `0` |
| `bb_break` | `trail_atr` | `0.75` | `baseline_fixed_remove` | `3` | `3` | `3` | `0` |
| `rsi_reversal` | `band_k` | `1.5` | `baseline_fixed_remove` | `2` | `2` | `2` | `0` |
| `rsi_reversal` | `cooldown_bars` | `6` | `active_tunable` | `4` | `0` | `0` | `1` |
| `rsi_reversal` | `ema_fast` | `55` | `baseline_fixed_remove` | `3` | `3` | `3` | `0` |
| `rsi_reversal` | `ema_htf` | `89` | `active_tunable` | `3` | `1` | `1` | `1` |
| `rsi_reversal` | `ema_slow` | `233` | `baseline_fixed_remove` | `2` | `2` | `2` | `0` |
| `rsi_reversal` | `entry_delay_bars` | `1` | `contract_fixed` | `2` | `0` | `0` | `0` |
| `rsi_reversal` | `exit_kind` | `fixed` | `contract_fixed` | `1` | `0` | `0` | `0` |
| `rsi_reversal` | `fixed_leverage` | `1.0` | `active_tunable` | `3` | `0` | `0` | `2` |
| `rsi_reversal` | `htf_mode` | `none` | `baseline_fixed_remove` | `3` | `0` | `0` | `0` |
| `rsi_reversal` | `indicator_window` | `21` | `active_tunable` | `4` | `0` | `0` | `0` |
| `rsi_reversal` | `macd_fast` | `21` | `baseline_fixed_remove` | `2` | `2` | `2` | `0` |
| `rsi_reversal` | `macd_signal` | `9` | `baseline_fixed_remove` | `2` | `2` | `2` | `0` |
| `rsi_reversal` | `macd_slow` | `55` | `baseline_fixed_remove` | `2` | `2` | `2` | `0` |
| `rsi_reversal` | `max_adx` | `45.0` | `active_tunable` | `4` | `0` | `0` | `0` |
| `rsi_reversal` | `max_aligned_funding_bps` | `2.0` | `path_fixed_remove` | `4` | `4` | `4` | `0` |
| `rsi_reversal` | `max_atr_bps` | `600.0` | `path_fixed_remove` | `3` | `3` | `3` | `0` |
| `rsi_reversal` | `max_dist_ema_bps` | `750.0` | `active_tunable` | `5` | `4` | `4` | `1` |
| `rsi_reversal` | `max_hold_bars` | `12` | `active_tunable` | `5` | `0` | `0` | `2` |
| `rsi_reversal` | `max_leverage` | `4.0` | `baseline_fixed_remove` | `3` | `3` | `3` | `0` |
| `rsi_reversal` | `min_adx` | `0.0` | `active_tunable` | `3` | `2` | `2` | `1` |
| `rsi_reversal` | `min_atr_bps` | `100.0` | `active_tunable` | `4` | `0` | `0` | `0` |
| `rsi_reversal` | `min_dir_roc_bps` | `50.0` | `active_tunable` | `4` | `0` | `0` | `0` |
| `rsi_reversal` | `min_rvol` | `0.0` | `neutral_fixed_remove` | `4` | `0` | `0` | `0` |
| `rsi_reversal` | `name` | `ETH_1H_AR_V1_RSI` | `contract_fixed` | `1` | `1` | `1` | `0` |
| `rsi_reversal` | `pullback_atr` | `0.0` | `baseline_fixed_remove` | `1` | `1` | `1` | `0` |
| `rsi_reversal` | `require_body_dir` | `True` | `path_fixed_remove` | `1` | `1` | `1` | `0` |
| `rsi_reversal` | `require_macd_turn` | `False` | `baseline_fixed_remove` | `1` | `0` | `0` | `0` |
| `rsi_reversal` | `risk_fraction` | `0.03` | `baseline_fixed_remove` | `2` | `2` | `2` | `0` |
| `rsi_reversal` | `roc_threshold_bps` | `100.0` | `baseline_fixed_remove` | `1` | `1` | `1` | `0` |
| `rsi_reversal` | `roc_window` | `3` | `active_tunable` | `4` | `0` | `0` | `0` |
| `rsi_reversal` | `side_mode` | `both` | `contract_fixed` | `2` | `1` | `1` | `0` |
| `rsi_reversal` | `sizing_kind` | `fixed` | `contract_fixed` | `1` | `0` | `0` | `1` |
| `rsi_reversal` | `sl_atr` | `2.0` | `active_tunable` | `4` | `0` | `0` | `0` |
| `rsi_reversal` | `style` | `rsi_reversal` | `contract_fixed` | `1` | `0` | `0` | `0` |
| `rsi_reversal` | `threshold_high` | `60.0` | `active_tunable` | `4` | `0` | `0` | `0` |
| `rsi_reversal` | `threshold_low` | `15.0` | `active_tunable` | `4` | `2` | `2` | `0` |
| `rsi_reversal` | `tp_atr` | `3.0` | `active_tunable` | `5` | `0` | `0` | `3` |
| `rsi_reversal` | `trail_activation_atr` | `0.75` | `baseline_fixed_remove` | `3` | `3` | `3` | `0` |
| `rsi_reversal` | `trail_atr` | `2.0` | `baseline_fixed_remove` | `2` | `2` | `2` | `0` |

## Prefit 严格改善单字段 Top 20

| Label | Prefit annual | Prefit DD | Prefit win | Validation annual | Validation DD | Reused holdout annual | Reused holdout DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `rsi_reversal__fixed_leverage__2p0` | `3.6472x` | `-15.83%` | `71.57%` | `3.3011x` | `-10.82%` | `0.4584x` | `-23.30%` |
| `rsi_reversal__fixed_leverage__1p5` | `3.2089x` | `-15.80%` | `71.57%` | `3.0444x` | `-10.96%` | `0.4883x` | `-22.09%` |
| `rsi_reversal__max_hold_bars__18` | `3.0744x` | `-15.80%` | `69.61%` | `3.1933x` | `-9.96%` | `0.5196x` | `-20.87%` |
| `bb_break__min_dir_roc_bps__100p0` | `3.0312x` | `-16.29%` | `73.00%` | `3.1288x` | `-9.57%` | `0.5221x` | `-20.78%` |
| `rsi_reversal__max_hold_bars__24` | `3.0167x` | `-16.05%` | `67.65%` | `3.1279x` | `-9.96%` | `0.5196x` | `-20.87%` |
| `bb_break__max_hold_bars__24` | `2.9664x` | `-15.80%` | `70.30%` | `2.5776x` | `-12.11%` | `0.4300x` | `-27.17%` |
| `rsi_reversal__tp_atr__5p0` | `2.9537x` | `-16.29%` | `71.57%` | `2.7736x` | `-11.43%` | `0.5196x` | `-20.87%` |
| `rsi_reversal__max_dist_ema_bps__500p0` | `2.9212x` | `-16.29%` | `73.20%` | `2.7959x` | `-11.43%` | `0.5196x` | `-20.87%` |
| `bb_break__min_dir_roc_bps__0p0` | `2.9142x` | `-16.29%` | `72.28%` | `2.7959x` | `-11.43%` | `0.5221x` | `-20.78%` |
| `rsi_reversal__tp_atr__3p5` | `2.9128x` | `-16.29%` | `71.57%` | `2.8065x` | `-11.43%` | `0.5196x` | `-20.87%` |
| `rsi_reversal__min_adx__24p0` | `2.8777x` | `-16.29%` | `73.96%` | `2.9893x` | `-11.43%` | `0.5196x` | `-20.87%` |
| `rsi_reversal__cooldown_bars__0` | `2.8666x` | `-16.29%` | `72.12%` | `2.8451x` | `-11.43%` | `0.5196x` | `-20.87%` |
| `rsi_reversal__ema_htf__144` | `2.8640x` | `-16.29%` | `72.92%` | `2.7959x` | `-11.43%` | `0.5196x` | `-20.87%` |
| `rsi_reversal__sizing_kind__risk` | `2.8250x` | `-16.11%` | `71.57%` | `2.8546x` | `-11.13%` | `0.5198x` | `-20.86%` |
| `rsi_reversal__tp_atr__2p5` | `2.8187x` | `-15.80%` | `71.57%` | `2.6311x` | `-11.43%` | `0.5196x` | `-20.87%` |

## 选择边界

- 删参只依据代码语义、V1 状态与路径等价性；不使用 reused holdout 决定保留字段。
- 后续微调只读取 train、validation 与 prefit；reused holdout 已解锁，只作冻结候选的复用审计。
- V1 的版本身份不因 clean surface 或微调而改变；除非另行登记，不创建新版本号。

## 机器证据

- `artifacts/eth_1h_ar_v1_full_ablation_2026-07-03.json`
- `artifacts/eth_1h_ar_v1_full_ablation_rows_2026-07-03.csv`
- `artifacts/eth_1h_ar_v1_full_ablation_fields_2026-07-03.csv`

复现：

```bash
uv run python research/eth/1h-adaptive-regime/scripts/research_eth_1h_ar_v1_full_ablation.py
```
