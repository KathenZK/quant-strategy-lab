# HYPE-EMA-TB-V39 Trailing Stop 诊断

日期：2026-07-09

## 结论

针对“V39 当前止损太宽，是否可以用 trailing stop 改善收益、回撤、胜率”的问题，本轮在 V39 上测试了 53 组 trailing stop 参数。结论是：**不建议把 trailing stop 合入 V39**。

核心原因：

1. **没有任何 trailing 变体能同时改善 full 收益、full maxDD、胜率**。
2. **没有任何 trailing 变体能同时改善最近 90 天收益、maxDD、胜率**。
3. Trailing stop 会把 V39 的主收益来源（打满 `5ATR` 的趋势单）提前截断，交易数和 trailing 退出次数明显上升，复利被大幅削弱。

因此，V39 当前仍保留原始 `5ATR TP / 7ATR hard stop / ADX delayed exit / mfe>=1.5 后关闭指标退出` 结构。Trailing stop 只记录为失败诊断，不登记 V39.2，也不作为 live/paper-live 候选。

## 数据与执行口径

- 市场：Binance USD-M 永续，`HYPE/USDT:USDT`，`15m`。
- 数据：本地数据湖 `2025-05-30 10:30 UTC` 至 `2026-07-08 05:30 UTC`，38765 根已闭合 K 线。
- 数据质量：缺口 0、重复 0、关键 OHLCV/null 0、raw/normalized 对齐最大差异 0。
- Funding：Binance funding，对齐到持仓 bar。
- 成本：`0.00085`/fill，含手续费与 4 bps adverse slippage 合并口径；含 funding。
- 执行：K0 close 信号、K2 open 入场、entry ATR 取 K1 已完成值。
- Trailing 时序：MFE 与 trailing stop 价格只在 15m bar 收盘后更新，更新后的 trailing stop 从下一根 bar 起生效。
- Trailing 成交：若下一根 open 已穿越 trailing stop，按 open 成交；否则按 trailing stop 价成交。TP/SL/trailing 同 bar 触发时按 stop-first 保守口径。

## V39 基线

| 指标 | 数值 |
| --- | ---: |
| full收益 | +9969.45% |
| full maxDD | -23.46% |
| Sharpe | 4.81 |
| 交易数 | 107 |
| 胜率 | 79.44% |
| 退出结构 | TP 83 / SL 14 / indicator 10 |
| 最近90天收益 | +217.53% |
| 最近90天 maxDD | -21.90% |
| 最近90天胜率 | 77.14% |

## 参数扫描

扫描形式：`trail_aX_dY` 表示 MFE 达到 `X ATR` 后启用 trailing，trailing stop = 当前最高有利浮盈 - `Y ATR`。例如 `trail_a40_d35` 表示 MFE 达到 `4.0ATR` 后，按 `3.5ATR` 回撤距离跟踪。

本轮覆盖：

- activation：`0.0 / 1.0 / 1.5 / 2.0 / 2.5 / 3.0 / 3.5 / 4.0 ATR`
- trail distance：`1.0 / 1.5 / 2.0 / 2.5 / 3.0 / 3.5 / 4.0 ATR`
- 过窄的 `activation=0` 且 `distance<=2` 等价于把初始止损直接收紧到 1-2ATR，未纳入主扫描。

## 最接近可用的变体

| 变体 | full收益 | full maxDD | Sharpe | 胜率 | 交易数 | 90d收益 | 90d maxDD | 判断 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| V39 | +9969.45% | -23.46% | 4.81 | 79.44% | 107 | +217.53% | -21.90% | 基线 |
| `trail_a40_d35` | +7510.79% | -28.92% | 4.70 | 82.76% | 116 | +184.86% | -21.90% | 胜率提高，但收益少 2458.66pp、full 回撤恶化 5.46pp |
| `trail_a40_d30` | +5563.54% | -28.10% | 4.38 | 81.20% | 117 | +187.66% | -21.90% | 90d 回撤持平，但收益显著下降 |
| `trail_a40_d25` | +4933.51% | -27.23% | 4.30 | 81.03% | 116 | +178.99% | -21.90% | 同样截断趋势，full 近乎腰斩 |
| `trail_a30_d25` | +2670.07% | -22.58% | 3.85 | 84.03% | 144 | +83.04% | -20.47% | full/90d 回撤和胜率改善，但收益塌陷，不可用 |
| `trail_a30_d30` | +2875.09% | -22.58% | 3.89 | 73.53% | 136 | +97.57% | -22.00% | full maxDD 改善 0.88pp，但收益损失超 7000pp |

`trail_a40_d35` 是 full 收益最高的 trailing 变体，但仍明显劣于 V39：full 收益 `+9969.45% -> +7510.79%`，maxDD `-23.46% -> -28.92%`，Sharpe `4.81 -> 4.70`。它只是把胜率从 `79.44%` 提到 `82.76%`，但这是用大量提前出场换来的，不是更稳版本。

`trail_a30_d25` 是少数能改善 full maxDD 的变体：`-23.46% -> -22.58%`，胜率 `79.44% -> 84.03%`；但 full 收益从 `+9969.45%` 掉到 `+2670.07%`，Sharpe 从 `4.81` 掉到 `3.85`，最近 90 天收益也从 `+217.53%` 掉到 `+83.04%`。它证明 trailing 可以降低部分亏损，但代价远高于收益。

## 为什么 trailing 不适合 V39

V39 的收益结构依赖少数强趋势单打满 `5ATR`。Trailing stop 一旦在 `1.0~3.0ATR` 附近开始跟踪，会把大量趋势单提前截断：

- `trail_a10_d35`：trailing exits 88 次，full 仅 `+672.91%`。
- `trail_a20_d35`：trailing exits 66 次，full `+1557.76%`。
- `trail_a30_d20`：trailing exits 78 次，胜率升到 `84.56%`，但 full 仍只有 `+4095.52%`。
- `trail_a40_d35`：已经很晚启动，仍有 21 次 trailing exits，full 收益低于 V39 约 2458.66pp。

这说明问题不是 trailing 参数还没调准，而是 V39 机制本身需要容忍较宽波动，让趋势单完成 `5ATR` TP。把“止损太宽”的问题用通用 trailing stop 解决，会把盈利尾部一起砍掉。

## 判断

1. **不合入 V39**：没有任何 trailing stop 配置同时改善收益、回撤、胜率。
2. **不登记 V39.2**：本轮没有发现比 V39 更稳健的新版本。
3. **若要处理“止损太宽”问题，优先方向不是 trailing stop**：更可能需要按入场质量、ADX/ATR regime、仓位 cap 或独立保护规则做更窄范围的诊断，而不是对所有仓位加通用 trailing。
4. **live-readiness 不变**：本轮只是样本内诊断；V39 仍是观察候选，未 promotion、未 live-ready。

## 复现与证据

- 脚本：`../scripts/research_hype_ema_tb_v39_trailing_stop.py`
- 汇总 JSON：`../artifacts/hype_ema_tb_v39_trailing_stop_2026-07-09.json`
- 逐笔 CSV：`../artifacts/hype_ema_tb_v39_trailing_stop_2026-07-09_trades.csv`
- 权益曲线 CSV：`../artifacts/hype_ema_tb_v39_trailing_stop_2026-07-09_equity.csv`
