# HYPE-EMA-TB-V39 K+1 Execution Diagnostic

日期：2026-07-09

## 结论

本轮测试 `HYPE-EMA-TB-V39` 是否可以把当前 K+2 open 入场改成 K+1 open 入场。结论：**不建议把 V39 改成 K+1；当前 V39 K+2 baseline 保持不变**。

K+1 不是理论上不可测，但在当前同窗回测里显著劣于 K+2：

- full 收益：`+9969.45% -> +3256.99%`
- full maxDD：`-23.46% -> -37.14%`
- Sharpe：`4.81 -> 3.76`
- 胜率：`79.44% -> 72.32%`
- 最近 90 天收益：`+217.53% -> +109.24%`
- 最近 90 天 maxDD：`-21.90% -> -25.20%`

因此，K+1 不能作为 V39 的直接替代执行口径，也不登记新版本。

## 数据与执行口径

- 市场：Binance USD-M 永续，`HYPE/USDT:USDT`，`15m`。
- 数据：本地数据湖 `2025-05-30 10:30 UTC` 至 `2026-07-08 05:30 UTC`，38765 根已闭合 K 线。
- 数据质量：缺口 0、重复 0、关键 OHLCV/null 0、raw/normalized 对齐最大差异 0。
- 成本：`0.00085`/fill，含手续费与 4 bps adverse slippage 合并口径；含 funding。
- 信号、入场过滤、sizing、TP/SL、indicator exit、timeout 全部沿用 V39。

本轮只改入场时序：

| 版本 | 信号 | 入场 | entry ATR |
| --- | --- | --- | --- |
| `v39_k2_base` | K0 close | K2 open | K1 已完成 `ATR672` |
| `v39_k1_entry` | K0 close | K1 open | K0 已完成 `ATR672` |

K+1 版本没有使用 K1 或未来 K 的 ATR，因此不是未来函数；它是一个更快但路径不同的执行诊断。

## 汇总对比

| 版本 | full收益 | full maxDD | Sharpe | 交易数 | 胜率 | 90d收益 | 90d maxDD | 90d胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `v39_k2_base` | +9969.45% | -23.46% | 4.81 | 107 | 79.44% | +217.53% | -21.90% | 77.14% |
| `v39_k1_entry` | +3256.99% | -37.14% | 3.76 | 112 | 72.32% | +109.24% | -25.20% | 66.67% |

标准分片：

| 窗口 | K2 收益 | K2 maxDD | K2 笔数 | K1 收益 | K1 maxDD | K1 笔数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1d | +0.00% | +0.00% | 0 | +0.00% | +0.00% | 0 |
| 7d | +9.94% | -14.60% | 3 | +9.64% | -14.60% | 3 |
| 1m | +23.40% | -20.11% | 7 | +22.98% | -20.06% | 7 |
| 3m | +217.53% | -21.90% | 35 | +109.24% | -25.20% | 36 |
| 6m | +1802.57% | -22.58% | 68 | +799.41% | -27.97% | 72 |
| 1y | +11342.95% | -23.08% | 104 | +4701.93% | -27.97% | 109 |
| full | +9969.45% | -23.46% | 107 | +3256.99% | -37.14% | 112 |

## 多空拆分

| 版本 | 多单数 | 多单胜率 | 多单均笔 | 空单数 | 空单胜率 | 空单均笔 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `v39_k2_base` | 83 | 79.52% | +4.81% | 24 | 79.17% | +5.59% |
| `v39_k1_entry` | 86 | 70.93% | +3.50% | 26 | 76.92% | +4.95% |

主要劣化来自多头：K+1 更早入场后，多单胜率从 `79.52%` 降到 `70.93%`，stop_loss 从 10 笔增到 16 笔。空单也略弱，但幅度小于多头。

## 交易路径差异

K+1 不是单纯把 K2 的成交价提前一根。因为入场更早，持仓区间、出场时间和后续信号占用都会改变：

| 项 | 数值 |
| --- | ---: |
| K2 总交易 | 107 |
| K1 总交易 | 112 |
| 同一 `signal_bar + direction` 可对齐交易 | 72 |
| K2-only 交易 | 35 |
| K1-only 交易 | 40 |

在 72 笔可对齐交易中：

- K1 相对 K2 entry price 中位差：`-0.0378%`
- K1 相对 K2 单笔收益差中位：`-0.0075pp`
- K1 相对 K2 单笔收益差均值：`-1.0085pp`
- 4 笔 K2 take_profit 在 K1 中变成 stop_loss
- 3 笔 K2 take_profit 在 K1 中变成 indicator_exit
- 47 笔共同保持 take_profit

这说明 K+1 并不是普遍“更便宜更好”。早一根进入会多吃未确认波动，也会改变持仓占用，导致部分原本 K2 能吃到的趋势段在 K1 路径里变成止损或被其它持仓状态错过。

## 判断

1. **V39 继续使用 K+2 open baseline**：K+1 在 full、90d、6m、1y 上都明显劣于 K2。
2. **K+1 不登记为 V39.2 / V39.1.x**：当前结果没有收益、回撤或胜率优势。
3. **K+1 可以作为 runner 延迟能力的压力参考**：如果实盘 runner 实际能稳定接近 K1 open 成交，也不代表应替换研究口径；至少需要单独设计 K+1 版本并重新通过消融、walk-forward 和 live-executable 审计。
4. **当前 live spec 不变**：`HYPE-EMA-TB-V39` handoff spec 仍保持 K0 close -> skip K1 -> K2 open 入场。

## 复现与证据

- 脚本：[research_hype_ema_tb_v39_k1_execution_diagnostic.py](../scripts/research_hype_ema_tb_v39_k1_execution_diagnostic.py)
- 汇总 JSON：[hype_ema_tb_v39_k1_execution_diagnostic_2026-07-09.json](../artifacts/hype_ema_tb_v39_k1_execution_diagnostic_2026-07-09.json)
- 逐笔 CSV：[hype_ema_tb_v39_k1_execution_diagnostic_2026-07-09_trades.csv](../artifacts/hype_ema_tb_v39_k1_execution_diagnostic_2026-07-09_trades.csv)
- 带 signal_bar 标注逐笔：[hype_ema_tb_v39_k1_execution_diagnostic_2026-07-09_annotated_trades.csv](../artifacts/hype_ema_tb_v39_k1_execution_diagnostic_2026-07-09_annotated_trades.csv)
- 权益曲线 CSV：[hype_ema_tb_v39_k1_execution_diagnostic_2026-07-09_equity.csv](../artifacts/hype_ema_tb_v39_k1_execution_diagnostic_2026-07-09_equity.csv)
