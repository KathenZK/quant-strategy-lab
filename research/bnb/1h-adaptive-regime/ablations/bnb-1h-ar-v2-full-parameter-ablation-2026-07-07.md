# BNB-1H-Adaptive-Regime-V2 全参数消融 - 2026-07-07

## 结论

V2 全参数消融完成：`29` 个受检字段中 `27` 个为 active（存在改变交易路径的取值），`0` 个在全部扫描取值下交易路径不变（可移除）。V2 仍为 `diagnostic observation / not promoted / not live-ready`；本报告不用于 OOS 后验选参。

- Baseline prefit：`2.20x` / `261.15%` / `-18.66%` / `87.04%` / `108`。
- Baseline locked OOS：`0.64x` / `-10.67%` / `-22.86%` / `68.42%` / `19`。
- Baseline full：`1.87x` / `222.63%` / `-22.86%` / `84.25%` / `127`。
- 消融 rows：`122`（含 component removal 与 exit_kind 联动变体）。

## 字段分类

| Component | Field | Classification | Variants | Path-changing |
| --- | --- | --- | ---: | ---: |
| `ema_pullback` | `cooldown_bars` | `active` | `5` | `4` |
| `ema_pullback` | `ema_fast` | `active` | `4` | `4` |
| `ema_pullback` | `ema_htf` | `active` | `4` | `4` |
| `ema_pullback` | `ema_slow` | `active` | `4` | `4` |
| `ema_pullback` | `exit_kind` | `active` | `3` | `3` |
| `ema_pullback` | `fixed_leverage` | `active` | `4` | `4` |
| `ema_pullback` | `max_dist_ema_bps` | `active` | `5` | `5` |
| `ema_pullback` | `max_hold_bars` | `active` | `6` | `6` |
| `ema_pullback` | `min_atr_bps` | `active` | `4` | `4` |
| `ema_pullback` | `min_rvol` | `active` | `6` | `6` |
| `ema_pullback` | `pullback_atr` | `active` | `5` | `5` |
| `ema_pullback` | `side_mode` | `active` | `2` | `2` |
| `ema_pullback` | `sl_atr` | `active` | `5` | `5` |
| `ema_pullback` | `tp_atr` | `active` | `7` | `7` |
| `wick_reject` | `band_k` | `active` | `5` | `5` |
| `wick_reject` | `cooldown_bars` | `active` | `4` | `4` |
| `wick_reject` | `exit_kind` | `active` | `3` | `3` |
| `wick_reject` | `fixed_leverage` | `active` | `4` | `4` |
| `wick_reject` | `htf_mode` | `active` | `3` | `3` |
| `wick_reject` | `max_hold_bars` | `active` | `5` | `5` |
| `wick_reject` | `min_adx` | `active` | `6` | `6` |
| `wick_reject` | `min_rvol` | `active` | `5` | `5` |
| `wick_reject` | `side_mode` | `active` | `2` | `2` |
| `wick_reject` | `sl_atr` | `active` | `4` | `4` |
| `wick_reject` | `threshold_high` | `active` | `3` | `3` |
| `wick_reject` | `threshold_low` | `active` | `4` | `4` |
| `wick_reject` | `tp_atr` | `active` | `4` | `4` |
| `ema_pullback` | `entry_delay_bars` | `execution_timing_parameter` | `2` | `2` |
| `wick_reject` | `entry_delay_bars` | `execution_timing_parameter` | `2` | `2` |

## Prefit 改进方向（仅供微调，不构成版本变更）

以下单字段变体在 train/validation/prefit 上不差于 baseline 且 prefit 年化更高；它们改变交易路径，只能作为微调搜索的方向输入：

- `ema_pullback.exit_kind=trailing_a2.0_t1.5`：prefit `2.36x / -14.87% / 89.52%`。
- `ema_pullback.min_rvol=0.8`：prefit `2.32x / -18.21% / 85.96%`。
- `ema_pullback.ema_slow=144`：prefit `2.30x / -14.87% / 87.16%`。
- `wick_reject.threshold_high=0.75`：prefit `2.25x / -18.11% / 86.32%`。
- `wick_reject.max_hold_bars=48`：prefit `2.23x / -18.21% / 87.04%`。
- `wick_reject.threshold_low=0.4`：prefit `2.23x / -18.30% / 87.50%`。
- `ema_pullback.max_hold_bars=240`：prefit `2.21x / -18.21% / 87.04%`。
- `wick_reject.threshold_high=0.8`：prefit `2.21x / -18.11% / 87.39%`。

## Component removal

| Removed | Prefit | Locked OOS | Full |
| --- | --- | --- | --- |
| `ema_pullback` | `1.13x / -6.64% / 92.73%` | `0.99x / -4.00% / 80.00%` | `1.11x / -6.64% / 90.77%` |
| `wick_reject` | `1.85x / -19.50% / 78.95%` | `0.72x / -18.23% / 60.00%` | `1.63x / -19.50% / 76.12%` |

## 产物

- `research/bnb/1h-adaptive-regime/artifacts/bnb_1h_ar_v2_full_ablation_2026-07-07.json`
- `research/bnb/1h-adaptive-regime/artifacts/bnb_1h_ar_v2_full_ablation_rows_2026-07-07.csv`
- `research/bnb/1h-adaptive-regime/artifacts/bnb_1h_ar_v2_full_ablation_fields_2026-07-07.csv`
