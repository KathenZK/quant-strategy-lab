# BTC-15M-EMA-Trend-Breakout V40 模板迁移最终诊断

- 日期：`2026-07-17`
- 研究身份：`BTC-15M-EMA-TB-V40-transfer-search`
- 市场：Binance USD-M Futures `BTCUSDT` perpetual，`15m`
- 状态结论：`explore / not promoted / not live-ready`

## 数据、切分与执行合同

数据质量审计覆盖 `2024-07-14T00:00:00Z` 至 `2026-07-17T14:30:00Z` 的 `70,427` 根已闭合 K 线，闭合截止边界为 `2026-07-17T14:45:00Z`。OHLCV 无缺口、重复、关键空值或 raw/normalized 不一致；历史 funding 共 `2,201` 条，最大间隔 `8h`，DQ blocker 为 `0`。详情见[数据质量审计](../artifacts/btc_binance_15m_data_quality_latest.json)。

[冻结切分](../artifacts/btc_15m_v40_frozen_splits_2026-07-17.json)均按 UTC 左闭右开：

- train：`2024-07-17T14:45:00Z` 至 `2025-07-17T14:45:00Z`；
- validation：`2025-07-17T14:45:00Z` 至 `2026-01-17T14:45:00Z`；
- sealed holdout：`2026-01-17T14:45:00Z` 至 `2026-07-17T14:45:00Z`。

搜索阶段未读取 holdout；selection 冻结后只执行第 `1` 次揭示，且没有重新选参。研究固定使用共享内核 `v2`，SHA256 为 `36e5d10c0d281701c46446344dd50af7a7589ec03285be3289e82362e1c2917a`。执行口径为 `fixed 1.0x` allocation、K0 close 确认信号、等待完整 K1、K2 open 入场；使用 `gap-open`，开盘越过 stop 时按更差 open 成交，同 bar TP/SL 按 `stop-first`。成本为每次 fill 手续费 `0.001` 加 adverse slippage `4 bps`；funding 使用已审计的官方历史 funding 逐事件计入，不假设为零。

## 开发集结果

V40 原模板在 BTC 上的基线已经明显亏损：

| 窗口 | 收益 | MDD | 交易数 | 胜率 | PF |
| --- | ---: | ---: | ---: | ---: | ---: |
| train | `-39.264%` | `-42.119%` | `124` | `51.61%` | `0.726` |
| validation | `-13.220%` | `-16.825%` | `59` | `52.54%` | `0.835` |

Stage 1 搜索了 `216` 个 long-only 变体及 `72` 个 bidirectional 扩展，门禁通过数为 `0`。随后按冻结 stepwise 合同执行 Stage 2：第一步 `36` 个单组件变体，第二步 `24` 个在最佳单组件父项上增加不同组件的变体，门禁通过数仍为 `0`。完整搜索见[搜索摘要](../artifacts/btc_15m_v40_search_summary_2026-07-17.json)与[候选指标](../artifacts/btc_15m_v40_candidate_metrics_2026-07-17.csv)。

冻结项只是 `diagnostic_near_miss`，不是 candidate：

| 窗口 | 收益 | MDD | 交易数 | PF |
| --- | ---: | ---: | ---: | ---: |
| train | `-2.466%` | `-12.419%` | `19` | `0.993` |
| validation | `+2.801%` | `-5.277%` | `15` | `1.461` |
| train，2x 成本 | `-10.676%` | `-13.589%` | `19` | `0.701` |
| validation，2x 成本 | `-0.967%` | `-6.644%` | `15` | `1.211` |

其 train 收益、train 样本数、train PF、train/validation 双倍成本收益及参数邻域均未通过；邻域正收益比例为 `0%`。因此[冻结选择](../artifacts/btc_15m_v40_frozen_selection_2026-07-17.json)在揭示前已明确标记为 near-miss，不能因单一 validation 正收益升级为 candidate。

## 一次性 holdout 揭示

冻结 near-miss 在唯一一次 holdout 揭示中收益 `-9.060%`、MDD `-10.603%`、`18` 笔、胜率 `44.44%`、PF `0.613`；双倍成本收益进一步降至 `-12.205%`。BTC buy-and-hold 同窗为 `-33.721%`、MDD `-39.149%`，只说明策略少亏于持有，不构成可交易 alpha：策略仍输给 `0%` 的 cash 基准。

方向独立 flat-reset 消融同样没有盈利腿：long-only `-8.186%`，short-only `-0.952%`。固定参数 development walk-forward 采用 `IS 60d + gap 10d + OOS 30d`，仅 `6/15` 个 OOS fold 为正，正收益比例 `40%`；holdout 仅 `18` 笔，低于 `30` 笔样本门槛。

以数据终点锚定并独立 flat-reset 的近期切片为：`365d -6.513%`、`182d -9.060%`、`90d +0.949%`（`8` 笔）、`30d +0.071%`（`2` 笔）、`7d 0` 笔、`1d 0` 笔。短窗正收益由极少交易构成，不能推翻中长期亏损与样本不足。

一次揭示及 post-reveal gate 见[holdout 摘要](../artifacts/btc_15m_v40_holdout_reveal_2026-07-17.json)；逐笔、净值和 walk-forward 证据分别见[holdout trades](../artifacts/btc_15m_v40_holdout_trades_2026-07-17.csv)、[holdout equity](../artifacts/btc_15m_v40_holdout_equity_2026-07-17.csv)与[development walk-forward](../artifacts/btc_15m_v40_dev_walk_forward_2026-07-17.csv)。

## 最终结论

本次没有找到通过门禁的类似盈利策略。V40 只是从 HYPE 家族借用的搜索模板身份，不是 BTC 家族版本；该机制迁移到 BTC `15m` 后，基线、扩展搜索、成本压力、邻域稳健性、walk-forward 和一次性 holdout 均不足以支持推进。

因此本研究保持 `explore / not promoted / not live-ready`，停止围绕 V40 模板继续扩搜；不得登记 `BTC-15M-EMA-Trend-Breakout-V1`，不得创建 `live spec`，不得接入或修改 quant-runner 配置。若未来重开，必须基于新的机制级假设和新冻结实验，而不是继续放宽本轮门禁或围绕 near-miss 调参。
