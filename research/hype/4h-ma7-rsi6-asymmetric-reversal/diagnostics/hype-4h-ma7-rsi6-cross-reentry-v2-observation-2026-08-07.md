# HYPE 4H MA7-RSI6 Cross-Reentry V2 观察（2026-08-07）

## 结论

V2 按用户确认只修改空头回多：空头收盘重新站上 SMA7 时，下一根 `4h` open 优先平空反多；多头跌破后的做空仍保留“最近三根至少一根 RSI6 `>70`”过滤。

该改动能捕捉图中空头后的 MA7 上穿，但整体质量显著下降：原生相位全期从 V1 的 `+113.10%` 降至 `+12.16%`，MDD 从 `-57.76%` 恶化至 `-66.94%`，PF 从 `1.36` 降至 `1.03`；同期 buy-and-hold 为 `+57.13%`。V2 不采纳、不登记。

## 冻结变更

- `flat -> long`：`close > SMA7`。
- `long -> short`：`close < SMA7`，且最近三根中至少一根 Wilder RSI6 `>70`。
- `short -> long`：`close > SMA7`，优先于 RSI6 `<30`。
- `short -> flat`：未重新站上 SMA7，但当前 RSI6 `<30`。
- 所有信号在下一根 `4h` open 执行；直接反手按两次 fill。

完整口径见[V2 观察合同](../specs/hype-4h-ma7-rsi6-cross-reentry-v2-observation-contract-2026-08-07.md)。

## V1 / V2 对比

| 指标 | V1 baseline | V2 Cross-Reentry |
| --- | ---: | ---: |
| 全期收益 | `+113.10%` | `+12.16%` |
| Buy-and-hold 超额 | `+55.98pp` | `-44.97pp` |
| MDD | `-57.76%` | `-66.94%` |
| Sharpe | `1.14` | `0.58` |
| PF | `1.36` | `1.03` |
| 交易数 | `81` | `139` |
| fills | `162` | `278` |
| 直接反手 | `40` | `120` |
| 最后 120 日 | `+30.96%` | `+25.73%` |

V2 新增了 `51` 次 `short -> long` 直接反手。总交易循环明显增加，成本累计达到初始权益的 `41.75%`；但 gross 无 fee/slippage 也只剩 `+65.54%`，因此下降不是纯成本问题。

## 场景审计

| 场景 | 收益 | MDD | PF |
| --- | ---: | ---: | ---: |
| Base | `+12.16%` | `-66.94%` | `1.03` |
| `8 bps/fill` | `+0.35%` | `-67.15%` | `1.00` |
| 额外延迟一根 `4h` | `+23.34%` | `-69.06%` | `1.06` |
| Gross：fee/slippage 为 `0` | `+65.54%` | `-66.18%` | `1.17` |
| Buy-and-hold | `+57.13%` | `-70.54%` | — |

最后 `120d` base 为 `+25.73%`、MDD `-37.52%`，仍低于同期持有的 `+44.99%`。

## 多空贡献

| Side | 交易数 | PF | 中位持仓 | 净 PnL（初始权益单位） |
| --- | ---: | ---: | ---: | ---: |
| Long | `70` | `1.13` | `94h` | `+0.317` |
| Short | `69` | `0.83` | `12h` | `-0.195` |

V1 的 short PF 为 `1.16`、净 PnL `+0.251`、中位持仓 `52h`；V2 频繁在上穿 MA7 时平空反多，把空头缩短到中位 `12h` 并使空头腿转亏。同时后续多头路径也改变，多头净 PnL 从 V1 的 `+0.880` 降至 `+0.317`。

## 相位与时间稳定性

| 4H 起点 | V1 | V2 |
| --- | ---: | ---: |
| `0h` | `+113.10%` | `+12.16%` |
| `1h` | `-51.65%` | `-25.32%` |
| `2h` | `-78.77%` | `-38.95%` |
| `3h` | `+177.22%` | `+10.90%` |

V2 压缩了相位极端值，却仍有两个相位显著亏损，不能通过相位门禁。

- 12 个 rolling `90d` 窗口只有 `5` 个盈利。
- 最差窗口 `-42.91%`，最好 `+47.97%`。
- 最近 `1d/7d/1m/3m/6m/1y` 为 `+0.42% / +3.86% / +3.83% / +42.71% / -5.67% / +2.69%`。

## 决策

- V2 解决了图形上“空头重新站上 MA7 未及时反多”的局部观感，但引入更多短周期反复切换。
- 历史超额、PF、rolling 和相位均不足；不采纳 V2，不替换 V1 baseline，不登记版本。
- V1 baseline 本身仍因相位失败和无保护状态保持 `explore / not promoted / not live-ready`。

## 证据

- [V2 完整交易路径 HTML](../artifacts/hype_4h_ma7_rsi6_v2_cross_reentry_trade_path_2026-08-07.html)
- [V2 机器摘要](../artifacts/hype_4h_ma7_rsi6_v2_cross_reentry_summary_2026-08-07.json)
- [V2 场景指标](../artifacts/hype_4h_ma7_rsi6_v2_cross_reentry_metrics_2026-08-07.csv)
- [V2 指标与目标状态](../artifacts/hype_4h_ma7_rsi6_v2_cross_reentry_indicators_2026-08-07.csv)
- [V2 逐笔交易](../artifacts/hype_4h_ma7_rsi6_v2_cross_reentry_trades_2026-08-07.csv)
- [V2 权益路径](../artifacts/hype_4h_ma7_rsi6_v2_cross_reentry_path_2026-08-07.csv)
- [V2 多空贡献](../artifacts/hype_4h_ma7_rsi6_v2_cross_reentry_trade_components_2026-08-07.csv)
- [V2 相位审计](../artifacts/hype_4h_ma7_rsi6_v2_cross_reentry_phase_2026-08-07.csv)
- [V2 滚动 90 日](../artifacts/hype_4h_ma7_rsi6_v2_cross_reentry_rolling_90d_2026-08-07.csv)
- [V2 近期切片](../artifacts/hype_4h_ma7_rsi6_v2_cross_reentry_recent_2026-08-07.csv)
- [复现脚本](../scripts/research_hype_4h_ma7_rsi6_asymmetric_reversal.py)
- [HTML 渲染脚本](../scripts/render_hype_4h_ma7_rsi6_trade_path.py)
