# Binance-1D-Monthly-Cross-Sectional-Momentum-LS3

- 别名：`BIN-1D-MCSM-LS3`
- 市场：Binance USD-M USDT 永续，UTC `1d`（由 `15m` Vision 月档聚合）
- 机制：每月 1 日开盘做多上月最强 3 名、做空最弱 3 名，等权总名义 200%
- 当前状态：`explore / not promoted / not live-ready`

## 边界

不是 [`BIN-1D-TSMOM-VT`](../1d-multi-asset-tsmom-vol-target/README.md) 的时序动量，也不是 [`BIN-1H-CSLGBM`](../1h-cross-sectional-lightgbm-selector/README.md) 的机器学习选币。本线只回答固定 3+3 月度横截面规则。

## 入口

- 主账：[binance-1d-mcsm-ls3-core-ledger.md](binance-1d-mcsm-ls3-core-ledger.md)
- 决策记录：[decision-log.md](decision-log.md)
- 诊断契约：[specs/binance-1d-mcsm-ls3-diagnostic-contract-2026-08-18.md](specs/binance-1d-mcsm-ls3-diagnostic-contract-2026-08-18.md)
- 诊断报告：[diagnostics/binance-1d-mcsm-ls3-diagnostic-2026-08-18.md](diagnostics/binance-1d-mcsm-ls3-diagnostic-2026-08-18.md)
- 扩展诊断：[diagnostics/binance-1d-mcsm-extensions-2026-08-18.md](diagnostics/binance-1d-mcsm-extensions-2026-08-18.md)
- 脚本：[scripts/README.md](scripts/README.md)
- 产物：[artifacts/README.md](artifacts/README.md)
