# Binance-MK7-Multi-Strategy-Account Core Ledger

## Family Identity

- Full family name：`Binance-MK7-Multi-Strategy-Account`
- External alias：`mk7`
- Market：Binance USD-M Futures perpetual
- Symbols：`TRXUSDT / SOLUSDT / HYPEUSDT / ETHUSDT / BTCUSDT / BNBUSDT`
- Timeframes：`1m / 5m / 15m / 30m / 1h / 6h / 12h`
- Mechanism：六币 `1h` adaptive-regime 腿、HYPE K2FQ、HYPE MII 与双槽共享账户。
- Boundary：独立的外部规格复现线，不是六币 `1h` 组合或任一 HYPE 成分家族的新版本。

## Current State

- Current object：外部 `mk7-v8` 独立回测观察值；**未登记为本仓库 promoted 版本**。
- Status：`explore / not promoted / not live-ready`。
- Reproduction：Binance Vision 全窗 `top_lsr` 已补齐并通过 REST 近窗对拍；六币 5/6 计数对齐，SOL `82≠79`、K2FQ `69≠68`、MII `374≠375`。最终 full/main 入选 `747/602`，已接近规格 `743/601`，但逐笔与哈希仍未闭合。
- Latest metrics：full `7,464,949.89x / -18.8964% MDD / 747 trades`；main `28,103.55x / -17.799% / 602 trades`。
- Forward：严格 `2026-07-02T03Z` 至 `2026-07-12T03Z` 10d OOS 为 `+0.01% / -8.99% MDD / 4 trades / 75% closed win / PF 0.97`；截至最新共同闭合时点 `2026-07-13T12Z` 为 `-17.49% / -21.98% MDD / 6 trades / 50% win`，MII 仍为 `0` 笔。该窗口大部分早于外部规格冻结日，不是 pristine OOS。
- Next gate：暂停任何 promotion 讨论，解释 HYPE DI / TRX Stoch 最新两笔高杠杆尾损并继续积累真正 post-freeze forward；同时取得 SOL、K2FQ、MII 冻结逐笔清单与哈希合同。

## Version Rules

- 外部 `mk7-v8` 只作为 observation，不自动取得本仓库 `registered` 身份。
- 若后续要求登记版本，必须冻结全部成分身份、外部数据源、特征公式、双槽状态机、资金规模、成本、funding 与验收交易路径。
- 信号、过滤、外部数据、退出事件顺序、账户仲裁或规模任一变化都需要新 observation 或新版本。

## Version Table

| Version / Observation | Status | Role | Key metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| External `mk7-v8` source claim | `explore / not promoted / not live-ready` | 规格自称冻结结果 | 来源声明：full `9,328,938.86x / -18.90% MDD / 743 trades` | [复现阻塞诊断](diagnostics/mk7-v8-reproduction-blocker-2026-07-12.md) | 仅来源声明 |
| External `mk7-v8` lab independent run 2026-07-13 | `explore / not promoted / not live-ready` | 本仓按规格独立回测；全窗 LSR + 15m MTM | raw 六币 `44/82/74/89/54/62`；K2FQ `69`；MII `374`；入选 full/main `747/602`；full `7,464,949.89x / MDD -18.8964%`；main `28,103.55x` | [回测笔记](notes/mk7-v8-backtest-2026-07-13.md)、[summary](artifacts/mk7_v8_backtest_summary_2026-07-13.json) | 不 promote；残余 SOL/K2FQ/MII 逐笔差异与 phase FAIL 待闭合 |

## Shared Assumptions

- closed-bar、UTC、显式 fee/slippage/funding、无前视。
- 缺失启用序列不得以零值填充；`top_lsr` 仅允许规格 §3.2 单点 fail-open。
- 规格来源数字在逐笔对齐前不构成 promotion 证据。

## Evidence Map

- [家族入口](README.md)
- [决策记录](decision-log.md)
- [`mk7-v8` 复现阻塞诊断](diagnostics/mk7-v8-reproduction-blocker-2026-07-12.md)
- [独立回测笔记 2026-07-13](notes/mk7-v8-backtest-2026-07-13.md)
- [相对本仓 MAE / K2 / MII 的改造与收益来源分析](notes/mk7-v8-relative-to-local-components-analysis-2026-07-13.md)
- [冻结后严格 10d OOS 回测](notes/mk7-v8-oos-10d-2026-07-13.md)
- [回测窗口后 10.875 天 forward 审计](notes/mk7-v8-post-window-forward-audit-2026-07-13.md)
- [回测脚本](scripts/research_mk7_v8_backtest.py)
- [OOS 数据更新脚本](scripts/update_mk7_v8_oos_data.py)
- [严格 10d OOS 回放脚本](scripts/research_mk7_v8_oos_10d.py)
- [OOS 审计脚本](scripts/audit_mk7_v8_post_window_oos_2026_07_13.py)
- [最近 1d/7d/1m/3m/6m/1y 分片](artifacts/mk7_v8_recent_slices_2026-07-13.json)
- [组件与账户反事实分解](artifacts/mk7_v8_relative_component_decomposition_2026-07-13.json)
- [OOS 汇总](artifacts/mk7_v8_post_window_oos_2026-07-13.json)
- [严格 10d OOS 汇总](artifacts/mk7_v8_oos_10d_summary_2026-07-13.json)
- [OOS 数据完整性](artifacts/mk7_v8_oos_data_integrity_2026-07-13.json)
- [数据完整性报告](../../../data/cache/mk7_v8_binance/logs/integrity_report.json)
