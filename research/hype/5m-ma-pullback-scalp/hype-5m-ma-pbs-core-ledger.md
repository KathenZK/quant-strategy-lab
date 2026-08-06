# HYPE-5M-MA-Pullback-Scalp Core Ledger

## Family Identity

- 完整家族名：`HYPE-5M-MA-Pullback-Scalp`
- 别名：`HYPE-5M-MA-PBS`
- 市场：Binance USD-M `HYPEUSDT` 永续，`5m`
- 机制：均线趋势中的回踩恢复入场，快速止损/止盈/超时退出。
- 碰撞警告：不是 `HYPE-1M-MA-Pullback-Scalp`，也不是 `HYPE-5M-Pullback-Trail`。

## Current State

- 当前版本：无登记版本；观察行 `HYPE_5M_MA_PBS_R03072__base` 与邻域 `__nb_0370`。
- 当前状态：`explore / not promoted / not live-ready`。
- 结论：首轮可执行搜索与邻域稳健性已完成，但证据尚不足以登记或启动 promotion review。
- 下一门：扩展 OOS、压力与执行审计，明确观察行是否值得冻结。

## Version Rules

- 1m 参数放大或 PBTR 参数复用不构成本家族版本。
- 只有完整 spec、可复现证据与用户明确登记才创建 `Vx`。

## Version Table

| Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| `R03072 base/nb_0370 observation` | `explore / not promoted / not live-ready` | 5m MA pullback scalp 及邻域 | 指标见搜索与稳健性报告 | [搜索](diagnostics/hype-5m-ma-pullback-scalp-search-2026-06-26.md) · [邻域](diagnostics/hype-5m-ma-pullback-scalp-robustness-2026-06-26.md) | 保留观察，不登记 |

## Shared Assumptions

- 数据：Binance `HYPEUSDT` 闭合 `5m` K；窗口待冻结。
- 成本：fee `0.001/fill`、slippage `4 bps/fill`，funding 与额外冲击需审计。
- 执行：closed-bar-only、下一根可执行价格；stop/timeout 顺序需显式定义。
- 仓位：单仓；高换手风险预算待定义。

## Evidence Map

- 诊断：[首轮搜索](diagnostics/hype-5m-ma-pullback-scalp-search-2026-06-26.md) · [邻域稳健性](diagnostics/hype-5m-ma-pullback-scalp-robustness-2026-06-26.md)
- 决策：[decision-log.md](decision-log.md)
- 脚本：[scripts/](scripts/)
- 产物：[artifacts/README.md](artifacts/README.md)
