# HYPE-1H-MMTF V3 最终审计 — 2026-07-22

## 最终结论

`HYPE-1H-Multi-Mechanism-Trend-Following-V3` 为明确 `HARD-GATE-FAILED / NO-GO / not promoted / not live-ready`。locked OOS 只揭示一次，冻结哈希核对通过；揭示后没有继续调参。

## 冻结窗口指标

| Window | Annual factor | Total return | MDD | Win rate | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Prefit | `7.3616x` | `+497.28%` | `19.83%` | `88.33%` | `60` | `4.794` |
| Locked OOS | `1.7887x` | `+15.59%` | `33.07%` | `84.62%` | `13` | `1.732` |
| Full | `5.4102x` | `+590.40%` | `33.07%` | `87.67%` | `73` | `3.768` |

目标要求完整样本和 OOS 同时 `>=20x / >=80% / <20%`，交易数至少 `60/15`。OOS 年化、回撤和交易数失败；full 年化与回撤失败。胜率通过不能抵消其他硬失败。

成本分解为逐笔相对收益项求和：full fee `-36.50%`、slippage `-14.65%`、funding `-0.27%`；OOS fee `-6.50%`、slippage `-2.63%`、funding `+0.03%`。这些是归一化 return charges，不是可直接相加到复利总收益的 USDT PnL。

## 最近切片

| Slice | Annual factor | Total return | MDD | Win rate | Trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1d | `1.0000x` | `0.00%` | `0.00%` | - | `0` |
| 7d | `3.4450x` | `+2.40%` | `3.28%` | `100%` | `1` |
| 1m | `2.7375x` | `+8.62%` | `14.70%` | `100%` | `3` |
| 3m | `1.8003x` | `+15.59%` | `33.07%` | `84.62%` | `13` |
| 6m | `4.9998x` | `+121.03%` | `33.07%` | `86.67%` | `30` |
| 1y | `5.0071x` | `+400.16%` | `33.07%` | `86.15%` | `65` |

短切片年化仅作形状诊断；`1d/7d/1m` 样本不足，不能当通过证据。

| Slice | PF | Fee return sum | Slippage return sum | Funding return sum |
| --- | ---: | ---: | ---: | ---: |
| 1d | `0.000` | `0.00%` | `0.00%` | `0.00%` |
| 7d | `inf` | `-0.50%` | `-0.20%` | `0.00%` |
| 1m | `inf` | `-1.50%` | `-0.60%` | `+0.05%` |
| 3m | `1.732` | `-6.50%` | `-2.63%` | `+0.03%` |
| 6m | `3.525` | `-15.00%` | `-6.06%` | `+0.01%` |
| 1y | `3.324` | `-32.50%` | `-13.03%` | `-0.23%` |

## 稳健性与执行门禁

- K+2：prefit `1.6354x / 64.80% MDD`，full `1.4886x / 64.80%`；失败。
- 8bps/fill：prefit MDD `20.49%`，full `33.32%`；失败。
- K+2 + 8bps：full `1.3052x / 66.31%`；失败。
- 30m shifted phase：annual factor `1.9147x`，仅 native `7.3636x` 的 `26.0%`；MDD `43.98%`，为 native 的 `2.22x`；门禁失败。
- 参数邻域 `23` 个，只有 `7` 个保持 prefit/validation 胜率、回撤与样本形状；MC full trade bootstrap 的 MDD `<20%` 概率仅 `27.56%`。
- 静态状态机：K+1、单净仓、最大 `2.5x`、stop/TP 保护与 stop-first 已验证；但没有 runner、重启恢复、拒单恢复、missing-bar fail-closed 或 kill switch 证据。

## 后续边界

不得利用已揭示的 `[2026-04-22 10:00, 2026-07-22 10:00) UTC` OOS 继续追参。若继续 HYPE 1h 趋势研究，应切换到对单一收线边界与一根延迟不敏感的 multi-bar hysteresis / trend-campaign 机制，并把 `2026-07-22 10:00 UTC` 之后的数据作为新 prospective OOS；该方向不得继承 V3 的通过结论。

机器证据：[prefit robustness](../artifacts/hype_1h_mmtf_v3_prefit_robustness_2026-07-22.json) · [one-time OOS reveal](../artifacts/hype_1h_mmtf_v3_locked_oos_reveal_2026-07-22.json) · [full trades](../artifacts/hype_1h_mmtf_v3_full_trades_2026-07-22.csv) · [full equity](../artifacts/hype_1h_mmtf_v3_full_equity_2026-07-22.csv)
