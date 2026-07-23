# HYPE-15M-MMTF-V3 最终审计 — 2026-07-22

## 最终结论

`HYPE-15M-MMTF-V3` 未达到目标，保持 `registered / HARD-GATE-FAILED / not promoted / not live-ready`。不得交接 runner、进入 dry-run 或上线；按状态机规则，dry-run 前不写 `NO-GO`。

## 核心窗口

| 窗口 | total return | annual factor | CAGR | MDD | WR | trades | PF | trade Sharpe | payoff |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train（至 2026-01-22） | `+65.88%` | `2.181x` | `118.09%` | `18.07%` | `89.19%` | `74` | `2.721` | `3.000` | `0.330` |
| validation 90d | `+40.53%` | `3.979x` | `297.87%` | `12.52%` | `100.00%` | `26` | `inf` | - | - |
| prefit（含 validation） | `+133.11%` | `2.573x` | `157.33%` | `18.07%` | `92.00%` | `100` | `3.835` | `4.082` | `0.333` |
| locked OOS 3m | `-14.78%` | `0.526x` | `-47.38%` | `21.88%` | `76.19%` | `21` | `0.547` | `-1.218` | `0.171` |
| full | `+98.65%` | `1.822x` | `82.15%` | `21.88%` | `89.26%` | `121` | `2.227` | `2.172` | `0.268` |

全样本距离硬目标：annual factor 仅为 `20x` 的 `9.11%`（约差 `10.98` 倍），CAGR 比 `1900%` 低 `1817.85pp`，MDD 超限 `1.88pp`；只有胜率通过。locked OOS 的 annual、MDD、WR 三项均失败。

## 最近切片

| 切片 | return | MDD | WR | trades |
| --- | ---: | ---: | ---: | ---: |
| 1d | `-11.85%` | `11.85%` | `0%` | `1` |
| 7d | `-11.85%` | `11.85%` | `0%` | `1` |
| 1m | `-6.88%` | `11.86%` | `75.00%` | `8` |
| 3m | `-15.14%` | `21.88%` | `75.00%` | `20` |
| 6m | `+19.76%` | `21.88%` | `89.36%` | `47` |
| 1y | `+88.40%` | `21.88%` | `88.89%` | `108` |

## 成本、尾部与杠杆

- full 的逐笔成本贡献合计：fee `-0.726`、slippage `-0.29042`、funding `+0.000369`；这是逐笔 return contribution 之和，不与复利净值直接相加。
- full 最大单笔亏损 `-17.55%`，最多连续亏损 `2`；高胜率由小 TP/大亏损尾部换取，平均盈亏比仅 `0.268`。
- `1x/2x/3x` full annual factor 分别 `1.234/1.508/1.822x`，MDD `7.37/14.67/21.88%`；3x 已违反回撤门槛，而 1x/2x 收益离 20x 更远。
- 双倍实际 funding 对结论几乎无影响；主要问题不是 funding，而是进场时点、相位与少数大亏损。

## 稳健性与可执行性

- K+2/4bps：full `-48.19%`、MDD `71.76%`；K+2/8bps：full `-61.37%`、MDD `74.85%`。
- K+1/8bps：full `+48.75%`，但 MDD `23.15%`，仍失败。
- 真实 1m 重聚合相位：native `+133.11%`；offset 5m `-51.26%`；offset 10m `-22.16%`；phase gate 失败。
- trade bootstrap：full MDD<20% 概率 `56.14%`，locked OOS 仅 `46.48%`。
- 极端波动 30d 窗口未出现爆仓；静态检查确认单净仓、无重叠、K+1 入场、最大 3x、stop-first 与 gap-open stop。
- 没有 quant-runner 实现，因此拒单恢复、断流 fail-closed、重启恢复、kill switch 和真实保护单行为均未证明；这本身是 promotion blocker。

## 下一机制建议

1. 不得在已揭示 OOS 上继续微调本配置；重开必须使用 `2026-07-22 11:45 UTC` 之后的 prospective OOS。
2. 若继续 15m 趋势线，应换成 materially new 的 breakout-retest / multi-bar confirmation 状态机，显式降低 K+1 与原生 bar 边界依赖，而不是继续微调 Keltner 阈值。
3. 重新设计 payoff：当前 `0.75 ATR` TP 与宽 stop 产生高胜率、低盈亏比；需要能保留趋势尾部的分层退出或 campaign，但必须重新通过 live-executable stop 审计。
4. 可研究真实 1m/5m 执行确认后的 15m signal，而不是假定 native 15m close 后一个固定 open 能稳定捕获同一价格路径。

## 证据

- [prefit robustness JSON](../artifacts/hype_15m_mmtf_v3_prefit_robustness_2026-07-22.json)
- [one-time locked OOS JSON](../artifacts/hype_15m_mmtf_v3_locked_oos_reveal_2026-07-22.json)
- [locked OOS trades](../artifacts/hype_15m_mmtf_v3_locked_oos_trades_2026-07-22.csv)
- [full trades](../artifacts/hype_15m_mmtf_v3_full_trades_2026-07-22.csv)
- [parameter neighborhood](../artifacts/hype_15m_mmtf_v3_parameter_neighborhood_2026-07-22.csv)
- [tests](../../../../tests/test_hype_15m_mmtf.py)

