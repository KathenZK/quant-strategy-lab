# BNB-1H-Adaptive-Regime-V1 Clean 参数规格 - 2026-07-06

## 身份与边界

- Base version：`BNB-1H-Adaptive-Regime-V1`
- Clean spec status：交易路径等价的 clean specification，不是新版本，不是 promotion。
- Evidence：`../ablations/bnb-1h-ar-v1-full-parameter-ablation-2026-07-06.md`
- 结论：全参数消融识别出 `32` 个交易路径完全不变的 no-op 字段；本规格只保留 V1 交易路径需要的活动参数。

## V1 等价指标

删除 no-op 参数不改变交易路径，因此指标与 V1 相同：

| Window | Annual | Return | Max DD | Win | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| train | `2.09x` | `131.53%` | `-18.21%` | `85.53%` | `76` | `2.350` |
| validation | `2.49x` | `55.98%` | `-13.66%` | `90.62%` | `32` | `3.893` |
| prefit | `2.20x` | `261.15%` | `-18.66%` | `87.04%` | `108` | `2.648` |
| locked OOS | `0.64x` | `-10.67%` | `-22.86%` | `68.42%` | `19` | `0.639` |
| full | `1.87x` | `222.63%` | `-22.86%` | `84.25%` | `127` | `2.134` |

## Ensemble

- Component A priority：`2.1431344645719372`
- Component B priority：`1.8729418183646944`
- 单仓 merge：同一时间只保留优先级更高的 component trade。

## Component A：`ema_pullback`

保留参数：

```json
{
  "style": "ema_pullback",
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

删除参数：

- 交易路径完全不变：`band_k`、`indicator_window`、`macd_fast`、`macd_signal`、`macd_slow`、`max_adx`、`max_aligned_funding_bps`、`max_atr_bps`、`max_leverage`、`risk_fraction`、`roc_threshold_bps`、`roc_window`、`threshold_high`、`threshold_low`、`trail_activation_atr`、`trail_atr`。
- 原值已是 neutral/no-filter，可从 clean spec 省略：`side_mode=both`、`min_adx=0`、`min_dir_roc_bps=-10000`、`htf_mode=none`、`require_macd_turn=false`、`require_body_dir=false`。

## Component B：`wick_reject`

保留参数：

```json
{
  "style": "wick_reject",
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

删除参数：

- 交易路径完全不变：`ema_fast`、`ema_htf`、`ema_slow`、`indicator_window`、`macd_fast`、`macd_signal`、`macd_slow`、`max_atr_bps`、`max_dist_ema_bps`、`max_leverage`、`pullback_atr`、`risk_fraction`、`roc_threshold_bps`、`roc_window`、`trail_activation_atr`、`trail_atr`。
- 原值已是 neutral/no-filter，可从 clean spec 省略：`side_mode=both`、`max_adx=100`、`min_atr_bps=0`、`min_dir_roc_bps=-10000`、`max_aligned_funding_bps=10000`、`require_macd_turn=false`、`require_body_dir=false`。

## 不可删除的执行口径

以下不是可删参数，即使不写在策略信号 clean spec 中，也必须由回测/实盘执行层强制：

- Binance 成本：`0.001` fee/fill、`4 bps` slippage/fill。
- Funding：逐笔计入 Binance 历史 funding。
- Entry：闭合 K 产生信号，下一根 `1h` open 市价成交。
- Exit：入场后 bracket 立即生效；同 K 双触发 stop-first；open 穿 stop 按 open 成交。
- `entry_delay_bars=1` 是 live-executable 时序边界，不得删除。

## Promotion 边界

Clean spec 只删除 no-op 参数，不修复 V1 的 locked OOS 失败。`BNB-1H-Adaptive-Regime-V1` 仍为 `diagnostic observation / not promoted / not live-ready`。
