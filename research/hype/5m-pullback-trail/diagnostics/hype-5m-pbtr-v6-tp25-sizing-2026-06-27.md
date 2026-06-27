# HYPE-5M-PBTR-V6 TP2.5 sizing 2026-06-27

Family id：`HYPE-5M-PBTR`

本报告测试用户提出的 sizing 方向：在 V6 上采用 `tp_atr=2.5`，再比较固定 `1x`、固定 `3x`，以及以 `3x` 为上限的波动率动态仓位。

## 口径

- 策略：V6 long-only，`EMA21/55`、`pullback_buffer=0.01`、`dir_ret192_bps>=788.123`。
- 出口：`TP=2.5ATR14`、`SL=7ATR14`、不 trailing、`36` 根 5m K 超时。
- 动态仓位：使用信号 K 的 `atr_ratio_14_96 = ATR14 / mean(ATR14, 96)`；波动越高，杠杆越低。
- 这是逐笔收益的 sizing replay，不额外模拟高杠杆下的滑点恶化、保证金约束或强平机制。

原始信号数：`1705`；过滤后信号数：`331`；实际交易数：`157`。

## 结果

| sizing | total | max DD | avg/trade | win | PF | payoff | worst | best | avg lev | lev range |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `fixed_1x` | `79.07%` | `-8.69%` | `0.38%` | `63.69%` | `1.773` | `1.011` | `-4.94%` | `3.08%` | `1.00x` | `1.00x-1.00x` |
| `fixed_3x` | `408.95%` | `-25.63%` | `1.15%` | `63.69%` | `1.773` | `1.011` | `-14.81%` | `9.23%` | `3.00x` | `3.00x-3.00x` |
| `vol_target1_floor0p5_cap3` | `351.31%` | `-23.89%` | `1.05%` | `63.69%` | `1.832` | `1.044` | `-14.81%` | `6.49%` | `2.62x` | `1.43x-3.00x` |
| `vol_target1_floor1_cap3` | `351.31%` | `-23.89%` | `1.05%` | `63.69%` | `1.832` | `1.044` | `-14.81%` | `6.49%` | `2.62x` | `1.43x-3.00x` |
| `vol_target0p8_floor0p5_cap3` | `264.63%` | `-21.37%` | `0.89%` | `63.69%` | `1.825` | `1.040` | `-14.81%` | `5.64%` | `2.25x` | `1.14x-3.00x` |
| `vol_target0p8_floor1_cap3` | `264.63%` | `-21.37%` | `0.89%` | `63.69%` | `1.825` | `1.040` | `-14.81%` | `5.64%` | `2.25x` | `1.14x-3.00x` |

## 结论

`tp_atr=2.5` 的 1x 回撤约 `-8.69%`，比 V6 原始 `TP=3ATR` 的主账回撤更低；固定 `3x` 将总收益放大到 `408.95%`，但最大回撤也扩大到 `-25.63%`。

本轮动态仓位里收益最高的是 `vol_target1_floor0p5_cap3`，总收益 `351.31%`、最大回撤 `-23.89%`、平均杠杆 `2.62x`。它相比固定 `3x` 主要是稍微降低高波动入场的仓位，但没有把回撤压回 1x 级别。

因此，`tp_atr=2.5 + 3x` 在回测里收益很漂亮，但已是高风险 sizing；波动率动态仓位能改善一点风险形态，却不是免费午餐。实盘前仍应先 paper audit 30-50 笔，确认滑点和 bracket 维护没有偏差。

## 产物

- 脚本：`research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v6_tp25_sizing.py`
- summary CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6_tp25_sizing_summary_2026-06-27.csv`
- trades CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6_tp25_sizing_trades_2026-06-27.csv`
- JSON：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6_tp25_sizing_2026-06-27.json`
