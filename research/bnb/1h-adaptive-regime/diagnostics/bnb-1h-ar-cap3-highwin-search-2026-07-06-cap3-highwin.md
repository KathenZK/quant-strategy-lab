# BNB-1H-Adaptive-Regime cap3 高胜率趋势/反转搜索 - 2026-07-06

## 结论

唯一冻结 primary 未能同时满足 full 与最近三个月 locked OOS 的 cap3 高胜率目标，当前为 `NO-GO / not promoted / not live-ready`。

- primary：`ENS__BNB_1H_CAP3_HW_N0501751__BNB_1H_CAP3_HW_N0663797`；kind/styles：`ensemble` / `ema_pullback+wick_reject`。
- prefit：annual `2.20x`，DD `-18.66%`，win `87.04%`，trades `108`，PF `2.648`。
- full：annual `1.87x`，return `222.63%`，DD `-22.86%`，win `84.25%`，trades `127`，PF `2.134`。
- locked OOS：annual `0.64x`，return `-10.67%`，DD `-22.86%`，win `68.42%`，trades `19`，PF `0.639`。
- cap3 high-win gate：`False`。

## 数据与协议

- Binance USD-M Futures `BNBUSDT` perpetual `1h`：`17520` 根闭合 K；UTC `2024-07-03T06:00:00+00:00` 至 `2026-07-03T05:00:00+00:00`；missing/duplicate=`0/0`。
- train：`2024-08-17T06:00:00+00:00` 至 `2025-10-07T01:00:00+00:00`；validation 至 `2026-04-03T06:00:00+00:00`；locked OOS 至 `2026-07-03T06:00:00+00:00`。
- prefit feature frame 物理排除 OOS；只评估一个预先落盘 primary。
- 杠杆硬约束：所有组件 `fixed_leverage/max_leverage <= 3.0`。

## 搜索覆盖

- curated_configs：`768`。
- random_configs：`500000`。
- first_pass_evaluated：`208885`。
- first_pass_eligible：`768`。
- first_pass_prefit_pass：`0`。
- neighbors_requested：`250000`。
- neighbors_evaluated：`198447`。
- neighbors_eligible：`38062`。
- neighbors_prefit_pass：`0`。
- retained_singles：`1500`。
- retained_ensembles：`300`。
- 机制覆盖：趋势类 `ema_cross/macd_flip/donchian_break/bb_break/ema_pullback/keltner_break/squeeze_release/di_cross/momentum_break`；反转类 `bb_revert/rsi_reversal/stoch_reversal/cci_reversal/williams_reversal/vwap_revert/wick_reject`；并测试趋势+反转 ensemble。

## 分片

| Window | Annual | Return | DD | Win | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `train` | `2.09x` | `131.53%` | `-18.21%` | `85.53%` | `76` | `2.350` |
| `validation` | `2.49x` | `55.98%` | `-13.66%` | `90.62%` | `32` | `3.893` |
| `locked_oos` | `0.64x` | `-10.67%` | `-22.86%` | `68.42%` | `19` | `0.639` |
| `full` | `1.87x` | `222.63%` | `-22.86%` | `84.25%` | `127` | `2.134` |
| `last_1d` | `1.00x` | `0.00%` | `0.00%` | `0.00%` | `0` | `0.000` |
| `last_7d` | `1.24x` | `0.41%` | `-0.35%` | `100.00%` | `1` | `inf` |
| `last_1m` | `3.58x` | `11.05%` | `-1.40%` | `100.00%` | `7` | `inf` |
| `last_3m` | `0.64x` | `-10.67%` | `-22.86%` | `68.42%` | `19` | `0.639` |
| `last_6m` | `1.24x` | `11.16%` | `-22.86%` | `77.14%` | `35` | `1.338` |
| `last_1y` | `1.29x` | `29.31%` | `-22.86%` | `79.66%` | `59` | `1.482` |

## Promotion 边界

cap3 high-win gate 未通过，禁止 candidate、paper-live、dry-run、handoff 或 live。

## 产物

- `research/bnb/1h-adaptive-regime/artifacts/bnb_1h_ar_cap3_highwin_frozen_primary_2026-07-06-cap3-highwin.json`
- `research/bnb/1h-adaptive-regime/artifacts/bnb_1h_ar_cap3_highwin_search_2026-07-06-cap3-highwin.json`
- `research/bnb/1h-adaptive-regime/artifacts/bnb_1h_ar_cap3_highwin_prefit_2026-07-06-cap3-highwin.csv`
- `research/bnb/1h-adaptive-regime/artifacts/bnb_1h_ar_cap3_highwin_slices_2026-07-06-cap3-highwin.csv`
- `research/bnb/1h-adaptive-regime/artifacts/bnb_1h_ar_cap3_highwin_primary_trades_2026-07-06-cap3-highwin.csv`
