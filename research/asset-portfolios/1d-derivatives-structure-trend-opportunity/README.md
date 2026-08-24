# Binance-1D-Derivatives-Structure-Trend-Opportunity

- Alias：`BIN-1D-DSTO`
- 市场/周期：Binance USD-M perpetual；每日 `00:00 UTC` 因果锚点，固定 5 日经济结果
- 资产：BTC/ETH/BNB/SOL/TRX development；HYPE 完全锁定
- 机制：每日 anchor 预测 long/flat/short，并以 price-only control 检验 derivatives 增量；原 OI/positioning/taker 全字段路线因官方源质量失败，精确 OI + funding 的 P0R 容量通过。
- 当前状态：`explore / diagnostic-only / not promoted / not live-ready`；历史 P1 因 aggregate isolation 违反合同而失效，不能解释 OI/funding 增量。
- 边界：不是 MA7 event selector；从官方 metrics 的共同覆盖期建立高容量每日锚点，并直接检验 derivatives structure 相对 price-only control 的增量。

## 入口

- [主账](binance-1d-dsto-core-ledger.md)
- [决策记录](decision-log.md)
- [P0/P1 数据与模型合同](specs/binance-1d-dsto-p0-p1-contract-2026-08-10.md)
- [P0R OI + Funding 修订合同](specs/binance-1d-dsto-p0r-oi-funding-contract-2026-08-10.md)
- [P0 官方源质量诊断](diagnostics/binance-1d-dsto-p0-source-quality-2026-08-10.md)
- [P1 OI + Funding 复核更正](diagnostics/binance-1d-dsto-p1-oi-funding-development-2026-08-10.md)
- [产物索引](artifacts/README.md)
- [前驱 DSML 容量失败诊断](../1d-ma7-derivatives-structure-meta-label/diagnostics/binance-1d-ma7-dsml-p0-capacity-2026-08-10.md)
