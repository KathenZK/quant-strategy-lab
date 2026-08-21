# Binance-1D-Monthly-Cross-Sectional-Momentum-Long10

- 别名：`BIN-1D-MCSM-L10`
- 市场：Binance USD-M USDT 永续，UTC `1d`
- 机制：每月 1 日开盘等权做多上一个完整日历月涨幅最高的 10 个合资格合约，持有一个月，不做空
- 当前状态：`explore / diagnostic-only / not promoted / not live-ready`
- 执行裁决：原 `00:00` 开盘路径存在同 bar 成交与不可成交/缺价事件，绩效标记 `PERFORMANCE_INVALIDATED`；仅保留 `ADV Top10 target12` 作为修复后待重跑的风险预算假设

## 边界

这是独立 long-only 家族，不覆盖 [`BIN-1D-MCSM-LS3`](../1d-monthly-cs-momentum-ls3/README.md)。Binance 原生 USD-M 股票/TradFi 永续与加密永续一样按点时上市历史进入合约池，不做资产类别排除；外部现货美股全市场不属于本家族。

## 入口

- 主账：[binance-1d-mcsm-l10-core-ledger.md](binance-1d-mcsm-l10-core-ledger.md)
- 契约：[specs/binance-1d-mcsm-long10-diagnostic-contract-2026-08-18.md](specs/binance-1d-mcsm-long10-diagnostic-contract-2026-08-18.md)
- 诊断：[diagnostics/binance-1d-mcsm-long10-diagnostic-2026-08-18.md](diagnostics/binance-1d-mcsm-long10-diagnostic-2026-08-18.md)
- 宽度诊断：[diagnostics/binance-1d-mcsm-long-breadth-diagnostic-2026-08-19.md](diagnostics/binance-1d-mcsm-long-breadth-diagnostic-2026-08-19.md)
- 风险与缓冲诊断：[diagnostics/binance-1d-mcsm-long10-risk-buffer-diagnostic-2026-08-19.md](diagnostics/binance-1d-mcsm-long10-risk-buffer-diagnostic-2026-08-19.md)
- 正收益与现金缺口诊断：[diagnostics/binance-1d-mcsm-long10-positive-cash-diagnostic-2026-08-19.md](diagnostics/binance-1d-mcsm-long10-positive-cash-diagnostic-2026-08-19.md)
- 可实盘化与执行审计：[diagnostics/binance-1d-mcsm-long10-liveability-audit-2026-08-20.md](diagnostics/binance-1d-mcsm-long10-liveability-audit-2026-08-20.md)
- 赚钱效应与领涨延续诊断：[diagnostics/binance-1d-mcsm-money-effect-continuation-diagnostic-2026-08-20.md](diagnostics/binance-1d-mcsm-money-effect-continuation-diagnostic-2026-08-20.md)
- 赚钱效应冻结合同：[specs/binance-1d-mcsm-money-effect-continuation-diagnostic-contract-2026-08-20.md](specs/binance-1d-mcsm-money-effect-continuation-diagnostic-contract-2026-08-20.md)
- 执行语义修复合同：[specs/binance-1d-mcsm-long10-execution-repair-contract-2026-08-20.md](specs/binance-1d-mcsm-long10-execution-repair-contract-2026-08-20.md)
- 决策：[decision-log.md](decision-log.md)
- 脚本：[scripts/README.md](scripts/README.md)
- 产物：[artifacts/README.md](artifacts/README.md)
