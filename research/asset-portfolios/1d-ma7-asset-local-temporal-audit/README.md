# Binance-1D-MA7-Asset-Local-Temporal-Audit

- Alias：`BIN-1D-MA7-ALTA`
- 市场/周期：Binance USD-M perpetual；UTC `1d` MA7 maturity events
- 资产：BTC/ETH/BNB/SOL/TRX/XRP/DOGE/ADA/LINK/LTC/DOT/AVAX/UNI/BCH/ETC/XLM/ATOM/VET/NEAR/AAVE/FIL
- 机制：在全新 post-cutoff 时间窗上先检验 `take_all` 的无条件经济性，再以无网格、单资产 `Ridge(alpha=1000)+train q80` 作固定对照。
- 当前状态：`HARD-GATE-FAILED / explore / not promoted / not live-ready`
- 边界：不是 QUML P2、不是第三组历史资产 holdout、不是 pooled selector；HYPE 完全锁定。
- 结论：未见时间窗 `take_all` 与固定 asset-local policy 均为负，按合同关闭已揭示数据上的同 substrate 搜索；这证明无条件 edge 为负，不等于所有未来独立信息均被证伪。

入口：

- [Core ledger](binance-1d-ma7-alta-core-ledger.md)
- [决策记录](decision-log.md)
- [P0/P1 合同](specs/binance-1d-ma7-alta-p0-p1-contract-2026-08-10.md)
- [P1 失败诊断](diagnostics/binance-1d-ma7-alta-p1-temporal-audit-2026-08-10.md)
- [产物索引](artifacts/README.md)
