# Binance-1D-MA7-Taker-Flow-Meta-Label

- Alias：`BIN-1D-MA7-TFML`
- 市场/周期：Binance USD-M perpetual；UTC `1d` maturity event + 原生 `5m` aggressor/taker flow
- 资产：BTC/ETH/BNB/SOL/TRX development；HYPE 在 P1 与 post-cutoff 五资产 P2 前完全锁定
- 机制：复用冻结 LMML 事件，但直接回归成本后 `z_8bps`；以 taker buy/sell quote imbalance、flow persistence/absorption 与 leave-target-out market flow 严格超越相同 Ridge 的 price-only control。
- 当前状态：`explore / diagnostic-only / not promoted / not live-ready`；P0 native-flow 有效，P0E 有 generator-source provenance blocker；P1/P1E 另因 held-source aggregate isolation 违反合同而失效，历史正/负增量均撤回
- 边界：不是 BPML 的 threshold 放宽，也不是 DSML taker ratio 字段修复；使用原生 5m kline taker-buy volume，并把经济 target 从 binary label 改为 expected utility。

## 入口

- [主账](binance-1d-ma7-tfml-core-ledger.md)
- [决策记录](decision-log.md)
- [P0/P1 合同](specs/binance-1d-ma7-tfml-p0-p1-contract-2026-08-10.md)
- [P0/P1 复核更正](diagnostics/binance-1d-ma7-tfml-p1-development-2026-08-10.md)
- [P0E/P1E Fresh-Universe 合同](specs/binance-1d-ma7-tfml-p0e-p1e-universe-expansion-contract-2026-08-10.md)
- [P0E/P1E Fresh-Universe 复核更正](diagnostics/binance-1d-ma7-tfml-p1e-fresh-universe-2026-08-10.md)
- [产物索引](artifacts/README.md)
- [BPML 失败诊断](../1d-ma7-basis-premium-meta-label/diagnostics/binance-1d-ma7-bpml-p1-development-2026-08-10.md)
