# Binance-15M-Multi-Indicator-Intraday-Transfer Core Ledger

## Family Identity

- 完整家族名：`Binance-15M-Multi-Indicator-Intraday-Transfer`
- 别名：`BIN-15M-MII-XFER`
- 市场：Binance USD-M `BTCUSDT`、`ETHUSDT` 永续，`15m`
- 机制：将 HYPE MII 的 RSI/MACD/ATR/RVOL/fixed-bracket 机制做受约束分资产缩放。
- 边界：不继承 HYPE 版本号；BTC/ETH 参数不能命名为 HYPE 版本。

## Current State

- 当前版本：无登记版本；仅有 BTC/ETH 迁移观察。
- 当前状态：`explore / not promoted / not live-ready`。
- 结论：BTC K+1/K+2 同正但收益低且仅 31 笔；ETH K+1 为正、K+2 `-11.11%`，延迟稳健性失败。
- 下一门：需要标准数据湖、资金费、更多 OOS 与跨延迟稳健候选；当前没有 promotion 目标。

## Version Rules

- 参数搜索标签是诊断观察，不是 `Vx`。
- 只有冻结独立 BTC/ETH 规则、证据和用户明确登记后才创建版本。

## Version Table

| Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| `BTC constrained observation` | `explore / not promoted / not live-ready` | RSI9 + ATR/RVOL + fixed bracket | K+1 `+2.99%`、K+2 `+2.24%`、31 笔 | [迁移诊断](diagnostics/binance-15m-mii-btc-eth-constrained-search-2026-06-30.md) | 样本与收益不足 |
| `ETH constrained observation` | `explore / not promoted / not live-ready` | 偏空 RSI9 + ATR/RVOL + fixed bracket | K+1 `+6.63%`；K+2 `-11.11%` | [迁移诊断](diagnostics/binance-15m-mii-btc-eth-constrained-search-2026-06-30.md) | 延迟门失败 |

## Shared Assumptions

- 数据：Binance futures kline API，`2025-05-30T10:30Z` 至 `2026-06-26T04:00Z`。
- 成本：fee `0.001/fill`、slippage `4 bps/fill`，round-trip `0.28%`；未计 funding。
- 执行：闭合 K 信号，K+1 主口径、K+2 延迟压力，固定 bracket。
- 仓位：单仓；指标与参数按资产独立。

## Evidence Map

- 诊断：[BTC/ETH 受约束搜索](diagnostics/binance-15m-mii-btc-eth-constrained-search-2026-06-30.md)
- 决策：[decision-log.md](decision-log.md)
- 脚本：[scripts/](scripts/)
- 产物：[artifacts/](artifacts/)
