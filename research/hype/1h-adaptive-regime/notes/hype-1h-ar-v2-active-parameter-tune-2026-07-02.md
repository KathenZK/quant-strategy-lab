# HYPE-1H-Adaptive-Regime-V2 active 参数微调 - 2026-07-02

## 结论

V2 clean baseline 已与 V1 做逐笔等价校验：DI component=`True`、Stoch component=`True`、merged=`True`。V2 不是换回测口径，而是删除 dormant 字段后的同一状态机。

微调只使用 prefit 与其内部 `4` 个时间块排序：DI `30000` 组、Stoch `30000` 组、组合 `19600` 组；reused holdout 在参数冻结后才作诊断，未参与 selection score。

冻结微调观察：`HYPE-1H-Adaptive-Regime-V2-TUNE__di_cross_021938__stoch_reversal_025279`；状态 `prefit_improvement_only_not_live_ready`。

## V2 与冻结微调观察对比

| Metric | V2 baseline prefit | Tune prefit | V2 current full | Tune current full |
| --- | ---: | ---: | ---: | ---: |
| Annual multiple | `11.67x` | `34.42x` | `9.68x` | `15.61x` |
| Max DD | `-16.93%` | `-16.17%` | `-19.64%` | `-36.57%` |
| Win rate | `79.25%` | `92.50%` | `78.26%` | `91.30%` |
| Trades | `53` | `40` | `69` | `46` |

## 冻结微调参数

### DI-cross

- `ema_htf = 89`
- `min_adx = 12.0`
- `max_adx = 36.0`
- `min_rvol = 2.0`
- `max_atr_bps = 400.0`
- `roc_window = 24`
- `min_dir_roc_bps = -200.0`
- `max_dist_ema_bps = 750.0`
- `htf_mode = h12`
- `require_body_dir = True`
- `max_aligned_funding_bps = 8.0`
- `tp_atr = 1.25`
- `sl_atr = 4.0`
- `max_hold_bars = 18`
- `fixed_leverage = 4.0`

### Stoch-reversal

- `indicator_window = 21`
- `threshold_low = 25.0`
- `threshold_high = 60.0`
- `ema_htf = 55`
- `min_adx = 10.0`
- `min_rvol = 1.0`
- `min_atr_bps = 250.0`
- `max_atr_bps = 400.0`
- `max_dist_ema_bps = 1500.0`
- `macd_fast = 34`
- `macd_slow = 89`
- `macd_signal = 13`
- `require_macd_turn = False`
- `sl_atr = 4.0`
- `trail_activation_atr = 1.0`
- `trail_atr = 1.0`
- `max_hold_bars = 18`
- `cooldown_bars = 24`
- `fixed_leverage = 3.5`

## 实盘压力

| Scenario | Current full ann | Full DD | Reused holdout ann | Holdout DD | Holdout win |
| --- | ---: | ---: | ---: | ---: | ---: |
| `base_k1` | `15.61x` | `-36.57%` | `1.05x` | `-36.57%` | `83.33%` |
| `delay_k2` | `5.33x` | `-43.57%` | `0.10x` | `-43.57%` | `66.67%` |
| `delay_k3` | `1.48x` | `-61.13%` | `0.40x` | `-31.19%` | `71.43%` |
| `slip_8bps` | `14.18x` | `-36.69%` | `1.00x` | `-36.69%` | `83.33%` |
| `slip_10bps` | `12.57x` | `-36.76%` | `0.97x` | `-36.76%` | `83.33%` |
| `fee12_slip8` | `13.23x` | `-36.83%` | `0.96x` | `-36.83%` | `83.33%` |
| `double_cost` | `10.02x` | `-37.40%` | `0.81x` | `-37.40%` | `83.33%` |

## Promotion 边界

- Current full 严格实现更高收益、更低回撤且胜率 `>=50%`：`False`。
- K+2 与 8 bps slippage reused-holdout 联合压力通过：`False`。
- 即使数值改善，reused holdout 已不是 untouched OOS；在新增 forward trades、生产 runner、restart recovery、exchange reconciliation、missing-bar fail-closed、kill switch 和真实 stop-market 滑点证据完成前，不提升为 candidate、paper-live、dry-run、handoff 或 live。
