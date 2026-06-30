# HYPE-15M-MII Core Ledger

Family：`HYPE-15M-Multi-Indicator-Intraday`

Alias：`HYPE-15M-MII`

Created：2026-06-30

## 边界

`HYPE-15M-MII` 是 Binance HYPEUSDT 永续 `15m` broad multi-indicator intraday 研究线，独立于 `HYPE-EMA-Crossover`、`HYPE-EMA-Trend-Breakout` 和 `HYPE-Candle-Count-Reversal`。

本台账中的 `V1`、`V1base` 只在 `HYPE-15M-MII` 家族内有效。裸版本号不具有策略身份。

## 当前状态

- 当前主观察基线：`HYPE-15M-MII-V1.1`。
- 当前实现名：`clean_rsi7_40_60_atrmin75_rvol1_h10_rsi14b0_tp120_sl360_hold16_x2`。
- 当前状态：`diagnostic observation only / not live-ready`。
- 家族实盘判断：`NO-GO`。
- 原因：仍缺资金费核算、盘口级 stop-market 证据、真实成交滑点、生产 runner、重启恢复、交易所对账、missing-bar fail-closed 和 kill switch。

## 数据与成本口径

- Exchange：Binance。
- Market：USD-M perpetual。
- Symbol：HYPEUSDT。
- Timeframe：`15m`。
- 数据：标准 raw/normalized 数据湖，`2025-05-30T10:30:00+00:00` 到 `2026-06-26T04:00:00+00:00`。
- 数据质量：quality gate `True`；gap、duplicate、critical null、invalid OHLC、open bar、raw/normalized mismatch 均为 `0`。
- 成本：手续费 `0.1000%`/fill，滑点 `0.0400%`/fill，round-trip `0.2800%`。
- 资金费：未计入。
- 执行：闭合 K 信号，下一根 open 入场；K+2 用作成交延迟压力测试；单仓不重叠；stop-first；timeout-open。

## 版本规则

| 版本 | 说明 |
| --- | --- |
| `HYPE-15M-MII-V1` | 首个冻结研究基线，来自早期最佳综合策略；修复不可执行时序后完整 gate `0/62`，实盘审计 `NO-GO`。 |
| `HYPE-15M-MII-V1base` | 当前主观察基线，按用户指定登记为 `sl360` 高收益诊断表达；只用于后续复现、审计和小额观察讨论，不是 promotion。 |
| `HYPE-15M-MII-V1.1` | `V1base` 的干净参数登记版，只保留实际生效项；策略行为与 `V1base` 相同，不是 promotion。此命名 supersede 早前 `V1.1 diagnostic lead` 的临时口径。 |

## 版本台账

| Version | Status | Core idea | Evidence | Decision |
| --- | --- | --- | --- | --- |
| `HYPE-15M-MII-V1` | diagnostic baseline / not live-ready | `RSI(7)` 上穿 `30` 做多、下穿 `60` 做空；MACD 方向过滤；ATR96 pct `0.60%-2.80%`；`TP=0.90%`、`SL=2.80%`、`hold=16`、`1.5x` | `canonical-specs/hype-15m-mii-v1-baseline-spec.md`；`ablations/hype-15m-mii-v1-full-parameter-ablation-2026-06-29.md`；`live-specs/hype-15m-mii-v1-live-feasibility-2026-06-29.md` | 可执行口径年化 `18.66%`、回撤 `-31.84%`、Last90 年化 `-41.44%`；`NO-GO` |
| `HYPE-15M-MII-V1base` | diagnostic observation / not live-ready | `RSI(7)` 上穿 `40` 做多、下穿 `60` 做空；MACD 方向过滤；`ATR96 pct >= 0.75%`；`min_rvol96=1.0`；`TP=1.20%`、`SL=3.60%`、`hold=16`、`2x` | `research-notes/hype-15m-mii-relaxed-dd-high-return-selection-2026-06-30.md`；补算 K+2 延迟压力 | K+1 年化高、Last90 强，但 K+2 回撤扩大到 `-36.28%`；保留为主观察基线，不提升为 candidate/paper-live/dry-run/handoff/live |
| `HYPE-15M-MII-V1.1` | clean diagnostic expression / not live-ready | 去掉未启用的 `1h confirm`、`RSI14 band`、ADX、H4、ret、churn、cooldown 等表达噪音，只保留生效项 | `research-notes/hype-15m-mii-v1-1-window-backtest-2026-06-30.md`；`research-notes/hype-15m-mii-v1-1-trade-paths-2026-06-30.md`；`research-notes/hype-15m-mii-v1-1-dynamic-take-profit-2026-06-30.md`；`research-notes/hype-15m-mii-v1-1-btc-eth-cross-asset-2026-06-30.md` | 行为等同 `V1base`；最近 1 周无交易，K+1 最近 1 月总收益 `34.40%`，全样本总收益 `309.54%`；动态止盈 `0/264` 超过 baseline 形状；BTC/ETH 跨资产诊断未证明可迁移；仍为 `NO-GO` |

## HYPE-15M-MII-V1base 规格

- Signal：`RSI(7)` 上穿 `40` 做多，下穿 `60` 做空。
- Filters：`MACD(12,26,9)` 方向过滤；`ATR96 pct >= 0.75%`；`min_rvol96=1.0`；无 `1h confirm`；无 `RSI14 band`。
- Exit：`TP=1.20%`；`SL=3.60%`；最长 `16` 根 `15m` K。
- Exposure：`2x` 权益暴露。
- Execution：K+1 open 入场；K+2 为延迟压力测试；stop-first；timeout-open；单仓不重叠。

## HYPE-15M-MII-V1.1 参数

`HYPE-15M-MII-V1.1` 与 `V1base` 行为相同，只保留实际生效参数：

- Signal：`RSI(7)` 上穿 `40` 做多，下穿 `60` 做空。
- Filter：`side=both`；`MACD(12,26,9)` 方向过滤，`min_dir_macd=0.0`；`ATR96 pct` 在 `0.75%-2.80%`；`RVOL96 >= 1.0`。
- Exit：固定 `TP=1.20%`、`SL=3.60%`、最长 `16` 根 `15m` K。
- Exposure：`2x` 权益暴露。
- Execution：K+1 open 入场；K+2 为延迟压力；单仓不重叠；stop-first；timeout-open。
- Cost：手续费 `0.1000%`/fill，滑点 `0.0400%`/fill，round-trip `0.2800%`；资金费未计入。

## V1base 结果

| 入场 | 年化 | 最大回撤 | 胜率 | 交易数 | 笔/天 | PF | Last90 年化 | 最差单笔 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `K+1` | `272.30%` | `-21.12%` | `80.75%` | `187` | `0.477` | `2.158` | `457.15%` | `-7.76%` |
| `K+2` | `96.51%` | `-36.28%` | `78.01%` | `191` | `0.488` | `1.446` | - | `-7.76%` |

K+1 分段：

- First half：年化 `337.24%`、回撤 `-16.89%`、胜率 `80.95%`、PF `2.140`。
- Second half：年化 `217.00%`、回撤 `-14.33%`、胜率 `80.49%`、PF `2.182`。
- Last90：年化 `457.15%`、回撤 `-10.35%`、胜率 `93.55%`、PF `5.696`。

## V1.1 分窗口结果

K+1 主口径：

| 窗口 | 年化 | 总收益 | 最大回撤 | 胜率 | 交易数 | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `最近1周` | `0.00%` | `0.00%` | `0.00%` | `0.00%` | `0` | `0.000` |
| `最近1月` | `3556.96%` | `34.40%` | `-5.32%` | `94.44%` | `18` | `21.980` |
| `最近3月` | `457.15%` | `52.69%` | `-10.35%` | `93.55%` | `31` | `5.696` |
| `最近6月` | `277.45%` | `93.84%` | `-13.76%` | `84.00%` | `75` | `2.526` |
| `最近1年` | `306.80%` | `306.41%` | `-21.12%` | `81.21%` | `165` | `2.480` |
| `全样本` | `272.30%` | `309.54%` | `-21.12%` | `80.75%` | `187` | `2.158` |

K+2 延迟压力：

| 窗口 | 年化 | 总收益 | 最大回撤 | 胜率 | 交易数 | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `最近1周` | `0.00%` | `0.00%` | `0.00%` | `0.00%` | `0` | `0.000` |
| `最近1月` | `747.88%` | `19.19%` | `-8.47%` | `80.00%` | `20` | `2.588` |
| `最近3月` | `257.03%` | `36.83%` | `-9.81%` | `84.85%` | `33` | `2.692` |
| `最近6月` | `83.44%` | `35.30%` | `-14.36%` | `77.63%` | `76` | `1.468` |
| `最近1年` | `91.29%` | `91.21%` | `-36.28%` | `77.38%` | `168` | `1.463` |
| `全样本` | `96.51%` | `106.38%` | `-36.28%` | `78.01%` | `191` | `1.446` |

## V1.1 交易路径图

- HTML：`artifacts/hype_15m_mii_v1_1_trade_paths_2026-06-30.html`
- 逐笔交易：`artifacts/hype_15m_mii_v1_1_trades_2026-06-30.csv`
- 图表内容：每笔交易局部 `15m` K 线、入场/出场连线、`RSI(7)` 与 `40/60` 阈值、`MACD(12,26,9)` 线/signal/histogram。

## V1.1 动态止盈测试

保持 `V1.1` 信号、过滤、`SL=3.60%`、`2x` 权益暴露和成本不变，取消固定 `TP=1.20%`，改为 activation 后 trailing stop：

- 动态 trailing 网格：`264` 个配置，`0` 个同时超过固定 TP baseline 的收益、回撤和胜率形状。
- 固定 TP baseline：K+1 年化 `272.30%`、回撤 `-21.12%`、胜率 `80.75%`；K+2 年化 `96.51%`、回撤 `-36.28%`。
- 动态综合第一 `trail_act150_trail30_sl360_hold16`：K+1 年化 `205.74%`、回撤 `-36.08%`、胜率 `71.35%`；K+2 年化 `135.71%`、回撤 `-39.52%`。
- 动态最高 K+1 年化 `trail_act120_trail30_sl360_hold16`：K+1 年化 `240.67%`、回撤 `-24.88%`；仍弱于 baseline。

结论：`V1.1` 的优势来自短促反转窗口。单纯放开固定 TP 让利润奔跑，会让更多交易从小赢变成回吐或 timeout，不能提升当前观察基线。

## V1.1 BTC/ETH 跨资产诊断

直接把 `HYPE-15M-MII-V1.1` 套到 Binance USD-M `BTCUSDT`、`ETHUSDT` `15m` API 数据，目标窗口与 HYPE 标准数据湖相同（`2025-05-30T10:30:00+00:00` 到 `2026-06-26T04:00:00+00:00`）。该数据来自 Binance futures kline API 直接拉取，不是本仓库标准 raw/normalized 数据湖；只用于 sanity check。

| 资产 | 入场 | 全样本年化 | 全样本总收益 | 最大回撤 | 胜率 | 交易数 | 结论 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `BTCUSDT` | `K+1` | `3.46%` | `3.71%` | `-2.06%` | `100.00%` | `2` | 交易太少，不能说明有效迁移 |
| `BTCUSDT` | `K+2` | `3.46%` | `3.71%` | `-1.56%` | `100.00%` | `2` | 交易太少，不能说明有效迁移 |
| `ETHUSDT` | `K+1` | `-37.95%` | `-40.06%` | `-42.74%` | `41.67%` | `24` | 明显不适配 |
| `ETHUSDT` | `K+2` | `-30.24%` | `-32.04%` | `-33.95%` | `50.00%` | `24` | 明显不适配 |

结论：`V1.1` 的 HYPE 参数没有自然迁移到 BTC/ETH。BTC 结果被极低交易数主导，ETH 结果为负；这强化了“该参数更可能是 HYPE 样本内形状，而非普遍 15m 反转 edge”的判断。

## 已知风险

- K+2 延迟后收益显著下降，回撤扩大到 `-36.28%`，说明入场时点敏感性仍然存在。
- 动态止盈测试没有改善收益/回撤/胜率综合形状；后续若继续研究利润奔跑，应先重新定义趋势过滤或分批止盈，而不是直接替换固定 TP。
- BTC/ETH 跨资产诊断没有证明自然迁移：BTC 只有 `2` 笔交易，ETH 全样本亏损 `-40.06%`（K+1）。
- 最近 1 周无交易；最近 1 月/3 月表现强，但短窗口年化会被样本长度放大。
- 样本来自同一标准数据湖窗口，不是 untouched OOS。
- 资金费未计入；对高换手或持仓跨资金费时段的影响仍需单独审计。
- `2x` 是回测权益暴露倍数，不等同于已审计过的交易所保证金和风控实现。
- 还没有生产 runner、重启恢复、交易所对账、missing-bar fail-closed、kill switch 或真实 stop-market 滑点证据。

## 证据入口

- V1 baseline spec：`canonical-specs/hype-15m-mii-v1-baseline-spec.md`
- V1 full ablation：`ablations/hype-15m-mii-v1-full-parameter-ablation-2026-06-29.md`
- V1 live feasibility：`live-specs/hype-15m-mii-v1-live-feasibility-2026-06-29.md`
- Clean evolution：`research-notes/hype-15m-mii-clean-parameter-evolution-2026-06-29.md`
- Delay-aware selection：`research-notes/hype-15m-mii-delay-aware-selection-2026-06-29.md`
- Relaxed DD high-return selection：`research-notes/hype-15m-mii-relaxed-dd-high-return-selection-2026-06-30.md`
- Fast validation ranking：`research-notes/hype-15m-mii-fast-validation-frequency-ranking-2026-06-30.md`
- Balanced leverage stress：`research-notes/hype-15m-mii-balanced-leverage-stress-2026-06-30.md`
- V1.1 window backtest：`research-notes/hype-15m-mii-v1-1-window-backtest-2026-06-30.md`
- V1.1 trade paths：`research-notes/hype-15m-mii-v1-1-trade-paths-2026-06-30.md`
- V1.1 dynamic take profit：`research-notes/hype-15m-mii-v1-1-dynamic-take-profit-2026-06-30.md`
- V1.1 BTC/ETH cross asset：`research-notes/hype-15m-mii-v1-1-btc-eth-cross-asset-2026-06-30.md`
- Decision log：`decision-log.md`

## 下一步

若继续推进 `V1base`，必须先补齐：

- 资金费回放。
- 盘口级 stop-market / market order 滑点审计。
- K+2/K+3 与更差滑点压力测试。
- 生产 runner 状态机复现。
- 重启恢复、交易所对账、missing-bar fail-closed 和 kill switch。
- 独立 OOS 或滚动窗口复验。
