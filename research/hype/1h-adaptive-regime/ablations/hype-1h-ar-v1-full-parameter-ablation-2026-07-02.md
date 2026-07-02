# HYPE-1H-Adaptive-Regime-V1 全参数消融 - 2026-07-02

## 结论

本轮以冻结的 `DI-cross + Stoch-reversal` 边界组合登记为 `HYPE-1H-Adaptive-Regime-V1`，并覆盖 `StrategyConfig` 除 metadata `name` 外全部 `38` 个字段、两条腿共 `76` 个 field slots。

共输出 `123` 行（含 baseline）；coverage missing fields 为 `0`。识别 structural dormant `24` 个、disabled/fixed switch `16` 个、active `36` 个。V2 将从配置接口移除前两类共 `40` 个 field slots，但会在专用状态机中硬编码必要的 K+1、退出类型和双向机制。

## V1 当前数据复现

| Window | Annual | Return | DD | Win | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Prefit | `11.67x` | `526.17%` | `-16.93%` | `79.25%` | `53` | `7.267` |
| Reused holdout | `5.13x` | `43.05%` | `-19.64%` | `75.00%` | `16` | `4.342` |
| Current full | `9.68x` | `795.75%` | `-19.64%` | `78.26%` | `69` | `6.486` |

## 将从 V2 配置接口移除的字段

| Component | Field | Class | Baseline | Component path equal | Note |
| --- | --- | --- | --- | ---: | --- |
| `di_cross` | `band_k` | `structural_dormant` | `1.0` | `True` | code branch does not reference field |
| `di_cross` | `cooldown_bars` | `disabled_or_fixed` | `0` | `False` | V1 switch is fixed or bound intentionally disables filter |
| `di_cross` | `ema_fast` | `structural_dormant` | `13` | `True` | code branch does not reference field |
| `di_cross` | `ema_slow` | `structural_dormant` | `233` | `True` | code branch does not reference field |
| `di_cross` | `entry_delay_bars` | `disabled_or_fixed` | `1` | `False` | V1 switch is fixed or bound intentionally disables filter |
| `di_cross` | `exit_kind` | `disabled_or_fixed` | `fixed` | `False` | V1 switch is fixed or bound intentionally disables filter |
| `di_cross` | `indicator_window` | `structural_dormant` | `32` | `True` | code branch does not reference field |
| `di_cross` | `macd_fast` | `structural_dormant` | `21` | `True` | code branch does not reference field |
| `di_cross` | `macd_signal` | `structural_dormant` | `9` | `True` | code branch does not reference field |
| `di_cross` | `macd_slow` | `structural_dormant` | `55` | `True` | code branch does not reference field |
| `di_cross` | `max_leverage` | `structural_dormant` | `3.0` | `True` | code branch does not reference field |
| `di_cross` | `min_atr_bps` | `disabled_or_fixed` | `0.0` | `False` | V1 switch is fixed or bound intentionally disables filter |
| `di_cross` | `pullback_atr` | `structural_dormant` | `0.25` | `True` | code branch does not reference field |
| `di_cross` | `require_macd_turn` | `structural_dormant` | `False` | `True` | code branch does not reference field |
| `di_cross` | `risk_fraction` | `structural_dormant` | `0.015` | `True` | code branch does not reference field |
| `di_cross` | `roc_threshold_bps` | `structural_dormant` | `200.0` | `True` | code branch does not reference field |
| `di_cross` | `side_mode` | `disabled_or_fixed` | `both` | `False` | V1 switch is fixed or bound intentionally disables filter |
| `di_cross` | `sizing_kind` | `disabled_or_fixed` | `fixed` | `False` | V1 switch is fixed or bound intentionally disables filter |
| `di_cross` | `threshold_high` | `structural_dormant` | `65.0` | `True` | code branch does not reference field |
| `di_cross` | `threshold_low` | `structural_dormant` | `40.0` | `True` | code branch does not reference field |
| `di_cross` | `trail_activation_atr` | `structural_dormant` | `3.0` | `True` | code branch does not reference field |
| `di_cross` | `trail_atr` | `structural_dormant` | `1.0` | `True` | code branch does not reference field |
| `stoch_reversal` | `band_k` | `structural_dormant` | `1.0` | `True` | code branch does not reference field |
| `stoch_reversal` | `ema_fast` | `structural_dormant` | `34` | `True` | code branch does not reference field |
| `stoch_reversal` | `ema_slow` | `structural_dormant` | `89` | `True` | code branch does not reference field |
| `stoch_reversal` | `entry_delay_bars` | `disabled_or_fixed` | `1` | `False` | V1 switch is fixed or bound intentionally disables filter |
| `stoch_reversal` | `exit_kind` | `disabled_or_fixed` | `trailing` | `False` | V1 switch is fixed or bound intentionally disables filter |
| `stoch_reversal` | `htf_mode` | `disabled_or_fixed` | `none` | `False` | V1 switch is fixed or bound intentionally disables filter |
| `stoch_reversal` | `max_adx` | `disabled_or_fixed` | `100.0` | `False` | V1 switch is fixed or bound intentionally disables filter |
| `stoch_reversal` | `max_aligned_funding_bps` | `disabled_or_fixed` | `10000.0` | `False` | V1 switch is fixed or bound intentionally disables filter |
| `stoch_reversal` | `max_leverage` | `structural_dormant` | `3.0` | `True` | code branch does not reference field |
| `stoch_reversal` | `min_dir_roc_bps` | `disabled_or_fixed` | `-10000.0` | `False` | V1 switch is fixed or bound intentionally disables filter |
| `stoch_reversal` | `pullback_atr` | `structural_dormant` | `0.75` | `True` | code branch does not reference field |
| `stoch_reversal` | `require_body_dir` | `disabled_or_fixed` | `False` | `False` | V1 switch is fixed or bound intentionally disables filter |
| `stoch_reversal` | `risk_fraction` | `structural_dormant` | `0.02` | `True` | code branch does not reference field |
| `stoch_reversal` | `roc_threshold_bps` | `structural_dormant` | `500.0` | `True` | code branch does not reference field |
| `stoch_reversal` | `roc_window` | `disabled_or_fixed` | `12` | `True` | V1 switch is fixed or bound intentionally disables filter |
| `stoch_reversal` | `side_mode` | `disabled_or_fixed` | `both` | `False` | V1 switch is fixed or bound intentionally disables filter |
| `stoch_reversal` | `sizing_kind` | `disabled_or_fixed` | `fixed` | `False` | V1 switch is fixed or bound intentionally disables filter |
| `stoch_reversal` | `tp_atr` | `structural_dormant` | `3.0` | `True` | code branch does not reference field |

## V2 继续保留和可微调的 active 字段

| Component | Field | Baseline | Variant rows |
| --- | --- | --- | ---: |
| `di_cross` | `ema_htf` | `89` | `1` |
| `di_cross` | `fixed_leverage` | `3.0` | `2` |
| `di_cross` | `htf_mode` | `h12` | `3` |
| `di_cross` | `max_adx` | `36.0` | `2` |
| `di_cross` | `max_aligned_funding_bps` | `8.0` | `2` |
| `di_cross` | `max_atr_bps` | `250.0` | `2` |
| `di_cross` | `max_dist_ema_bps` | `750.0` | `2` |
| `di_cross` | `max_hold_bars` | `18` | `2` |
| `di_cross` | `min_adx` | `12.0` | `2` |
| `di_cross` | `min_dir_roc_bps` | `-200.0` | `2` |
| `di_cross` | `min_rvol` | `2.0` | `2` |
| `di_cross` | `require_body_dir` | `True` | `1` |
| `di_cross` | `roc_window` | `24` | `2` |
| `di_cross` | `sl_atr` | `4.0` | `2` |
| `di_cross` | `style` | `di_cross` | `1` |
| `di_cross` | `tp_atr` | `1.5` | `2` |
| `stoch_reversal` | `cooldown_bars` | `24` | `3` |
| `stoch_reversal` | `ema_htf` | `55` | `1` |
| `stoch_reversal` | `fixed_leverage` | `2.0` | `2` |
| `stoch_reversal` | `indicator_window` | `21` | `2` |
| `stoch_reversal` | `macd_fast` | `8` | `2` |
| `stoch_reversal` | `macd_signal` | `5` | `2` |
| `stoch_reversal` | `macd_slow` | `21` | `2` |
| `stoch_reversal` | `max_atr_bps` | `400.0` | `2` |
| `stoch_reversal` | `max_dist_ema_bps` | `2500.0` | `2` |
| `stoch_reversal` | `max_hold_bars` | `8` | `2` |
| `stoch_reversal` | `min_adx` | `12.0` | `2` |
| `stoch_reversal` | `min_atr_bps` | `200.0` | `2` |
| `stoch_reversal` | `min_rvol` | `1.0` | `2` |
| `stoch_reversal` | `require_macd_turn` | `True` | `1` |
| `stoch_reversal` | `sl_atr` | `4.0` | `2` |
| `stoch_reversal` | `style` | `stoch_reversal` | `1` |
| `stoch_reversal` | `threshold_high` | `60.0` | `2` |
| `stoch_reversal` | `threshold_low` | `25.0` | `2` |
| `stoch_reversal` | `trail_activation_atr` | `1.0` | `2` |
| `stoch_reversal` | `trail_atr` | `1.0` | `2` |

## 防过拟合与实盘边界

- 消融中 prefit 同时提高年化并降低回撤、胜率 `>=50%` 的单字段行：`1`。它们只用于决定 V2 微调方向，不使用 reused holdout 排名。
- 所有交易继续使用 closed-bar signal、K+1 open 入场、入场即保护止损、stop gap-open、同 K stop-first、每 fill `0.001` fee + `4 bps` slippage 和实际 funding。
- Reused holdout 已在上一轮研究中解锁，本轮只能作为诊断窗口，不能重新包装为 untouched OOS。
- V1/V2 在 K+2 和高滑点压力未通过前均不得提升为 candidate、paper-live、dry-run、handoff 或 live。
