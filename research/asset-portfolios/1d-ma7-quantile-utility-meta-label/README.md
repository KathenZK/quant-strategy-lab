# Binance-1D-MA7-Quantile-Utility-Meta-Label

- Alias：`BIN-1D-MA7-QUML`
- 市场/周期：Binance USD-M perpetual；UTC `1d` V6-style maturity events
- 资产：13 个 legacy training assets；BCH/ETC/XLM/ATOM/VET/NEAR/AAVE/FIL 为 second-fresh outer；HYPE 完全锁定
- 机制：price-only Ridge 直接预测 `z_8bps`，以 train-prediction quantile 替代跨资产不稳定的 absolute threshold，并严格对比原 absolute policy。
- 当前状态：`explore / diagnostic-only / not promoted / not live-ready`；P1 evidence invalidated
- 边界：不是 TFML 的 flow 修补，也不是在已揭示八资产上调 threshold；第二组 fresh outcome 在合同冻结时未读取。
- 结论：P0 通过；P1 因预计算 market aggregates 未排除 held source history 而失效，不能用于 ranking、calibration 或增量归因；不补第三组历史 holdout、不读 HYPE。

入口：

- [Core ledger](binance-1d-ma7-quml-core-ledger.md)
- [决策记录](decision-log.md)
- [P0/P1 合同](specs/binance-1d-ma7-quml-p0-p1-contract-2026-08-10.md)
- [P1 复核更正](diagnostics/binance-1d-ma7-quml-p1-development-2026-08-10.md)
- [产物索引](artifacts/README.md)
