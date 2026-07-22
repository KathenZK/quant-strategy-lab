# BTC 15m 趋势延续长历史搜索诊断（2026-07-20）

## 结论

本轮找到一个值得冻结观察、但不能登记或晋升的研究候选：`lvcb-913f4ff89386`。它不是 Keltner 的继续调参，而是“低波动压缩 → 顺 EMA 趋势做 Donchian 突破 → ATR 保护 + 定时退出”的 `15m` long-only 延续机制。

主状态维持 `explore / not promoted / not live-ready`。最关键的限制不是回测收益，而是 `2024-01-01` 之后的数据已被事件研究和候选审查使用，不能再称 untouched OOS；新的 prospective 证据只能从 `2026-07-20 07:30 UTC` 之后开始。

## 数据与质量

- 市场：Binance USD-M Futures perpetual
- Symbol / timeframe：`BTCUSDT` / `15m`
- UTC 区间：`2020-01-01 00:00` 至 `2026-07-20 07:30`（右开）
- K 线：`229,662` 根；缺口、重复、关键空值、OHLC 约束异常均为 `0`
- Funding：`7,177` 条；最大间隔 `8h`；DQ blocker `0`
- raw / normalized：关键列逐列一致
- 权威证据：[长历史数据质量报告](../artifacts/btc_binance_15m_long_data_quality_latest.json)

## 为什么转向这个机制

全历史固定持有事件研究显示，普通 Donchian、一般 EMA reclaim 与 Keltner 类高频突破多数无法覆盖 `28 bps` 往返成本。唯一形成清晰结构的事件是：

- `ATR96 / close` 在过去 `32` bars 内曾低于 trailing `90d q20`
- `EMA96 > EMA384` 且慢线向上
- 收盘突破 prior Donchian96 high
- 从下一根开盘持有 `192` bars

该事件在非重叠抽样中有 `313` 次，成本代理后平均 `+14.60 bps`，`7` 个自然年中 `6` 年均值为正。它只用于发现机制，不是策略收益证据；详见[事件结构摘要](../artifacts/btc_15m_trend_structure_summary_2026-07-20.json)。

并行的普通 Donchian/Chandelier、Bollinger-Keltner squeeze 和 breakout-retest/reclaim 探索分别没有开发门禁通过项。最终保留的是更低频、带绝对波动上限的压缩突破，而不是这些失败模板。

## 冻结研究候选

`strategy_id = lvcb-913f4ff89386`

### 信号

1. `ATR96 / close <= 0.0035`。
2. 当前 bar 之前 `16` bars 内，至少一根的 `ATR96 / close` 低于其 trailing `90d q40`；分位阈值只使用更早数据。
3. `EMA96 > EMA384`。
4. `EMA384 > EMA384.shift(16)`。
5. 当前收盘价突破此前 `96` bars 的最高价。
6. 仅做多；信号在 bar close 确认，下一根 bar open 入场。

### 退出与成本

- 初始止损：`entry_fill - 4.0 * ATR96(signal bar)`。
- 止损从入场 bar 立即生效；若开盘穿越止损，按开盘价退出。
- 最长持有：`192` bars；到期在 bar open 退出。
- 每次成交 fee `0.001`，每次 adverse slippage `4 bps`。
- Funding 按审计后的官方事件逐笔计入。
- 单仓、`1.0x` equity allocation，不叠仓。

## 冻结搜索与历史结果

开发选择区间为 `2020-2024`；`2024-2026-07-20` 标记为 reused diagnostic。机制发现和最终候选筛选都看过复用区间，因此所有数字都是全历史研究证据，不是 untouched OOS。

| 区间 | 收益 | MDD | Trades | PF | Sharpe |
| --- | ---: | ---: | ---: | ---: | ---: |
| Train `2020-2021` | `+30.96%` | `-13.68%` | `34` | `2.03` | `1.07` |
| Validation `2022-2023` | `+29.30%` | `-10.26%` | `56` | `1.64` | `1.04` |
| Reused diagnostic `2024-2026-07-20` | `+54.55%` | `-14.23%` | `133` | `1.47` | `1.17` |
| Train，双倍 fee/slippage | `+18.31%` | `-18.15%` | `34` | `1.54` | `0.69` |
| Validation，双倍 fee/slippage | `+7.30%` | `-14.65%` | `58` | `1.17` | `0.33` |
| Reused diagnostic，双倍 fee/slippage | `+6.29%` | `-26.30%` | `135` | `1.09` | `0.23` |

冻结搜索共评估 `184` 个 signal/exit 组合：`66` 个通过开发与双倍成本门禁，`16` 个同时满足复用期标准成本正收益、双倍成本正收益及最近 `1y > -5%`。完整机器结果见[搜索摘要](../artifacts/btc_15m_lvcb_summary_2026-07-20.json)和[候选表](../artifacts/btc_15m_lvcb_candidates_2026-07-20.csv)。

### 自然年与近期切片

| 窗口 | 收益 | Trades | PF |
| --- | ---: | ---: | ---: |
| `2020` | `+27.02%` | `31` | `2.03` |
| `2021` | `+3.11%` | `3` | `2.02` |
| `2022` | `-2.12%` | `26` | `0.94` |
| `2023` | `+32.10%` | `30` | `2.46` |
| `2024` | `+55.48%` | `53` | `2.06` |
| `2025` | `-4.80%` | `53` | `0.91` |
| `2026 YTD` | `+4.41%` | `27` | `1.27` |
| 最近 `1d` | `-0.92%` | `1` | `0.00` |
| 最近 `7d` | `-2.20%` | `2` | `0.00` |
| 最近 `1m` | `-6.44%` | `6` | `0.00` |
| 最近 `3m` | `-9.32%` | `16` | `0.25` |
| 最近 `6m` | `-2.85%` | `23` | `0.85` |
| 最近 `1y` | `-2.43%` | `47` | `0.94` |

近期切片明确恶化，不能用 `2024` 的强收益掩盖。当前逐笔序列已连续 `6` 笔非正收益，这也是不晋升的直接原因之一。

## 稳健性与基准

- `13` 个连续 `180d` 窗口中 `10` 个正收益，正收益比例 `76.9%`；见[滚动窗口](../artifacts/btc_15m_lvcb_rolling_windows_2026-07-20.csv)。
- `223` 笔全历史交易做 `10,000` 次、block length `5` 的 circular trade bootstrap：终值为正概率 `98.94%`，MDD 超过 `25%` 的概率 `14.22%`，终值收益 `p05 = +30.96%`；审计通过，但它不能替代 bar-path Monte Carlo 或 prospective OOS。见[bootstrap 审计](../artifacts/btc_15m_lvcb_candidate_audit_2026-07-20.json)。
- 复用诊断期 BTC buy-and-hold 为 `+50.71% / MDD -53.85%`；候选为 `+54.55% / MDD -14.23%`。Train 中 buy-and-hold `+543.94%`，候选绝对收益显著落后，但风险暴露也远低于长期满仓。
- Short-only 在复用期仅 `+0.31%`，both 为 `+55.04%` 且 MDD 更差；short arm 在开发期失败，因此冻结候选保持 long-only。
- 逐笔交易见[交易明细](../artifacts/btc_15m_lvcb_selected_trades_2026-07-20.csv)。

## 决策与后续门槛

本轮可以说“找到一个结构清晰、长历史后成本为正的 `15m` 趋势研究候选”，但不能说“找到已验证可上线的策略”。

维持 `explore / not promoted / not live-ready`，不登记 `V1`。参数从 `2026-07-20 07:30 UTC` 起冻结；下一次决策至少需要：

1. 新增 `>= 6m` 或 `>= 30` 笔 prospective 交易，且不得据此继续调参后再冒充 OOS。
2. 补齐 BTC `1m` 数据并完成多 offset 的 `15m` 相位审计。
3. 完成 CPCV、bar-path / execution Monte Carlo。
4. 审计 runner 可复现的 pending-entry、entry-bar stop、gap stop、funding、重启恢复、缺 bar fail-closed 与 kill switch。
5. 重点观察绝对 `ATR96/close <= 0.0035` 门槛是否发生长期尺度漂移，以及近期亏损是否继续扩大。

## 复现

- [长历史刷新与 DQ](../scripts/refresh_and_audit_btc_15m_long_data.py)
- [事件结构分析](../scripts/analyze_btc_15m_trend_structure.py)
- [候选搜索与冻结](../scripts/research_btc_15m_low_vol_compression_breakout.py)
- [trade-block bootstrap](../scripts/audit_btc_15m_lvcb_candidate.py)
