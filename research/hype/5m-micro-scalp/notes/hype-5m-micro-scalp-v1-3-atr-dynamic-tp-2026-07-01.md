# HYPE-5M-Micro-Scalp-V1.3 ATR 动态止盈回测 2026-07-01

Family id：`HYPE-5M-Micro-Scalp`

在 V1.3 入场/过滤/固定 SL 不变的前提下，将固定 `tp_bps=110` 替换为信号 K 的 ATR 动态止盈，并与基线对比。

## 动态止盈口径

- 信号仍用已收盘 K；入场仍为下一根 open + `4 bps` 不利滑点。
- 止损保持 V1.3 固定 `sl_bps=400`。
- `atr_abs`：`TP 距离 = tp_atr_mult × ATR14(signal bar)`。
- `atr_pct`：`TP bps = clip(tp_atr_mult × atr_pct_bps, 40, 250)`，再换算目标价。
- 目标价在入场时一次性确定，持仓内不 trailing；同 K 双触仍 stop-first。
- 成本：fee `0.001`/fill，slippage `4.0 bps`/fill。

## V1.3 固定 TP 基线

- trades `180`，ann `1.76x`，PF `1.934`。
- win `85.00%`，avg `34.96 bps`，maxDD `-9.96%`。
- target hit `83.33%`，VAL PF `5.081`，FWD PF `10.245`。

## 对比表

| variant | tp_mode | mult | trades | ann | PF | win | avg | maxDD | TP中位bps | target% | VAL PF | FWD PF |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `V1.3_fixed_tp_110bps` | `fixed` | `0.0` | `180` | `1.76x` | `1.934` | `85.00%` | `34.96 bps` | `-9.96%` | `110.0` | `83.33%` | `5.081` | `10.245` |
| `V1.3_atr_pct_x3.0` | `atr_pct` | `3.0` | `176` | `1.72x` | `1.514` | `73.30%` | `35.35 bps` | `-22.18%` | `163.7` | `68.75%` | `4.757` | `1.310` |
| `V1.3_atr_abs_x3.0` | `atr_abs` | `3.0` | `176` | `1.72x` | `1.514` | `73.30%` | `35.34 bps` | `-22.18%` | `163.7` | `68.75%` | `4.756` | `1.310` |
| `V1.3_atr_abs_x2.5` | `atr_abs` | `2.5` | `177` | `1.64x` | `1.538` | `76.27%` | `31.88 bps` | `-16.08%` | `136.6` | `73.45%` | `6.452` | `2.107` |
| `V1.3_atr_pct_x2.5` | `atr_pct` | `2.5` | `177` | `1.64x` | `1.538` | `76.27%` | `31.87 bps` | `-16.09%` | `136.5` | `73.45%` | `6.453` | `2.107` |
| `V1.3_atr_pct_x3.5` | `atr_pct` | `3.5` | `175` | `1.60x` | `1.400` | `67.43%` | `31.30 bps` | `-20.85%` | `191.1` | `61.71%` | `2.950` | `1.327` |
| `V1.3_atr_abs_x2.0` | `atr_abs` | `2.0` | `179` | `1.58x` | `1.604` | `81.56%` | `29.07 bps` | `-19.66%` | `109.8` | `79.89%` | `4.980` | `10.589` |
| `V1.3_atr_pct_x2.0` | `atr_pct` | `2.0` | `179` | `1.58x` | `1.604` | `81.56%` | `29.07 bps` | `-19.66%` | `109.7` | `79.89%` | `4.980` | `10.589` |
| `V1.3_atr_abs_x1.5` | `atr_abs` | `1.5` | `181` | `1.30x` | `1.405` | `86.74%` | `16.54 bps` | `-14.63%` | `82.0` | `86.19%` | `3.371` | `inf` |

## 结论

- 最佳动态 TP 为 `V1.3_atr_pct_x3.0`（`atr_pct` × `3.0`）：ann `1.72x`（Δ `-0.04x`），maxDD `-22.18%`（Δ `-12.22pp`），target hit `68.75%`。
- 本实验只替换止盈模型；不构成 live-ready 证明。
- 若推进实盘，还需审计 bracket 下单时 ATR 快照、最小价格精度、以及动态 TP 是否可在入场瞬间稳定挂出。

## 产物

- Script：`research/hype/5m-micro-scalp/scripts/research_hype_5m_micro_scalp_v1_3_atr_dynamic_tp.py`
- Summary CSV：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_v1_3_atr_dynamic_tp_summary_2026-07-01.csv`
- Trades CSV：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_v1_3_atr_dynamic_tp_trades_2026-07-01.csv`
- JSON：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_v1_3_atr_dynamic_tp_2026-07-01.json`
