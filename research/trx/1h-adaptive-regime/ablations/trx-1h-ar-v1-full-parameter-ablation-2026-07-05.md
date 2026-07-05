# TRX-1H-Adaptive-Regime-V1 全参数消融 - 2026-07-05

## 结论

已覆盖 V1 两个组件全部 `78` 个 StrategyConfig 字段槽，MACD `39` 个、Stochastic `39` 个，coverage missing 为 `0`。

分类结果：`{'active_tunable': 33, 'baseline_fixed_remove': 27, 'contract_fixed': 12, 'neutral_fixed_remove': 6}`。`baseline_fixed_remove` 与 `neutral_fixed_remove` 从 V1 clean-equivalent 参数面移除；`contract_fixed` 作为实现常量保留，但不再作为可调搜索参数。

one-at-a-time 变体中，严格满足 prefit 年化更高、回撤更小、胜率 >=50%、train/validation 同正且 validation DD<20% 的行数为 `4`。

V1 clean-equivalent 是 V1 的删参干净版，行为等价边界仍为 `NO-GO / not promoted / not live-ready`；它不是 candidate、paper-live、dry-run、handoff 或 live 版本。

## V1 基线

| Window | Annual | Return | DD | Win | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `train` | `9.1982x` | `944.03%` | `-16.34%` | `90.77%` | `65` | `6.793` |
| `validation` | `1.7925x` | `39.40%` | `-19.84%` | `80.65%` | `31` | `2.089` |
| `prefit` | `5.1894x` | `1355.40%` | `-19.84%` | `87.50%` | `96` | `4.758` |
| `holdout` | `0.8445x` | `-4.12%` | `-11.42%` | `75.00%` | `8` | `0.771` |
| `full` | `4.0772x` | `1295.38%` | `-19.84%` | `86.54%` | `104` | `4.090` |

## 全字段覆盖与删参分类

| Component | Field | Baseline | Classification | Variants | Component equal | Merged equal | Prefit strict improve |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `macd_flip` | `band_k` | `2.5` | `baseline_fixed_remove` | `3` | `3` | `3` | `0` |
| `macd_flip` | `cooldown_bars` | `3` | `active_tunable` | `4` | `2` | `3` | `0` |
| `macd_flip` | `ema_fast` | `144` | `baseline_fixed_remove` | `3` | `3` | `3` | `0` |
| `macd_flip` | `ema_htf` | `377` | `active_tunable` | `3` | `1` | `2` | `0` |
| `macd_flip` | `ema_slow` | `233` | `baseline_fixed_remove` | `1` | `1` | `1` | `0` |
| `macd_flip` | `entry_delay_bars` | `1` | `contract_fixed` | `2` | `0` | `0` | `0` |
| `macd_flip` | `exit_kind` | `fixed` | `contract_fixed` | `1` | `0` | `0` | `0` |
| `macd_flip` | `fixed_leverage` | `4.0` | `active_tunable` | `4` | `0` | `0` | `0` |
| `macd_flip` | `htf_mode` | `h12` | `active_tunable` | `3` | `0` | `0` | `0` |
| `macd_flip` | `indicator_window` | `96` | `baseline_fixed_remove` | `3` | `3` | `3` | `0` |
| `macd_flip` | `macd_fast` | `34` | `active_tunable` | `3` | `0` | `0` | `0` |
| `macd_flip` | `macd_signal` | `13` | `active_tunable` | `3` | `0` | `0` | `0` |
| `macd_flip` | `macd_slow` | `89` | `active_tunable` | `3` | `0` | `0` | `0` |
| `macd_flip` | `max_adx` | `28.0` | `active_tunable` | `4` | `0` | `0` | `0` |
| `macd_flip` | `max_aligned_funding_bps` | `10000.0` | `neutral_fixed_remove` | `4` | `2` | `2` | `0` |
| `macd_flip` | `max_atr_bps` | `200.0` | `active_tunable` | `4` | `4` | `4` | `0` |
| `macd_flip` | `max_dist_ema_bps` | `1000.0` | `active_tunable` | `4` | `0` | `0` | `0` |
| `macd_flip` | `max_hold_bars` | `168` | `active_tunable` | `4` | `3` | `3` | `0` |
| `macd_flip` | `max_leverage` | `5.0` | `baseline_fixed_remove` | `3` | `3` | `3` | `0` |
| `macd_flip` | `min_adx` | `12.0` | `active_tunable` | `4` | `2` | `2` | `0` |
| `macd_flip` | `min_atr_bps` | `0.0` | `neutral_fixed_remove` | `3` | `0` | `0` | `0` |
| `macd_flip` | `min_dir_roc_bps` | `-100.0` | `active_tunable` | `4` | `3` | `3` | `0` |
| `macd_flip` | `min_rvol` | `1.5` | `active_tunable` | `4` | `0` | `0` | `0` |
| `macd_flip` | `name` | `TRX_1H_AR_N131875` | `contract_fixed` | `1` | `1` | `1` | `0` |
| `macd_flip` | `pullback_atr` | `-0.25` | `baseline_fixed_remove` | `3` | `3` | `3` | `0` |
| `macd_flip` | `require_body_dir` | `False` | `baseline_fixed_remove` | `1` | `0` | `0` | `0` |
| `macd_flip` | `require_macd_turn` | `True` | `active_tunable` | `1` | `1` | `1` | `0` |
| `macd_flip` | `risk_fraction` | `0.025` | `baseline_fixed_remove` | `3` | `3` | `3` | `0` |
| `macd_flip` | `roc_threshold_bps` | `100.0` | `baseline_fixed_remove` | `3` | `3` | `3` | `0` |
| `macd_flip` | `roc_window` | `12` | `active_tunable` | `4` | `3` | `3` | `0` |
| `macd_flip` | `side_mode` | `both` | `contract_fixed` | `2` | `0` | `0` | `0` |
| `macd_flip` | `sizing_kind` | `fixed` | `contract_fixed` | `1` | `0` | `0` | `0` |
| `macd_flip` | `sl_atr` | `4.0` | `active_tunable` | `4` | `0` | `0` | `0` |
| `macd_flip` | `style` | `macd_flip` | `contract_fixed` | `1` | `0` | `0` | `0` |
| `macd_flip` | `threshold_high` | `70.0` | `baseline_fixed_remove` | `3` | `3` | `3` | `0` |
| `macd_flip` | `threshold_low` | `35.0` | `baseline_fixed_remove` | `3` | `3` | `3` | `0` |
| `macd_flip` | `tp_atr` | `2.0` | `active_tunable` | `4` | `0` | `0` | `0` |
| `macd_flip` | `trail_activation_atr` | `1.0` | `baseline_fixed_remove` | `3` | `3` | `3` | `0` |
| `macd_flip` | `trail_atr` | `2.5` | `baseline_fixed_remove` | `3` | `3` | `3` | `0` |
| `stoch_reversal` | `band_k` | `1.25` | `baseline_fixed_remove` | `3` | `3` | `3` | `0` |
| `stoch_reversal` | `cooldown_bars` | `24` | `active_tunable` | `4` | `0` | `0` | `1` |
| `stoch_reversal` | `ema_fast` | `8` | `baseline_fixed_remove` | `1` | `1` | `1` | `0` |
| `stoch_reversal` | `ema_htf` | `55` | `active_tunable` | `3` | `3` | `3` | `0` |
| `stoch_reversal` | `ema_slow` | `21` | `baseline_fixed_remove` | `3` | `3` | `3` | `0` |
| `stoch_reversal` | `entry_delay_bars` | `1` | `contract_fixed` | `2` | `0` | `0` | `1` |
| `stoch_reversal` | `exit_kind` | `trailing` | `contract_fixed` | `1` | `0` | `0` | `0` |
| `stoch_reversal` | `fixed_leverage` | `3.0` | `active_tunable` | `4` | `0` | `0` | `0` |
| `stoch_reversal` | `htf_mode` | `none` | `baseline_fixed_remove` | `3` | `0` | `0` | `0` |
| `stoch_reversal` | `indicator_window` | `21` | `active_tunable` | `3` | `0` | `0` | `0` |
| `stoch_reversal` | `macd_fast` | `12` | `baseline_fixed_remove` | `3` | `3` | `3` | `0` |
| `stoch_reversal` | `macd_signal` | `9` | `baseline_fixed_remove` | `3` | `3` | `3` | `0` |
| `stoch_reversal` | `macd_slow` | `26` | `baseline_fixed_remove` | `3` | `3` | `3` | `0` |
| `stoch_reversal` | `max_adx` | `30.0` | `active_tunable` | `4` | `0` | `0` | `0` |
| `stoch_reversal` | `max_aligned_funding_bps` | `4.0` | `baseline_fixed_remove` | `4` | `3` | `3` | `0` |
| `stoch_reversal` | `max_atr_bps` | `10000.0` | `neutral_fixed_remove` | `4` | `4` | `4` | `0` |
| `stoch_reversal` | `max_dist_ema_bps` | `1500.0` | `neutral_fixed_remove` | `4` | `3` | `3` | `0` |
| `stoch_reversal` | `max_hold_bars` | `168` | `active_tunable` | `4` | `0` | `0` | `0` |
| `stoch_reversal` | `max_leverage` | `2.5` | `baseline_fixed_remove` | `3` | `3` | `3` | `0` |
| `stoch_reversal` | `min_adx` | `0.0` | `neutral_fixed_remove` | `3` | `1` | `1` | `0` |
| `stoch_reversal` | `min_atr_bps` | `0.0` | `neutral_fixed_remove` | `3` | `0` | `0` | `0` |
| `stoch_reversal` | `min_dir_roc_bps` | `-200.0` | `active_tunable` | `4` | `0` | `0` | `0` |
| `stoch_reversal` | `min_rvol` | `1.0` | `active_tunable` | `4` | `0` | `0` | `0` |
| `stoch_reversal` | `name` | `TRX_1H_AR_N129128` | `contract_fixed` | `1` | `1` | `1` | `0` |
| `stoch_reversal` | `pullback_atr` | `0.0` | `baseline_fixed_remove` | `3` | `3` | `3` | `0` |
| `stoch_reversal` | `require_body_dir` | `True` | `active_tunable` | `1` | `0` | `0` | `0` |
| `stoch_reversal` | `require_macd_turn` | `False` | `baseline_fixed_remove` | `1` | `0` | `0` | `0` |
| `stoch_reversal` | `risk_fraction` | `0.015` | `baseline_fixed_remove` | `3` | `3` | `3` | `0` |
| `stoch_reversal` | `roc_threshold_bps` | `75.0` | `baseline_fixed_remove` | `3` | `3` | `3` | `0` |
| `stoch_reversal` | `roc_window` | `3` | `active_tunable` | `4` | `0` | `0` | `0` |
| `stoch_reversal` | `side_mode` | `long` | `contract_fixed` | `2` | `0` | `0` | `1` |
| `stoch_reversal` | `sizing_kind` | `fixed` | `contract_fixed` | `1` | `0` | `0` | `0` |
| `stoch_reversal` | `sl_atr` | `5.0` | `active_tunable` | `4` | `0` | `0` | `1` |
| `stoch_reversal` | `style` | `stoch_reversal` | `contract_fixed` | `1` | `0` | `0` | `0` |
| `stoch_reversal` | `threshold_high` | `85.0` | `active_tunable` | `3` | `3` | `3` | `0` |
| `stoch_reversal` | `threshold_low` | `25.0` | `active_tunable` | `4` | `0` | `0` | `0` |
| `stoch_reversal` | `tp_atr` | `0.75` | `baseline_fixed_remove` | `4` | `4` | `4` | `0` |
| `stoch_reversal` | `trail_activation_atr` | `3.0` | `active_tunable` | `4` | `0` | `0` | `0` |
| `stoch_reversal` | `trail_atr` | `1.25` | `active_tunable` | `4` | `0` | `0` | `0` |

## V1 Clean-equivalent 参数面

- `macd_flip` 保留字段：`['cooldown_bars', 'ema_htf', 'entry_delay_bars', 'exit_kind', 'fixed_leverage', 'htf_mode', 'macd_fast', 'macd_signal', 'macd_slow', 'max_adx', 'max_atr_bps', 'max_dist_ema_bps', 'max_hold_bars', 'min_adx', 'min_dir_roc_bps', 'min_rvol', 'name', 'require_macd_turn', 'roc_window', 'side_mode', 'sizing_kind', 'sl_atr', 'style', 'tp_atr']`。
- `macd_flip` 移除字段：`['band_k', 'ema_fast', 'ema_slow', 'indicator_window', 'max_aligned_funding_bps', 'max_leverage', 'min_atr_bps', 'pullback_atr', 'require_body_dir', 'risk_fraction', 'roc_threshold_bps', 'threshold_high', 'threshold_low', 'trail_activation_atr', 'trail_atr']`。
- `stoch_reversal` 保留字段：`['cooldown_bars', 'ema_htf', 'entry_delay_bars', 'exit_kind', 'fixed_leverage', 'indicator_window', 'max_adx', 'max_hold_bars', 'min_dir_roc_bps', 'min_rvol', 'name', 'require_body_dir', 'roc_window', 'side_mode', 'sizing_kind', 'sl_atr', 'style', 'threshold_high', 'threshold_low', 'trail_activation_atr', 'trail_atr']`。
- `stoch_reversal` 移除字段：`['band_k', 'ema_fast', 'ema_slow', 'htf_mode', 'macd_fast', 'macd_signal', 'macd_slow', 'max_aligned_funding_bps', 'max_atr_bps', 'max_dist_ema_bps', 'max_leverage', 'min_adx', 'min_atr_bps', 'pullback_atr', 'require_macd_turn', 'risk_fraction', 'roc_threshold_bps', 'tp_atr']`。

## Prefit 严格改善单字段 Top 20

| Label | Prefit annual | Prefit DD | Prefit win | Validation annual | Validation DD | Holdout annual | Holdout DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `stoch_reversal__entry_delay_bars__2` | `5.6566x` | `-15.12%` | `87.37%` | `2.4312x` | `-15.12%` | `0.8061x` | `-11.80%` |
| `stoch_reversal__sl_atr__4p0` | `5.2926x` | `-19.06%` | `86.46%` | `1.6848x` | `-19.06%` | `0.9296x` | `-10.13%` |
| `stoch_reversal__cooldown_bars__12` | `5.2868x` | `-19.84%` | `87.63%` | `1.8969x` | `-19.84%` | `0.8445x` | `-11.42%` |
| `stoch_reversal__side_mode__both` | `5.2543x` | `-19.29%` | `84.62%` | `2.8757x` | `-11.04%` | `0.6324x` | `-17.08%` |

## 选择边界

- V1 登记的是既有领先观察值，不改变其 OOS 亏损和 hard-gate 失败事实。
- V1 clean-equivalent 只移除语义休眠字段和 neutral fixed 字段；不使用 locked OOS 选择新参数。
- V1 clean-equivalent 后续若重新搜索，只能读取 train/validation/prefit；当前 locked OOS 已解锁，只能作复用审计。

## 机器证据

- `artifacts/trx_1h_ar_v1_full_ablation_2026-07-05.json`
- `artifacts/trx_1h_ar_v1_full_ablation_rows_2026-07-05.csv`
- `artifacts/trx_1h_ar_v1_full_ablation_fields_2026-07-05.csv`

复现：

```bash
uv run python research/trx/1h-adaptive-regime/scripts/research_trx_1h_ar_v1_full_ablation.py
```
