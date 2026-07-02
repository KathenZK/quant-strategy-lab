# BTC-1H-Adaptive-Regime-V1 全参数消融 - 2026-07-02

## 结论

已覆盖 V1 两条腿全部 `78` 个 StrategyConfig 字段槽，Keltner `39` 个、CCI `39` 个，coverage missing 为 `0`。

分类结果：`{'active_tunable': 27, 'contract_fixed': 12, 'neutral_fixed_remove': 4, 'semantic_dormant_remove': 35}`。其中 semantic dormant 与 neutral fixed 字段从后续 clean tuning surface 移除；contract fixed 字段保留为实现常量，不进入搜索。

one-at-a-time 变体中，严格满足 prefit 年化更高、回撤更小、胜率 >=50%、train/validation 同正且 validation DD<20% 的行数为 `5`。

## V1 基线

| Window | Annual | Return | DD | Win | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `train` | `2.5774x` | `172.05%` | `-15.13%` | `68.00%` | `50` | `2.372` |
| `validation` | `3.3339x` | `98.46%` | `-18.68%` | `68.75%` | `32` | `2.406` |
| `prefit` | `2.8204x` | `439.91%` | `-18.68%` | `68.29%` | `82` | `2.385` |
| `reused_holdout` | `0.1695x` | `-35.74%` | `-42.73%` | `38.46%` | `13` | `0.304` |
| `current_full` | `1.9412x` | `246.95%` | `-42.73%` | `64.21%` | `95` | `1.765` |

## 全字段覆盖与删参分类

| Component | Field | Baseline | Classification | Variants | Component equal | Merged equal | Prefit strict improve |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `keltner_break` | `band_k` | `2.5` | `active_tunable` | `4` | `0` | `0` | `1` |
| `keltner_break` | `cooldown_bars` | `6` | `active_tunable` | `4` | `0` | `0` | `0` |
| `keltner_break` | `ema_fast` | `55` | `semantic_dormant_remove` | `2` | `2` | `2` | `0` |
| `keltner_break` | `ema_htf` | `55` | `semantic_dormant_remove` | `2` | `2` | `2` | `0` |
| `keltner_break` | `ema_slow` | `144` | `semantic_dormant_remove` | `2` | `2` | `2` | `0` |
| `keltner_break` | `entry_delay_bars` | `1` | `contract_fixed` | `2` | `0` | `0` | `0` |
| `keltner_break` | `exit_kind` | `fixed` | `contract_fixed` | `1` | `0` | `0` | `0` |
| `keltner_break` | `fixed_leverage` | `3.0` | `active_tunable` | `4` | `0` | `0` | `0` |
| `keltner_break` | `htf_mode` | `d1` | `active_tunable` | `3` | `0` | `0` | `0` |
| `keltner_break` | `indicator_window` | `20` | `active_tunable` | `3` | `0` | `0` | `0` |
| `keltner_break` | `macd_fast` | `8` | `semantic_dormant_remove` | `2` | `2` | `2` | `0` |
| `keltner_break` | `macd_signal` | `5` | `semantic_dormant_remove` | `2` | `2` | `2` | `0` |
| `keltner_break` | `macd_slow` | `21` | `semantic_dormant_remove` | `2` | `2` | `2` | `0` |
| `keltner_break` | `max_adx` | `100.0` | `neutral_fixed_remove` | `2` | `1` | `1` | `0` |
| `keltner_break` | `max_aligned_funding_bps` | `2.0` | `active_tunable` | `4` | `1` | `1` | `2` |
| `keltner_break` | `max_atr_bps` | `200.0` | `active_tunable` | `4` | `3` | `3` | `0` |
| `keltner_break` | `max_dist_ema_bps` | `10000.0` | `neutral_fixed_remove` | `4` | `3` | `3` | `0` |
| `keltner_break` | `max_hold_bars` | `120` | `active_tunable` | `4` | `2` | `2` | `0` |
| `keltner_break` | `max_leverage` | `2.0` | `semantic_dormant_remove` | `3` | `3` | `3` | `0` |
| `keltner_break` | `min_adx` | `36.0` | `active_tunable` | `4` | `0` | `0` | `0` |
| `keltner_break` | `min_atr_bps` | `0.0` | `neutral_fixed_remove` | `2` | `0` | `0` | `0` |
| `keltner_break` | `min_dir_roc_bps` | `0.0` | `active_tunable` | `4` | `2` | `2` | `0` |
| `keltner_break` | `min_rvol` | `0.8` | `active_tunable` | `4` | `0` | `0` | `0` |
| `keltner_break` | `name` | `BTC_1H_AR_V1_KELTNER` | `contract_fixed` | `1` | `1` | `1` | `0` |
| `keltner_break` | `pullback_atr` | `0.75` | `semantic_dormant_remove` | `2` | `2` | `2` | `0` |
| `keltner_break` | `require_body_dir` | `False` | `semantic_dormant_remove` | `1` | `1` | `1` | `0` |
| `keltner_break` | `require_macd_turn` | `False` | `semantic_dormant_remove` | `1` | `0` | `0` | `0` |
| `keltner_break` | `risk_fraction` | `0.015` | `semantic_dormant_remove` | `3` | `3` | `3` | `0` |
| `keltner_break` | `roc_threshold_bps` | `300.0` | `semantic_dormant_remove` | `2` | `2` | `2` | `0` |
| `keltner_break` | `roc_window` | `24` | `active_tunable` | `2` | `0` | `0` | `0` |
| `keltner_break` | `side_mode` | `both` | `contract_fixed` | `2` | `0` | `0` | `0` |
| `keltner_break` | `sizing_kind` | `fixed` | `contract_fixed` | `1` | `0` | `0` | `0` |
| `keltner_break` | `sl_atr` | `4.0` | `active_tunable` | `4` | `0` | `0` | `0` |
| `keltner_break` | `style` | `keltner_break` | `contract_fixed` | `1` | `0` | `0` | `0` |
| `keltner_break` | `threshold_high` | `85.0` | `semantic_dormant_remove` | `2` | `2` | `2` | `0` |
| `keltner_break` | `threshold_low` | `20.0` | `semantic_dormant_remove` | `2` | `2` | `2` | `0` |
| `keltner_break` | `tp_atr` | `1.5` | `active_tunable` | `4` | `0` | `0` | `0` |
| `keltner_break` | `trail_activation_atr` | `3.0` | `semantic_dormant_remove` | `3` | `3` | `3` | `0` |
| `keltner_break` | `trail_atr` | `1.5` | `semantic_dormant_remove` | `3` | `3` | `3` | `0` |
| `cci_reversal` | `band_k` | `1.5` | `semantic_dormant_remove` | `2` | `2` | `2` | `0` |
| `cci_reversal` | `cooldown_bars` | `24` | `active_tunable` | `4` | `0` | `0` | `1` |
| `cci_reversal` | `ema_fast` | `89` | `semantic_dormant_remove` | `2` | `2` | `2` | `0` |
| `cci_reversal` | `ema_htf` | `144` | `active_tunable` | `2` | `2` | `2` | `0` |
| `cci_reversal` | `ema_slow` | `233` | `semantic_dormant_remove` | `2` | `2` | `2` | `0` |
| `cci_reversal` | `entry_delay_bars` | `1` | `contract_fixed` | `2` | `0` | `0` | `0` |
| `cci_reversal` | `exit_kind` | `fixed` | `contract_fixed` | `1` | `0` | `0` | `0` |
| `cci_reversal` | `fixed_leverage` | `4.0` | `active_tunable` | `4` | `0` | `0` | `0` |
| `cci_reversal` | `htf_mode` | `none` | `semantic_dormant_remove` | `3` | `0` | `0` | `0` |
| `cci_reversal` | `indicator_window` | `20` | `active_tunable` | `3` | `0` | `0` | `0` |
| `cci_reversal` | `macd_fast` | `21` | `semantic_dormant_remove` | `2` | `2` | `2` | `0` |
| `cci_reversal` | `macd_signal` | `9` | `semantic_dormant_remove` | `2` | `2` | `2` | `0` |
| `cci_reversal` | `macd_slow` | `55` | `semantic_dormant_remove` | `2` | `2` | `2` | `0` |
| `cci_reversal` | `max_adx` | `36.0` | `active_tunable` | `3` | `0` | `0` | `0` |
| `cci_reversal` | `max_aligned_funding_bps` | `10000.0` | `semantic_dormant_remove` | `4` | `2` | `2` | `0` |
| `cci_reversal` | `max_atr_bps` | `300.0` | `active_tunable` | `5` | `5` | `5` | `0` |
| `cci_reversal` | `max_dist_ema_bps` | `1000.0` | `active_tunable` | `5` | `5` | `5` | `0` |
| `cci_reversal` | `max_hold_bars` | `96` | `active_tunable` | `3` | `0` | `0` | `1` |
| `cci_reversal` | `max_leverage` | `2.5` | `semantic_dormant_remove` | `3` | `3` | `3` | `0` |
| `cci_reversal` | `min_adx` | `0.0` | `neutral_fixed_remove` | `3` | `1` | `1` | `0` |
| `cci_reversal` | `min_atr_bps` | `50.0` | `active_tunable` | `3` | `0` | `0` | `0` |
| `cci_reversal` | `min_dir_roc_bps` | `-10000.0` | `semantic_dormant_remove` | `3` | `0` | `0` | `0` |
| `cci_reversal` | `min_rvol` | `1.5` | `active_tunable` | `4` | `0` | `0` | `0` |
| `cci_reversal` | `name` | `BTC_1H_AR_V1_CCI` | `contract_fixed` | `1` | `1` | `1` | `0` |
| `cci_reversal` | `pullback_atr` | `-0.25` | `semantic_dormant_remove` | `2` | `2` | `2` | `0` |
| `cci_reversal` | `require_body_dir` | `False` | `semantic_dormant_remove` | `1` | `0` | `0` | `0` |
| `cci_reversal` | `require_macd_turn` | `False` | `semantic_dormant_remove` | `1` | `0` | `0` | `0` |
| `cci_reversal` | `risk_fraction` | `0.01` | `semantic_dormant_remove` | `3` | `3` | `3` | `0` |
| `cci_reversal` | `roc_threshold_bps` | `300.0` | `semantic_dormant_remove` | `2` | `2` | `2` | `0` |
| `cci_reversal` | `roc_window` | `48` | `semantic_dormant_remove` | `2` | `2` | `2` | `0` |
| `cci_reversal` | `side_mode` | `long` | `contract_fixed` | `2` | `0` | `0` | `0` |
| `cci_reversal` | `sizing_kind` | `fixed` | `contract_fixed` | `1` | `0` | `0` | `0` |
| `cci_reversal` | `sl_atr` | `1.25` | `active_tunable` | `4` | `0` | `0` | `0` |
| `cci_reversal` | `style` | `cci_reversal` | `contract_fixed` | `1` | `0` | `0` | `0` |
| `cci_reversal` | `threshold_high` | `125.0` | `active_tunable` | `3` | `0` | `0` | `0` |
| `cci_reversal` | `threshold_low` | `40.0` | `semantic_dormant_remove` | `2` | `2` | `2` | `0` |
| `cci_reversal` | `tp_atr` | `4.0` | `active_tunable` | `4` | `0` | `0` | `0` |
| `cci_reversal` | `trail_activation_atr` | `0.75` | `semantic_dormant_remove` | `3` | `3` | `3` | `0` |
| `cci_reversal` | `trail_atr` | `1.25` | `semantic_dormant_remove` | `3` | `3` | `3` | `0` |

## Prefit 严格改善单字段 Top 20

| Label | Prefit annual | Prefit DD | Prefit win | Validation annual | Validation DD | Reused holdout annual | Reused holdout DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `keltner_break__band_k__2p0` | `3.2323x` | `-18.23%` | `70.00%` | `4.3074x` | `-14.93%` | `0.1542x` | `-44.06%` |
| `keltner_break__max_aligned_funding_bps__8p0` | `2.9098x` | `-18.68%` | `68.67%` | `3.3339x` | `-18.68%` | `0.1695x` | `-42.73%` |
| `keltner_break__max_aligned_funding_bps__10000p0` | `2.9098x` | `-18.68%` | `68.67%` | `3.3339x` | `-18.68%` | `0.1695x` | `-42.73%` |
| `cci_reversal__cooldown_bars__12` | `2.8602x` | `-18.68%` | `66.28%` | `3.3339x` | `-18.68%` | `0.1695x` | `-42.73%` |
| `cci_reversal__max_hold_bars__72` | `2.8323x` | `-18.68%` | `68.29%` | `3.3746x` | `-18.68%` | `0.1695x` | `-42.73%` |

## 选择边界

- 删参只依据代码语义、V1 状态与路径等价性；不使用 reused holdout 决定保留字段。
- 后续微调只读取 train、validation 与 prefit；reused holdout 已解锁，只作冻结候选的复用审计。
- V1 的版本身份不因 clean surface 或微调而改变；除非另行登记，不创建新版本号。

## 机器证据

- `artifacts/btc_1h_ar_v1_full_ablation_2026-07-02.json`
- `artifacts/btc_1h_ar_v1_full_ablation_rows_2026-07-02.csv`
- `artifacts/btc_1h_ar_v1_full_ablation_fields_2026-07-02.csv`

复现：

```bash
uv run research/btc/1h-adaptive-regime/scripts/research_btc_1h_ar_v1_full_ablation.py
```
