# TradFi-1D-Multi-Asset-Futures-TSMOM

- Alias：`TF-1D-FUT-TSMOM`
- 市场：股票指数、美国国债、G10 外汇和商品连续期货，日线/月末调仓
- 机制：固定多速度 TSMOM，以及独立的 MOP 2012 `12M/1M` 论文原式观察
- 状态：`explore / diagnostic-only / not promoted / not live-ready`

本家族把黄金单标的固定规则扩展为传统四大资产类别期货组合。它不是 Binance
`BIN-1D-TSMOM-VT` 的新版本，也不是 EWMAC 代理复现；不继承加密资产池、成本或结论。

## 入口

- [核心主账](tf-1d-fut-tsmom-core-ledger.md)
- [决策日志](decision-log.md)
- [冻结契约](specs/tf-1d-fut-tsmom-p0-contract-2026-08-18.md)
- [论文原式契约](specs/tf-1d-fut-tsmom-paper-exact-p1-contract-2026-08-19.md)
- [研究结论](diagnostics/tf-1d-fut-tsmom-research-conclusion-2026-08-18.md)
- [论文原式复刻报告](diagnostics/tf-1d-fut-tsmom-paper-exact-p1-2026-08-19.md)
- [Lab 事实源与交接清单](lab-handoff-2026-08-19.md)
- [脚本](scripts/README.md)
- [产物](artifacts/README.md)
