# BTC-1H-Adaptive-Regime-V3 全参数消融 - 2026-07-06

## 结论

已覆盖 V3 两条腿全部 `78` 个 StrategyConfig 字段槽，Keltner `39` 个、CCI `39` 个，coverage missing 为 `0`。

分类结果：`{'active_tunable': 27, 'baseline_fixed_remove': 35, 'contract_fixed': 12, 'neutral_fixed_remove': 4}`。本轮沿用 V1/V2 全消融的字段语义分类；这是 V3 冻结参数的 one-at-a-time 敏感性审计，不做组合搜索。

相对 V3 基线，one-at-a-time 变体中同时满足 prefit 年化更高、回撤更小、train/validation/prefit 胜率 >=80%、train/validation 同正且 validation DD<20% 的行数为 `0`。这些观察不构成 V3.1 或 promotion。

## V3 基线

| Window | Annual | Return | DD | Win | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `train` | `7.3797x` | `727.16%` | `-12.87%` | `91.18%` | `34` | `14.734` |
| `validation` | `4.3990x` | `132.38%` | `-10.80%` | `82.76%` | `29` | `4.353` |
| `prefit` | `6.1574x` | `1822.15%` | `-12.87%` | `87.30%` | `63` | `8.284` |
| `reused_holdout` | `1.8998x` | `17.34%` | `-17.47%` | `81.82%` | `11` | `2.279` |
| `current_full` | `5.2669x` | `2155.40%` | `-17.47%` | `86.49%` | `74` | `6.844` |

## 全字段覆盖与消融摘要

| Component | Field | Baseline | Classification | Variants | Path equal | Strict improve | Active gate | Best prefit | Worst prefit |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `keltner_break` | `band_k` | `2.0` | `active_tunable` | `4` | `0` | `0` | `0` | `5.4524x` | `3.3635x` |
| `keltner_break` | `cooldown_bars` | `0` | `active_tunable` | `4` | `0` | `0` | `4` | `5.3503x` | `5.1069x` |
| `keltner_break` | `ema_fast` | `55` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `6.1574x` | `6.1574x` |
| `keltner_break` | `ema_htf` | `55` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `6.1574x` | `6.1574x` |
| `keltner_break` | `ema_slow` | `144` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `6.1574x` | `6.1574x` |
| `keltner_break` | `entry_delay_bars` | `1` | `contract_fixed` | `2` | `0` | `0` | `0` | `4.7881x` | `3.9378x` |
| `keltner_break` | `exit_kind` | `fixed` | `contract_fixed` | `1` | `0` | `0` | `0` | `4.4348x` | `4.4348x` |
| `keltner_break` | `fixed_leverage` | `2.4` | `active_tunable` | `4` | `1` | `0` | `4` | `6.1574x` | `4.7141x` |
| `keltner_break` | `htf_mode` | `h4` | `active_tunable` | `3` | `0` | `0` | `0` | `6.2282x` | `4.7701x` |
| `keltner_break` | `indicator_window` | `20` | `active_tunable` | `3` | `0` | `0` | `0` | `3.2712x` | `2.5862x` |
| `keltner_break` | `macd_fast` | `8` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `6.1574x` | `6.1574x` |
| `keltner_break` | `macd_signal` | `5` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `6.1574x` | `6.1574x` |
| `keltner_break` | `macd_slow` | `21` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `6.1574x` | `6.1574x` |
| `keltner_break` | `max_adx` | `100.0` | `neutral_fixed_remove` | `2` | `1` | `0` | `1` | `6.1574x` | `4.5114x` |
| `keltner_break` | `max_aligned_funding_bps` | `4.0` | `active_tunable` | `3` | `3` | `0` | `3` | `6.1574x` | `6.1574x` |
| `keltner_break` | `max_atr_bps` | `200.0` | `active_tunable` | `4` | `3` | `0` | `4` | `6.1574x` | `5.4372x` |
| `keltner_break` | `max_dist_ema_bps` | `10000.0` | `neutral_fixed_remove` | `4` | `3` | `0` | `4` | `6.1574x` | `5.0591x` |
| `keltner_break` | `max_hold_bars` | `240` | `active_tunable` | `4` | `2` | `0` | `3` | `6.1574x` | `4.9367x` |
| `keltner_break` | `max_leverage` | `2.0` | `baseline_fixed_remove` | `3` | `3` | `0` | `3` | `6.1574x` | `6.1574x` |
| `keltner_break` | `min_adx` | `40.0` | `active_tunable` | `4` | `0` | `0` | `0` | `4.7953x` | `3.1842x` |
| `keltner_break` | `min_atr_bps` | `0.0` | `neutral_fixed_remove` | `2` | `0` | `0` | `0` | `6.1236x` | `4.5626x` |
| `keltner_break` | `min_dir_roc_bps` | `-200.0` | `active_tunable` | `4` | `3` | `0` | `4` | `6.1574x` | `6.1393x` |
| `keltner_break` | `min_rvol` | `1.25` | `active_tunable` | `4` | `0` | `0` | `3` | `5.7982x` | `4.8519x` |
| `keltner_break` | `name` | `BTC_1H_AR_V3_KELTNER` | `contract_fixed` | `1` | `1` | `0` | `1` | `6.1574x` | `6.1574x` |
| `keltner_break` | `pullback_atr` | `0.75` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `6.1574x` | `6.1574x` |
| `keltner_break` | `require_body_dir` | `False` | `baseline_fixed_remove` | `1` | `1` | `0` | `1` | `6.1574x` | `6.1574x` |
| `keltner_break` | `require_macd_turn` | `False` | `baseline_fixed_remove` | `1` | `0` | `0` | `1` | `5.9259x` | `5.9259x` |
| `keltner_break` | `risk_fraction` | `0.015` | `baseline_fixed_remove` | `3` | `3` | `0` | `3` | `6.1574x` | `6.1574x` |
| `keltner_break` | `roc_threshold_bps` | `300.0` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `6.1574x` | `6.1574x` |
| `keltner_break` | `roc_window` | `24` | `active_tunable` | `3` | `3` | `0` | `3` | `6.1574x` | `6.1574x` |
| `keltner_break` | `side_mode` | `both` | `contract_fixed` | `2` | `0` | `0` | `1` | `5.7523x` | `3.9032x` |
| `keltner_break` | `sizing_kind` | `fixed` | `contract_fixed` | `1` | `0` | `0` | `1` | `3.8463x` | `3.8463x` |
| `keltner_break` | `sl_atr` | `5.0` | `active_tunable` | `4` | `0` | `0` | `3` | `6.1373x` | `4.6546x` |
| `keltner_break` | `style` | `keltner_break` | `contract_fixed` | `1` | `0` | `0` | `0` | `3.6464x` | `3.6464x` |
| `keltner_break` | `threshold_high` | `85.0` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `6.1574x` | `6.1574x` |
| `keltner_break` | `threshold_low` | `20.0` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `6.1574x` | `6.1574x` |
| `keltner_break` | `tp_atr` | `1.5` | `active_tunable` | `4` | `0` | `0` | `2` | `5.5730x` | `4.5768x` |
| `keltner_break` | `trail_activation_atr` | `3.0` | `baseline_fixed_remove` | `3` | `3` | `0` | `3` | `6.1574x` | `6.1574x` |
| `keltner_break` | `trail_atr` | `1.5` | `baseline_fixed_remove` | `3` | `3` | `0` | `3` | `6.1574x` | `6.1574x` |
| `cci_reversal` | `band_k` | `1.5` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `6.1574x` | `6.1574x` |
| `cci_reversal` | `cooldown_bars` | `0` | `active_tunable` | `4` | `1` | `0` | `4` | `6.1574x` | `5.2656x` |
| `cci_reversal` | `ema_fast` | `89` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `6.1574x` | `6.1574x` |
| `cci_reversal` | `ema_htf` | `377` | `active_tunable` | `3` | `0` | `0` | `0` | `6.3088x` | `5.7672x` |
| `cci_reversal` | `ema_slow` | `233` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `6.1574x` | `6.1574x` |
| `cci_reversal` | `entry_delay_bars` | `1` | `contract_fixed` | `2` | `0` | `0` | `1` | `5.5703x` | `3.4437x` |
| `cci_reversal` | `exit_kind` | `fixed` | `contract_fixed` | `1` | `0` | `0` | `1` | `2.3966x` | `2.3966x` |
| `cci_reversal` | `fixed_leverage` | `3.5` | `active_tunable` | `4` | `1` | `0` | `4` | `6.1574x` | `3.6724x` |
| `cci_reversal` | `htf_mode` | `none` | `baseline_fixed_remove` | `3` | `0` | `0` | `3` | `3.4957x` | `2.8389x` |
| `cci_reversal` | `indicator_window` | `20` | `active_tunable` | `3` | `0` | `0` | `0` | `3.5806x` | `2.2084x` |
| `cci_reversal` | `macd_fast` | `21` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `6.1574x` | `6.1574x` |
| `cci_reversal` | `macd_signal` | `9` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `6.1574x` | `6.1574x` |
| `cci_reversal` | `macd_slow` | `55` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `6.1574x` | `6.1574x` |
| `cci_reversal` | `max_adx` | `40.0` | `active_tunable` | `4` | `1` | `0` | `2` | `6.1574x` | `4.7352x` |
| `cci_reversal` | `max_aligned_funding_bps` | `10000.0` | `baseline_fixed_remove` | `4` | `2` | `0` | `4` | `6.1574x` | `5.6889x` |
| `cci_reversal` | `max_atr_bps` | `600.0` | `active_tunable` | `3` | `3` | `0` | `3` | `6.1574x` | `6.1574x` |
| `cci_reversal` | `max_dist_ema_bps` | `750.0` | `active_tunable` | `4` | `0` | `0` | `0` | `6.5870x` | `4.4723x` |
| `cci_reversal` | `max_hold_bars` | `72` | `active_tunable` | `3` | `0` | `0` | `3` | `6.2430x` | `5.7204x` |
| `cci_reversal` | `max_leverage` | `2.5` | `baseline_fixed_remove` | `3` | `3` | `0` | `3` | `6.1574x` | `6.1574x` |
| `cci_reversal` | `min_adx` | `0.0` | `neutral_fixed_remove` | `3` | `2` | `0` | `3` | `6.1574x` | `3.5976x` |
| `cci_reversal` | `min_atr_bps` | `75.0` | `active_tunable` | `3` | `0` | `0` | `2` | `5.2954x` | `1.7145x` |
| `cci_reversal` | `min_dir_roc_bps` | `-10000.0` | `baseline_fixed_remove` | `3` | `0` | `0` | `3` | `2.5814x` | `2.1485x` |
| `cci_reversal` | `min_rvol` | `1.25` | `active_tunable` | `4` | `0` | `0` | `2` | `5.4143x` | `2.5288x` |
| `cci_reversal` | `name` | `BTC_1H_AR_V3_CCI` | `contract_fixed` | `1` | `1` | `0` | `1` | `6.1574x` | `6.1574x` |
| `cci_reversal` | `pullback_atr` | `-0.25` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `6.1574x` | `6.1574x` |
| `cci_reversal` | `require_body_dir` | `False` | `baseline_fixed_remove` | `1` | `0` | `0` | `1` | `5.0362x` | `5.0362x` |
| `cci_reversal` | `require_macd_turn` | `False` | `baseline_fixed_remove` | `1` | `0` | `0` | `1` | `4.3894x` | `4.3894x` |
| `cci_reversal` | `risk_fraction` | `0.01` | `baseline_fixed_remove` | `3` | `3` | `0` | `3` | `6.1574x` | `6.1574x` |
| `cci_reversal` | `roc_threshold_bps` | `300.0` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `6.1574x` | `6.1574x` |
| `cci_reversal` | `roc_window` | `48` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `6.1574x` | `6.1574x` |
| `cci_reversal` | `side_mode` | `long` | `contract_fixed` | `2` | `0` | `0` | `0` | `1.9132x` | `0.6272x` |
| `cci_reversal` | `sizing_kind` | `fixed` | `contract_fixed` | `1` | `0` | `0` | `1` | `2.1670x` | `2.1670x` |
| `cci_reversal` | `sl_atr` | `1.5` | `active_tunable` | `4` | `0` | `0` | `3` | `6.7643x` | `4.1329x` |
| `cci_reversal` | `style` | `cci_reversal` | `contract_fixed` | `1` | `0` | `0` | `1` | `1.7145x` | `1.7145x` |
| `cci_reversal` | `threshold_high` | `125.0` | `active_tunable` | `4` | `0` | `0` | `1` | `3.6132x` | `1.6679x` |
| `cci_reversal` | `threshold_low` | `40.0` | `baseline_fixed_remove` | `2` | `2` | `0` | `2` | `6.1574x` | `6.1574x` |
| `cci_reversal` | `tp_atr` | `5.5` | `active_tunable` | `4` | `0` | `0` | `4` | `6.0412x` | `3.5779x` |
| `cci_reversal` | `trail_activation_atr` | `0.75` | `baseline_fixed_remove` | `3` | `3` | `0` | `3` | `6.1574x` | `6.1574x` |
| `cci_reversal` | `trail_atr` | `1.25` | `baseline_fixed_remove` | `3` | `3` | `0` | `3` | `6.1574x` | `6.1574x` |

## Prefit 严格改善单字段 Top 20

| Label | Prefit annual | Prefit DD | Prefit win | Validation annual | Validation DD | Reused holdout annual | Reused holdout DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| - | - | - | - | - | - | - | - |

## 选择边界

- 本轮是 V3 冻结参数的 one-at-a-time 全字段敏感性消融，不做组合搜索。
- reused holdout 已在 V1/V2/V3 研究中解锁，只能作为复用审计列展示，不得用于新版本选参。
- V3 仍为 diagnostic observation；没有新增 forward trades、production runner、重启恢复、交易所对账、missing-bar fail-closed、kill switch 和真实 stop-market 滑点证据。

## 机器证据

- `artifacts/btc_1h_ar_v3_full_ablation_2026-07-06.json`
- `artifacts/btc_1h_ar_v3_full_ablation_rows_2026-07-06.csv`
- `artifacts/btc_1h_ar_v3_full_ablation_fields_2026-07-06.csv`

复现：

```bash
uv run research/btc/1h-adaptive-regime/scripts/research_btc_1h_ar_v3_full_ablation.py
```
