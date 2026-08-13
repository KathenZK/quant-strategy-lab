# Binance-1D-MA7-Basis-Premium-Meta-Label

- Alias：`BIN-1D-MA7-BPML`
- 市场/周期：Binance USD-M perpetual；UTC `1d` maturity event + 原生 `1h` premium/mark/index context
- 资产：BTC/ETH/BNB/SOL/TRX development；HYPE 在模型与阈值冻结前完全锁定
- 机制：复用冻结 LMML 经济事件与标签，以 premium-index 和 mark/index basis 判断趋势延续是否拥挤；主 full 必须严格超越原 LMML price control。
- 当前状态：`HARD-GATE-FAILED / explore / diagnostic-only / not promoted / not live-ready`；14 日 P0R 容量通过，但 full `19/20` folds 无合格 inner choice，唯一 OOF trade 亏损且无 price-control 增量
- 边界：不是 DSML 的缺值修复、不是 DSTO daily full-anchor，也不修改 MA7 root、maturity、probe outcome 或 V6 core。

## 入口

- [主账](binance-1d-ma7-bpml-core-ledger.md)
- [决策记录](decision-log.md)
- [P0/P1 合同](specs/binance-1d-ma7-bpml-p0-p1-contract-2026-08-10.md)
- [P0R 14 日 Basis 修订合同](specs/binance-1d-ma7-bpml-p0r-14d-basis-contract-2026-08-10.md)
- [P0/P1 失败诊断](diagnostics/binance-1d-ma7-bpml-p1-development-2026-08-10.md)
- [产物索引](artifacts/README.md)
- [LMML 失败诊断](../1d-ma7-later-maturity-meta-label/diagnostics/binance-1d-ma7-lmml-p1-development-2026-08-10.md)
- [DSTO OI + Funding 失败诊断](../1d-derivatives-structure-trend-opportunity/diagnostics/binance-1d-dsto-p1-oi-funding-development-2026-08-10.md)
