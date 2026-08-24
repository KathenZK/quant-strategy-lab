# Binance 日线 MA7 平多即反手空诊断（2026-08-06）

## 结论

按[冻结合同](../specs/binance-ma7-long-exit-short-reversal-contract-2026-08-06.md)，只在多头原本触发 `ma7_hysteresis_exit` 时，于同一下一日 open 平多并反手 `1x` 空单。结果是：

| 路线 | R0 原策略 | R1 平多反手空 | 收益变化 | MDD 变化 | 真正新增反手空 | 判定 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| HYPE V1 | `+293.20%` | `+292.64%` | `-0.56pp` | `-0.10pp` | 1 笔，净 PnL `-0.0035` | 失败 |
| BTC 共享参数 | `+112.34%` | `+112.34%` | `0.00pp` | `0.00pp` | 0 笔 | 无增量 |
| ETH 共享参数 | `+161.46%` | `+138.74%` | `-22.73pp` | `-4.07pp` | 1 笔，净 PnL `-0.1851` | 失败 |

`8 bps/fill` 压力下结论不变：HYPE / BTC / ETH 的收益变化分别为 `-0.86 / 0.00 / -22.51pp`。因此不采纳该规则，不修改 HYPE V1 或 BTC/ETH 共享参数身份。

## 对“V1 做空能力差”的修正

HYPE V1 的问题更准确地说是**空头覆盖次数少**，不是已成交空单质量差：

- 原组合全期只有 5 笔空单，但 5 笔全部盈利，合计净 PnL `+0.8810`；原 short-only 历史收益为 `+52.31%`。
- 8 笔多头中 7 笔由 trailing/protective stop 退出，只有 1 笔真正走到 `MA7 - 0.75 ATR7` 的迟滞退出。因此“只在明显跌破 MA7 的平多点反手”天然很少触发。
- 唯一新增 HYPE 反手发生在 `2026-03-31`：`36.840` 开空，6 天后 `36.846` 退出，价格几乎没动，双边成本后该笔 `-0.14%`。最新数据延伸至 `2026-08-06` 后结论仍为 R0 `+286.99%`、R1 `+286.44%`。

这说明原策略确实会漏掉一些没有 short reclaim 的下跌，但本次提出的平多点并没有提供可收割的新增空头优势。

## BTC / ETH 为什么不同

### BTC：原共享参数已自然完成同开盘反手

BTC 有 2 次多头迟滞退出；两次在原策略中同时满足 shared short 的 `pullback_reclaim`，因此 R0 已在同一 open 开空。R1 没有改变任何成交：

- `2024-10-03` 的自然空单随后 protective stop，约 `-5.72%`；
- `2025-03-31` 的自然空单随后 protective stop，约 `-5.17%`。

所以对 BTC 来说，用户提出的行为在相关事件上已经存在，新增规则完全冗余。

### ETH：新增反手抓到的是回调终点，不是下跌起点

ETH 唯一新增反手发生在 `2025-08-03`。此前多单已盈利约 `+30.76%`；`3392.42` 反手做空后价格迅速反弹，在约 41 小时内以 `3678.61` 触发 `1.5 ATR7` protective stop，该笔 `-8.69%`。它把组合收益从 `+161.46%` 降到 `+138.74%`，并把 MDD 从 `-29.29%` 扩大到 `-33.37%`。

## 分期、延迟、近期与相位检查

- 所有真正新增反手都发生在 development / prefit；三条路线的 researcher-exposed holdout 均没有新增反手，故本次没有获得后段支持。
- 额外延迟一天时，HYPE 新增空单偶然转正并令总收益提高 `+1.72pp`，但 ETH 仍下降 `-23.79pp`；方向对一天时点敏感，不能覆盖 base 与压力失败。
- 最近 `1d/7d/1m/3m/6m/1y` 已按数据终点审计，仅用于报告，不参与选择；新增反手都早于最近 3 个月，近期路径未提供增量证据。
- `12h` 相位是非强制检查项：HYPE R0/R1 为 `+28.97%/+15.39%`，BTC 完全相同，ETH 为 `-10.58%/-7.99%`。它不单独否决，但没有提供稳定支持。

## 数据与执行口径

- 市场：Binance USD-M `HYPEUSDT`、`BTCUSDT`、`ETHUSDT` perpetual；UTC `1d`，accepted `1h` raw/normalized 聚合。
- 主横比终点：terminal open `2026-07-30 00:00 UTC`；HYPE `2025-05-31` 起，BTC/ETH accepted 数据 `2024-07-31` 起。
- 成本：手续费 `0.001/fill`，基准滑点 `4 bps/fill`、压力 `8 bps/fill`，实际 event-time funding。
- 执行：日 `t` 闭合后产生退出，`t+1` open 平多并开空，两次 fill 分别计成本；short hard stop / trailing / exit / max-hold 沿原冻结参数。
- 三资产质量审计均为零 blocker；全部历史已揭示，本结果是机制诊断，不是 clean OOS 或 promotion 证据。

## 证据

- [复现脚本](../scripts/audit_ma7_long_exit_short_reversal.py)
- [机器摘要](../artifacts/binance_ma7_long_exit_short_reversal_2026-08-06_summary.json)
- [窗口/压力/延迟指标](../artifacts/binance_ma7_long_exit_short_reversal_2026-08-06_metrics.csv)
- [逐笔交易与入场来源](../artifacts/binance_ma7_long_exit_short_reversal_2026-08-06_trades.csv)
- [近期切片](../artifacts/binance_ma7_long_exit_short_reversal_2026-08-06_recent.csv)
- [相位检查](../artifacts/binance_ma7_long_exit_short_reversal_2026-08-06_phase.csv)
