# BTC-1H-Adaptive-Regime-V2 全参数消融 - 2026-07-06

## 结论

已覆盖 V2 两条腿全部 `78` 个 StrategyConfig 字段槽，Keltner `39` 个、CCI `39` 个，coverage missing 为 `0`。

分类结果：`{'active_tunable': 27, 'baseline_fixed_remove': 35, 'contract_fixed': 12, 'neutral_fixed_remove': 4}`。本轮仍沿用 V1 全消融的字段语义分类：active tunable 为 V2 clean surface 可调项；contract fixed 为执行合同常量；baseline/neutral fixed 为代码语义上不影响当前 leg 或固定删除的槽。

相对 V2 基线，one-at-a-time 变体中同时满足 prefit 年化更高、回撤更小、胜率 >=50%、train/validation 同正且 validation DD<20% 的行数为 `5`。这些只是单字段敏感性观察，不构成 V2.1 或 promotion。

## V2 基线

| Window | Annual | Return | DD | Win | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `train` | `3.6068x` | `288.08%` | `-13.99%` | `86.49%` | `37` | `7.180` |
| `validation` | `2.5108x` | `68.88%` | `-10.29%` | `82.76%` | `29` | `3.274` |
| `prefit` | `3.1773x` | `555.39%` | `-13.99%` | `84.85%` | `66` | `5.171` |
| `reused_holdout` | `1.5232x` | `11.05%` | `-13.48%` | `81.82%` | `11` | `2.074` |
| `current_full` | `2.8817x` | `627.83%` | `-13.99%` | `84.42%` | `77` | `4.612` |

## 全字段覆盖与消融摘要

| Component | Field | Baseline | Classification | Variants | Path equal | Strict improve | Active gate | Best prefit | Worst prefit |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `keltner_break` | `band_k` | `2.0` | `active_tunable` | `4` | `0` | `0` | `1` | `2.8282x` | `2.0799x` |
| `keltner_break` | `cooldown_bars` | `0` | `active_tunable` | `4` | `0` | `0` | `4` | `2.7176x` | `2.6239x` |
| `keltner_break` | `ema_fast` | `55` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `3.1773x` | `3.1773x` |
| `keltner_break` | `ema_htf` | `55` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `3.1773x` | `3.1773x` |
| `keltner_break` | `ema_slow` | `144` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `3.1773x` | `3.1773x` |
| `keltner_break` | `entry_delay_bars` | `1` | `contract_fixed` | `2` | `0` | `0` | `1` | `2.5109x` | `2.1765x` |
| `keltner_break` | `exit_kind` | `fixed` | `contract_fixed` | `1` | `0` | `0` | `1` | `2.3755x` | `2.3755x` |
| `keltner_break` | `fixed_leverage` | `1.8` | `active_tunable` | `4` | `0` | `0` | `4` | `3.6291x` | `2.6564x` |
| `keltner_break` | `htf_mode` | `h4` | `active_tunable` | `3` | `0` | `1` | `1` | `3.2074x` | `2.6338x` |
| `keltner_break` | `indicator_window` | `20` | `active_tunable` | `3` | `0` | `0` | `0` | `2.0404x` | `1.6990x` |
| `keltner_break` | `macd_fast` | `8` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `3.1773x` | `3.1773x` |
| `keltner_break` | `macd_signal` | `5` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `3.1773x` | `3.1773x` |
| `keltner_break` | `macd_slow` | `21` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `3.1773x` | `3.1773x` |
| `keltner_break` | `max_adx` | `100.0` | `neutral_fixed_remove` | `2` | `1` | `0` | `2` | `3.1773x` | `2.3895x` |
| `keltner_break` | `max_aligned_funding_bps` | `4.0` | `active_tunable` | `3` | `3` | `0` | `3` | `3.1773x` | `3.1773x` |
| `keltner_break` | `max_atr_bps` | `200.0` | `active_tunable` | `4` | `3` | `0` | `4` | `3.1773x` | `2.7505x` |
| `keltner_break` | `max_dist_ema_bps` | `10000.0` | `neutral_fixed_remove` | `4` | `3` | `0` | `4` | `3.1773x` | `2.6051x` |
| `keltner_break` | `max_hold_bars` | `240` | `active_tunable` | `4` | `2` | `0` | `4` | `3.1773x` | `2.5617x` |
| `keltner_break` | `max_leverage` | `2.0` | `baseline_fixed_remove` | `3` | `3` | `0` | `3` | `3.1773x` | `3.1773x` |
| `keltner_break` | `min_adx` | `40.0` | `active_tunable` | `4` | `0` | `0` | `2` | `2.6464x` | `1.9184x` |
| `keltner_break` | `min_atr_bps` | `0.0` | `neutral_fixed_remove` | `2` | `0` | `0` | `2` | `3.1635x` | `2.4109x` |
| `keltner_break` | `min_dir_roc_bps` | `-200.0` | `active_tunable` | `4` | `3` | `0` | `4` | `3.1773x` | `3.1703x` |
| `keltner_break` | `min_rvol` | `1.25` | `active_tunable` | `4` | `0` | `0` | `4` | `2.8912x` | `2.5673x` |
| `keltner_break` | `name` | `BTC_1H_AR_V2_KELTNER` | `contract_fixed` | `1` | `1` | `0` | `1` | `3.1773x` | `3.1773x` |
| `keltner_break` | `pullback_atr` | `0.75` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `3.1773x` | `3.1773x` |
| `keltner_break` | `require_body_dir` | `False` | `baseline_fixed_remove` | `1` | `1` | `0` | `1` | `3.1773x` | `3.1773x` |
| `keltner_break` | `require_macd_turn` | `False` | `baseline_fixed_remove` | `1` | `0` | `0` | `1` | `3.0871x` | `3.0871x` |
| `keltner_break` | `risk_fraction` | `0.015` | `baseline_fixed_remove` | `3` | `3` | `0` | `3` | `3.1773x` | `3.1773x` |
| `keltner_break` | `roc_threshold_bps` | `300.0` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `3.1773x` | `3.1773x` |
| `keltner_break` | `roc_window` | `24` | `active_tunable` | `3` | `3` | `0` | `3` | `3.1773x` | `3.1773x` |
| `keltner_break` | `side_mode` | `both` | `contract_fixed` | `2` | `0` | `1` | `2` | `3.1857x` | `2.1790x` |
| `keltner_break` | `sizing_kind` | `fixed` | `contract_fixed` | `1` | `0` | `0` | `1` | `2.1865x` | `2.1865x` |
| `keltner_break` | `sl_atr` | `5.0` | `active_tunable` | `4` | `0` | `0` | `4` | `3.1697x` | `2.4526x` |
| `keltner_break` | `style` | `keltner_break` | `contract_fixed` | `1` | `0` | `0` | `0` | `2.1847x` | `2.1847x` |
| `keltner_break` | `threshold_high` | `85.0` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `3.1773x` | `3.1773x` |
| `keltner_break` | `threshold_low` | `20.0` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `3.1773x` | `3.1773x` |
| `keltner_break` | `tp_atr` | `1.5` | `active_tunable` | `4` | `0` | `0` | `4` | `2.7756x` | `2.4060x` |
| `keltner_break` | `trail_activation_atr` | `3.0` | `baseline_fixed_remove` | `3` | `3` | `0` | `3` | `3.1773x` | `3.1773x` |
| `keltner_break` | `trail_atr` | `1.5` | `baseline_fixed_remove` | `3` | `3` | `0` | `3` | `3.1773x` | `3.1773x` |
| `cci_reversal` | `band_k` | `1.5` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `3.1773x` | `3.1773x` |
| `cci_reversal` | `cooldown_bars` | `48` | `active_tunable` | `4` | `0` | `1` | `4` | `3.2295x` | `3.0056x` |
| `cci_reversal` | `ema_fast` | `89` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `3.1773x` | `3.1773x` |
| `cci_reversal` | `ema_htf` | `377` | `active_tunable` | `3` | `0` | `0` | `3` | `2.9802x` | `2.7826x` |
| `cci_reversal` | `ema_slow` | `233` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `3.1773x` | `3.1773x` |
| `cci_reversal` | `entry_delay_bars` | `1` | `contract_fixed` | `2` | `0` | `0` | `1` | `3.1619x` | `2.3843x` |
| `cci_reversal` | `exit_kind` | `fixed` | `contract_fixed` | `1` | `0` | `0` | `1` | `1.9633x` | `1.9633x` |
| `cci_reversal` | `fixed_leverage` | `2.7` | `active_tunable` | `4` | `0` | `0` | `4` | `3.6536x` | `2.6454x` |
| `cci_reversal` | `htf_mode` | `none` | `baseline_fixed_remove` | `3` | `0` | `0` | `3` | `2.0765x` | `1.9262x` |
| `cci_reversal` | `indicator_window` | `20` | `active_tunable` | `3` | `0` | `0` | `2` | `2.1207x` | `1.5572x` |
| `cci_reversal` | `macd_fast` | `21` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `3.1773x` | `3.1773x` |
| `cci_reversal` | `macd_signal` | `9` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `3.1773x` | `3.1773x` |
| `cci_reversal` | `macd_slow` | `55` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `3.1773x` | `3.1773x` |
| `cci_reversal` | `max_adx` | `45.0` | `active_tunable` | `4` | `0` | `1` | `4` | `3.2118x` | `2.9734x` |
| `cci_reversal` | `max_aligned_funding_bps` | `10000.0` | `baseline_fixed_remove` | `4` | `2` | `0` | `4` | `3.1773x` | `3.1220x` |
| `cci_reversal` | `max_atr_bps` | `600.0` | `active_tunable` | `3` | `3` | `0` | `3` | `3.1773x` | `3.1773x` |
| `cci_reversal` | `max_dist_ema_bps` | `750.0` | `active_tunable` | `4` | `0` | `0` | `4` | `3.0803x` | `2.7826x` |
| `cci_reversal` | `max_hold_bars` | `72` | `active_tunable` | `3` | `2` | `0` | `3` | `3.1773x` | `3.1586x` |
| `cci_reversal` | `max_leverage` | `2.5` | `baseline_fixed_remove` | `3` | `3` | `0` | `3` | `3.1773x` | `3.1773x` |
| `cci_reversal` | `min_adx` | `0.0` | `neutral_fixed_remove` | `3` | `2` | `0` | `3` | `3.1773x` | `2.2101x` |
| `cci_reversal` | `min_atr_bps` | `75.0` | `active_tunable` | `3` | `0` | `0` | `3` | `2.9421x` | `1.4244x` |
| `cci_reversal` | `min_dir_roc_bps` | `-10000.0` | `baseline_fixed_remove` | `3` | `0` | `0` | `3` | `2.0031x` | `1.7052x` |
| `cci_reversal` | `min_rvol` | `1.25` | `active_tunable` | `4` | `0` | `0` | `3` | `2.8866x` | `1.3052x` |
| `cci_reversal` | `name` | `BTC_1H_AR_V2_CCI` | `contract_fixed` | `1` | `1` | `0` | `1` | `3.1773x` | `3.1773x` |
| `cci_reversal` | `pullback_atr` | `-0.25` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `3.1773x` | `3.1773x` |
| `cci_reversal` | `require_body_dir` | `False` | `baseline_fixed_remove` | `1` | `0` | `0` | `1` | `2.8304x` | `2.8304x` |
| `cci_reversal` | `require_macd_turn` | `False` | `baseline_fixed_remove` | `1` | `0` | `0` | `1` | `2.6028x` | `2.6028x` |
| `cci_reversal` | `risk_fraction` | `0.01` | `baseline_fixed_remove` | `3` | `3` | `0` | `3` | `3.1773x` | `3.1773x` |
| `cci_reversal` | `roc_threshold_bps` | `300.0` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `3.1773x` | `3.1773x` |
| `cci_reversal` | `roc_window` | `48` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `3.1773x` | `3.1773x` |
| `cci_reversal` | `side_mode` | `long` | `contract_fixed` | `2` | `0` | `0` | `1` | `1.8263x` | `0.8602x` |
| `cci_reversal` | `sizing_kind` | `fixed` | `contract_fixed` | `1` | `0` | `0` | `1` | `1.8063x` | `1.8063x` |
| `cci_reversal` | `sl_atr` | `1.5` | `active_tunable` | `4` | `0` | `0` | `3` | `3.0423x` | `2.5613x` |
| `cci_reversal` | `style` | `cci_reversal` | `contract_fixed` | `1` | `0` | `0` | `1` | `1.5011x` | `1.5011x` |
| `cci_reversal` | `threshold_high` | `125.0` | `active_tunable` | `4` | `0` | `0` | `3` | `2.4976x` | `1.4213x` |
| `cci_reversal` | `threshold_low` | `40.0` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `3.1773x` | `3.1773x` |
| `cci_reversal` | `tp_atr` | `4.5` | `active_tunable` | `4` | `0` | `1` | `4` | `3.5469x` | `2.5181x` |
| `cci_reversal` | `trail_activation_atr` | `0.75` | `baseline_fixed_remove` | `3` | `3` | `0` | `3` | `3.1773x` | `3.1773x` |
| `cci_reversal` | `trail_atr` | `1.25` | `baseline_fixed_remove` | `3` | `3` | `0` | `3` | `3.1773x` | `3.1773x` |

## Prefit 严格改善单字段 Top 20

| Label | Prefit annual | Prefit DD | Prefit win | Validation annual | Validation DD | Reused holdout annual | Reused holdout DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cci_reversal__tp_atr__5p0` | `3.5469x` | `-13.99%` | `84.85%` | `2.7181x` | `-10.29%` | `1.5842x` | `-13.48%` |
| `cci_reversal__cooldown_bars__0` | `3.2295x` | `-13.73%` | `82.61%` | `2.1422x` | `-13.73%` | `1.5232x` | `-13.48%` |
| `cci_reversal__max_adx__40p0` | `3.2118x` | `-13.99%` | `88.52%` | `2.9345x` | `-6.78%` | `1.5232x` | `-13.48%` |
| `keltner_break__htf_mode__none` | `3.2074x` | `-13.42%` | `84.00%` | `2.1839x` | `-13.42%` | `1.5232x` | `-13.48%` |
| `keltner_break__side_mode__short` | `3.1857x` | `-13.99%` | `83.64%` | `2.6808x` | `-11.03%` | `1.6623x` | `-13.48%` |

## 选择边界

- 本轮是 V2 冻结参数的 one-at-a-time 全字段敏感性消融，不做组合搜索。
- reused holdout 已在 V1/V2 研究中解锁，只能作为复用审计列展示，不得用于新版本选参。
- V2 仍为 paper-audit observation；没有新增 forward trades、production runner、重启恢复、交易所对账、missing-bar fail-closed、kill switch 和真实 stop-market 滑点证据。

## 机器证据

- `artifacts/btc_1h_ar_v2_full_ablation_2026-07-06.json`
- `artifacts/btc_1h_ar_v2_full_ablation_rows_2026-07-06.csv`
- `artifacts/btc_1h_ar_v2_full_ablation_fields_2026-07-06.csv`

复现：

```bash
uv run research/btc/1h-adaptive-regime/scripts/research_btc_1h_ar_v2_full_ablation.py
```
