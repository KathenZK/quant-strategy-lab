# BNB-1H-Adaptive-Regime-V2 参数规格 - 2026-07-07

## 版本身份

- Version：`BNB-1H-Adaptive-Regime-V2`
- Short id：`BNB-1H-AR-V2`
- Market：Binance USD-M Futures `BNBUSDT` perpetual
- Timeframe：`1h`
- 状态：`clean-equivalent diagnostic observation / not promoted / not live-ready`
- 定义：V1 的 clean 参数版本。V1 全参数消融识别的 no-op 字段全部固定为已验证的 neutral 值；逐笔重放确认 V2 与 V1 交易路径完全一致（trade signature 相等）。
- 可执行定义：`../scripts/bnb_1h_ar_v2.py`
- 验证与多窗口证据：`../notes/bnb-1h-ar-v2-multiwindow-backtest-2026-07-07.md`
- 来源消融：`../ablations/bnb-1h-ar-v1-full-parameter-ablation-2026-07-06.md`

## 数据与执行口径

- 数据：`17520` 根闭合 `1h` K，UTC `2024-07-03T06:00:00+00:00` 至 `2026-07-03T05:00:00+00:00`；与 V1 冻结数据一致。
- Split：train 至 `2025-10-07T01:00:00+00:00`；validation 至 `2026-04-03T06:00:00+00:00`；locked OOS 至 `2026-07-03T06:00:00+00:00`。
- 成本：`0.001` fee/fill、`4 bps` adverse slippage/fill，逐笔计入 Binance funding。
- 执行：闭合 K 信号，下一根 `1h` open 市价成交；bracket 立即生效；同 K 双触发 stop-first；open 穿 stop 按 open 成交。
- 杠杆硬约束：`<= 3.0x`；V2 实际最大暴露 `2.0x`。

## Ensemble

- Merge priorities：`ema_pullback = 2.1431344645719372`，`wick_reject = 1.8729418183646944`；单仓，同时只保留优先级更高的 component trade。

## Component A：`ema_pullback` 活动参数

```json
{
  "style": "ema_pullback",
  "side_mode": "both",
  "ema_fast": 55,
  "ema_slow": 89,
  "pullback_atr": -0.25,
  "ema_htf": 377,
  "max_dist_ema_bps": 300.0,
  "min_rvol": 1.0,
  "min_atr_bps": 50.0,
  "exit_kind": "fixed",
  "tp_atr": 3.0,
  "sl_atr": 5.0,
  "max_hold_bars": 168,
  "cooldown_bars": 6,
  "entry_delay_bars": 1,
  "sizing_kind": "fixed",
  "fixed_leverage": 2.0
}
```

## Component B：`wick_reject` 活动参数

```json
{
  "style": "wick_reject",
  "side_mode": "both",
  "threshold_low": 0.35,
  "threshold_high": 0.85,
  "band_k": 0.5,
  "min_adx": 24.0,
  "min_rvol": 2.0,
  "htf_mode": "h12",
  "exit_kind": "fixed",
  "tp_atr": 1.0,
  "sl_atr": 5.0,
  "max_hold_bars": 72,
  "cooldown_bars": 24,
  "entry_delay_bars": 1,
  "sizing_kind": "fixed",
  "fixed_leverage": 0.75
}
```

被移除的 no-op 字段及其 neutral 固定值见 `../scripts/bnb_1h_ar_v2.py` 中 `EMA_PULLBACK_V2` / `WICK_REJECT_V2` 的完整定义。

## 指标（与 V1 等价）

| Window | Annual | Return | Max DD | Win | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| train | `2.09x` | `131.53%` | `-18.21%` | `85.53%` | `76` | `2.350` |
| validation | `2.49x` | `55.98%` | `-13.66%` | `90.62%` | `32` | `3.893` |
| prefit | `2.20x` | `261.15%` | `-18.66%` | `87.04%` | `108` | `2.648` |
| locked OOS | `0.64x` | `-10.67%` | `-22.86%` | `68.42%` | `19` | `0.639` |
| full | `1.87x` | `222.63%` | `-22.86%` | `84.25%` | `127` | `2.134` |

## Promotion 边界

V2 只是参数表示的清理，交易路径与 V1 完全一致，因此 locked OOS 失败结论原样继承。禁止 candidate、paper-live、dry-run、handoff 或 live。
