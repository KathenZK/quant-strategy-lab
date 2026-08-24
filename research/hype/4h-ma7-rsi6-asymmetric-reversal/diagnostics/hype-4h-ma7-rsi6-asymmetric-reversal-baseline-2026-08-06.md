# HYPE 4H MA7-RSI6 非对称反转基准（2026-08-06）

## 结论

用户指定规则在原生 UTC `4h` K 上成本后全期 `+113.10%`，优于同期 buy-and-hold 的 `+57.13%`；最后 `120d` 为 `+30.96%`，但低于同期持有的 `+44.99%`。

该正收益不能解释为稳健候选：将 `4h` K 起点平移 `1h/2h` 后分别为 `-51.65% / -78.77%`，四相位只有两个盈利；12 个滚动 90 日窗口只有 6 个盈利；原生相位 MDD `-57.76%`，且无止损的固定数量空仓在逆向行情中使有效杠杆最高漂至 `2.15x`，`2h` 相位更达到 `6.96x`。因此保持 `explore / not promoted / not live-ready`，不登记版本。

## 冻结规则

使用 SMA7 和 TradingView/Wilder RSI6：

1. Flat：`close[t] > SMA7[t]`，下一根 `4h` open 做多。
2. Long：`close[t] < SMA7[t]`，且最近三根（含当前）至少一根 RSI6 严格 `>70`，下一根 open 平多并反手做空。
3. Short：当前 RSI6 严格 `<30`，下一根 open 只平空并进入 flat。
4. 其他情况维持原状态；空头不因重新站上 MA7 退出，平空后不在同一 open 反多。

完整定义见[冻结合同](../specs/hype-4h-ma7-rsi6-asymmetric-reversal-contract-2026-08-06.md)。

## 数据与执行

- Binance USD-M `HYPEUSDT` perpetual。
- 标准数据湖闭合 `1h`：`2025-05-30 10:00` 至 `2026-08-06 07:00 UTC`；原生相位形成 `2,596` 根完整 `4h`。
- 每根 `4h` 严格由四根连续 `1h` 聚合；数据质量 blocker 为 `0`。
- 收盘信号最早在下一根 `4h` open 成交，不使用盘中未来信息。
- 单仓、非加仓；成交后约 `1x`，数量持有至下一次成交。
- 手续费 `0.001/fill`、基准不利滑点 `4 bps/fill`、压力 `8 bps/fill`；actual Binance funding。
- 直接反手按平旧仓和开新仓两次 fill；terminal open 强制平仓。

## 全期结果

| 场景 | 收益 | MDD | Sharpe | PF | 交易 / fills |
| --- | ---: | ---: | ---: | ---: | ---: |
| Base | `+113.10%` | `-57.76%` | `1.14` | `1.36` | `81 / 162` |
| `8 bps/fill` | `+99.75%` | `-58.37%` | `1.08` | `1.33` | `81 / 162` |
| 额外延迟一根 `4h` | `+110.08%` | `-61.17%` | `1.13` | `1.36` | `81 / 162` |
| Gross：fee/slippage 为 `0` | `+167.27%` | `-55.90%` | `1.33` | `1.49` | `81 / 162` |
| Buy-and-hold | `+57.13%` | `-70.54%` | `0.89` | — | `1 / 2` |

- 相对持有的历史超额为 `+55.98` 个百分点。
- 胜率 `60.49%`；多头/空头交易 `41 / 40`。
- 曝险 `90.91%`，直接多翻空 `40` 次，成交总数 `162`。
- 累计交易成本为初始权益的 `32.47%`；cost stress 和额外延迟仍盈利。
- 无 stop 时原生相位有效杠杆最高约 `2.15x`，不是稳定维持 `1x` 风险。

## 最后 120 日

| 场景 | 收益 | MDD | Sharpe | PF |
| --- | ---: | ---: | ---: | ---: |
| Base | `+30.96%` | `-38.58%` | `1.35` | `1.62` |
| `8 bps/fill` | `+28.56%` | `-38.63%` | `1.28` | `1.57` |
| 额外延迟一根 `4h` | `+38.58%` | `-34.46%` | `1.54` | `1.79` |
| Gross：fee/slippage 为 `0` | `+39.74%` | `-38.40%` | `1.56` | `1.82` |
| Buy-and-hold | `+44.99%` | `-34.25%` | `1.74` | — |

最后 `120d` base 虽盈利，但落后持有 `14.02` 个百分点，MDD 也略差；不是近期超额证据。

## 多空贡献

| Side | 交易数 | 胜率 | PF | 中位持仓 | 净 PnL（初始权益单位） |
| --- | ---: | ---: | ---: | ---: | ---: |
| Long | `41` | `56.10%` | `1.58` | `124h` | `+0.880` |
| Short | `40` | `65.00%` | `1.16` | `52h` | `+0.251` |

两边均为正，但主要利润来自多头；空头 PF 只略高于 1。

## 相位与时间稳定性

| 4H 起点 | 收益 | MDD | PF | 最大有效杠杆 |
| --- | ---: | ---: | ---: | ---: |
| `0h` | `+113.10%` | `-57.76%` | `1.36` | `2.15x` |
| `1h` | `-51.65%` | `-76.12%` | `0.74` | `3.20x` |
| `2h` | `-78.77%` | `-90.13%` | `0.63` | `6.96x` |
| `3h` | `+177.22%` | `-63.59%` | `1.29` | `2.12x` |

这是当前最严重的问题：同一市场、同一规则，只移动 K 线边界就从翻倍变为大亏。原生相位的收益不能视为稳定结构。

- 12 个 rolling `90d` 窗口只有 `6` 个盈利。
- 最差窗口 `-31.28%`，最好 `+101.22%`。
- 最近 `1d/7d/1m/3m/6m/1y` 为 `+0.42% / +3.86% / +10.14% / +57.84% / +10.21% / +85.67%`；这些是完整路径切片，不是独立 OOS。

## 相比纯 MA7 反手为何改善

- 交易数从 `557` 降为 `81`，显著减少 MA7 附近来回打脸。
- 多头不会在每次普通跌破时退出，只有最近出现 RSI6 overbought 才允许反手。
- 空头在 RSI6 oversold 后退出到 flat，避免始终持有方向仓位。
- 中位多头/空头持仓延长到 `124h / 52h`，更接近趋势 campaign。

但过滤条件与 UTC K 线边界高度耦合，改善尚未跨相位复现。

## 决策

- 保留为有趣的历史观察，不登记、不 promotion。
- 在讨论参数优化前，必须先解决相位不稳定和无保护空仓的风险；不能只围绕原生 UTC 相位挑阈值。
- 无 hard stop、phase `2h` 的 `-90.13%` MDD 与潜在强平风险均阻止任何 runner 推进。

## 证据

- [完整交易路径 HTML](../artifacts/hype_4h_ma7_rsi6_asymmetric_reversal_trade_path_2026-08-06.html)
- [机器摘要](../artifacts/hype_4h_ma7_rsi6_asymmetric_reversal_summary_2026-08-06.json)
- [场景指标](../artifacts/hype_4h_ma7_rsi6_asymmetric_reversal_metrics_2026-08-06.csv)
- [指标与目标状态](../artifacts/hype_4h_ma7_rsi6_asymmetric_reversal_indicators_2026-08-06.csv)
- [逐笔交易](../artifacts/hype_4h_ma7_rsi6_asymmetric_reversal_trades_2026-08-06.csv)
- [权益路径](../artifacts/hype_4h_ma7_rsi6_asymmetric_reversal_path_2026-08-06.csv)
- [多空贡献](../artifacts/hype_4h_ma7_rsi6_asymmetric_reversal_trade_components_2026-08-06.csv)
- [相位审计](../artifacts/hype_4h_ma7_rsi6_asymmetric_reversal_phase_2026-08-06.csv)
- [滚动 90 日](../artifacts/hype_4h_ma7_rsi6_asymmetric_reversal_rolling_90d_2026-08-06.csv)
- [近期切片](../artifacts/hype_4h_ma7_rsi6_asymmetric_reversal_recent_2026-08-06.csv)
- [复现脚本](../scripts/research_hype_4h_ma7_rsi6_asymmetric_reversal.py)
- [HTML 渲染脚本](../scripts/render_hype_4h_ma7_rsi6_trade_path.py)
