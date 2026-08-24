# Binance-1D-Monthly-Cross-Sectional-Momentum-LS3 Core Ledger

## Family Identity

- Full name：`Binance-1D-Monthly-Cross-Sectional-Momentum-LS3`
- Alias：`BIN-1D-MCSM-LS3`
- 市场：Binance USD-M USDT 永续；UTC 日 K 由 `15m` Vision 月档 + 主力 `date=*` 补洞聚合
- 周期：每月 1 日开盘换仓，持有至下月 1 日开盘
- 机制：上一日历月收益横截面，等权做多最强 3、做空最弱 3，总名义 200%
- 防串线：不是 [`BIN-1D-TSMOM-VT`](../1d-multi-asset-tsmom-vol-target/README.md) 时序动量，也不是 [`BIN-1H-CSLGBM`](../1h-cross-sectional-lightgbm-selector/README.md)

## Current State

- 当前主状态：`explore / not promoted / not live-ready`
- 当前观察：`2026-08-18` 字面规则与扩展诊断，无版本号、未登记
- 下一门禁：不推进。Top10、short 波动约束与组合风险缩放均已在全历史揭示；若重开须预注册独立机制与新前瞻证据，不得把本轮胜出项当作 clean OOS

## Version Rules

- 当前没有注册版本；本次只固定用户给定的 3+3 月度规则作诊断。
- 未来只有用户明确要求登记时才创建 `V1`；改 N、改形成期或改流动性过滤都是新观察。

## Version Table

| Observation | Status | Role | Key Frozen Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| `2026-08-18 diagnostic` | `explore` | UTC 月频 3 多 3 空字面规则 | 全上市净收益 `-99.96%` / CAGR `-71.44%` / Sharpe `-0.154`；`ADV≥1000万` 动量 `-99.93%`；同窗 BTC `+586%` | [契约](specs/binance-1d-mcsm-ls3-diagnostic-contract-2026-08-18.md) · [诊断](diagnostics/binance-1d-mcsm-ls3-diagnostic-2026-08-18.md) | 不登记、不晋升 |
| `2026-08-18 extensions` | `explore / diagnostic-only` | 广度、形成期、尾部裁剪、风险缩放与 short 约束 | ADV Top10/Bottom10 `+142.15%` 但 MDD `-94.41%`；20% 目标波动版 `+67.87%` / MDD `-41.19%`；short 约束版历史胜出但 MDD `-85.08%`、年度不稳 | [扩展诊断](diagnostics/binance-1d-mcsm-extensions-2026-08-18.md) | 全部已揭示；不登记、不晋升 |

## Shared Assumptions

- 上月最后可见收盘 / 再上月最后可见收盘定义形成期；换仓填在 UTC 月 1 日开盘。
- 多头三腿各 `+1/3`、空头三腿各 `-1/3`；Binance 默认每边 `0.001+4bps`，资金费按日 as-of。
- 评估窗 `2020-03-01`–`2026-06-30`；`2026-07` 起无全市场月档。
- 线性 PnL，不模拟强平。

## Evidence Map

- [诊断契约](specs/binance-1d-mcsm-ls3-diagnostic-contract-2026-08-18.md)
- [诊断报告](diagnostics/binance-1d-mcsm-ls3-diagnostic-2026-08-18.md)
- [扩展诊断](diagnostics/binance-1d-mcsm-extensions-2026-08-18.md)
- [Artifacts](artifacts/README.md)
- [Scripts](scripts/README.md)

## What Not To Put Here

- 不粘贴换仓清单、日路径或分年全表；见诊断与 artifacts。
