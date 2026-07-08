# BNB-1H-Adaptive-Regime-V1 参数规格 - 2026-07-06

## 版本身份

- Version：`BNB-1H-Adaptive-Regime-V1`
- Short id：`BNB-1H-AR-V1`
- Market：Binance USD-M Futures `BNBUSDT` perpetual
- Timeframe：`1h`
- 状态：`diagnostic observation / not promoted / not live-ready`
- 来源：2026-07-06 `<=3x` 高胜率趋势/反转搜索的唯一冻结 primary。
- Evidence：`../diagnostics/bnb-1h-ar-cap3-highwin-search-2026-07-06-cap3-highwin.md`

## 数据与执行口径

- 数据：`17520` 根闭合 `1h` K，UTC `2024-07-03T06:00:00+00:00` 至 `2026-07-03T05:00:00+00:00`；missing/duplicate=`0/0`。
- Split：train `2024-08-17T06:00:00+00:00` 至 `2025-10-07T01:00:00+00:00`；validation 至 `2026-04-03T06:00:00+00:00`；locked OOS 至 `2026-07-03T06:00:00+00:00`。
- 成本：`0.001` fee/fill、`4 bps` adverse slippage/fill，并逐笔计入 Binance funding。
- 执行：闭合 K 产生信号，下一根 `1h` open 市价成交；入场后保护性 bracket 立即生效；同 K 双触发 stop-first；open 穿越 stop 按 open 成交。
- 杠杆：搜索硬约束 `fixed_leverage/max_leverage <= 3.0`；V1 实际最大暴露为 `2.0x`。

## V1 冻结 primary

- Primary：`ENS__BNB_1H_CAP3_HW_N0501751__BNB_1H_CAP3_HW_N0663797`
- Kind：`ensemble`
- Styles：`ema_pullback + wick_reject`
- Merge priorities：`2.1431344645719372` / `1.8729418183646944`

## 指标

| Window | Annual | Return | Max DD | Win | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| train | `2.09x` | `131.53%` | `-18.21%` | `85.53%` | `76` | `2.350` |
| validation | `2.49x` | `55.98%` | `-13.66%` | `90.62%` | `32` | `3.893` |
| prefit | `2.20x` | `261.15%` | `-18.66%` | `87.04%` | `108` | `2.648` |
| locked OOS | `0.64x` | `-10.67%` | `-22.86%` | `68.42%` | `19` | `0.639` |
| full | `1.87x` | `222.63%` | `-22.86%` | `84.25%` | `127` | `2.134` |

## Component A：`ema_pullback`

```json
{
  "name": "BNB_1H_CAP3_HW_N0501751",
  "style": "ema_pullback",
  "side_mode": "both",
  "ema_fast": 55,
  "ema_slow": 89,
  "ema_htf": 377,
  "indicator_window": 32,
  "threshold_low": 15.0,
  "threshold_high": 65.0,
  "band_k": 3.0,
  "pullback_atr": -0.25,
  "roc_window": 3,
  "roc_threshold_bps": 200.0,
  "macd_fast": 21,
  "macd_slow": 55,
  "macd_signal": 9,
  "min_adx": 0.0,
  "max_adx": 100.0,
  "min_rvol": 1.0,
  "min_atr_bps": 50.0,
  "max_atr_bps": 250.0,
  "min_dir_roc_bps": -10000.0,
  "max_dist_ema_bps": 300.0,
  "htf_mode": "none",
  "require_macd_turn": false,
  "require_body_dir": false,
  "max_aligned_funding_bps": 8.0,
  "exit_kind": "fixed",
  "tp_atr": 3.0,
  "sl_atr": 5.0,
  "trail_activation_atr": 4.0,
  "trail_atr": 1.5,
  "max_hold_bars": 168,
  "cooldown_bars": 6,
  "entry_delay_bars": 1,
  "sizing_kind": "fixed",
  "fixed_leverage": 2.0,
  "risk_fraction": 0.02,
  "max_leverage": 3.0
}
```

## Component B：`wick_reject`

```json
{
  "name": "BNB_1H_CAP3_HW_N0663797",
  "style": "wick_reject",
  "side_mode": "both",
  "ema_fast": 55,
  "ema_slow": 144,
  "ema_htf": 144,
  "indicator_window": 20,
  "threshold_low": 0.35,
  "threshold_high": 0.85,
  "band_k": 0.5,
  "pullback_atr": -0.25,
  "roc_window": 48,
  "roc_threshold_bps": 150.0,
  "macd_fast": 21,
  "macd_slow": 55,
  "macd_signal": 9,
  "min_adx": 24.0,
  "max_adx": 100.0,
  "min_rvol": 2.0,
  "min_atr_bps": 0.0,
  "max_atr_bps": 300.0,
  "min_dir_roc_bps": -10000.0,
  "max_dist_ema_bps": 2500.0,
  "htf_mode": "h12",
  "require_macd_turn": false,
  "require_body_dir": false,
  "max_aligned_funding_bps": 10000.0,
  "exit_kind": "fixed",
  "tp_atr": 1.0,
  "sl_atr": 5.0,
  "trail_activation_atr": 0.75,
  "trail_atr": 2.5,
  "max_hold_bars": 72,
  "cooldown_bars": 24,
  "entry_delay_bars": 1,
  "sizing_kind": "fixed",
  "fixed_leverage": 0.75,
  "risk_fraction": 0.025,
  "max_leverage": 2.5
}
```

## Promotion 边界

V1 只登记为 diagnostic observation。它满足 prefit 高胜率低回撤观察形态，但 locked OOS 的收益、胜率和回撤均失败，不得标记为 candidate、paper-live、dry-run、handoff 或 live。
