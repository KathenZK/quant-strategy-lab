# Binance-1D-MA7-Derivatives-Structure-Meta-Label

- Alias：`BIN-1D-MA7-DSML`
- 市场/周期：Binance USD-M perpetual；完整 UTC `1d` maturity event，`5m/1h` derivatives structure context
- 资产：BTC/ETH/BNB/SOL/TRX development；HYPE 完全锁定
- 机制：复用已冻结 LMML 经济事件与标签，只新增 Binance Vision open interest、top-trader/global positioning 和 taker long/short flow；严格 OOF 判断独立信息是否能区分真漏趋势与噪声。
- 当前状态：`HARD-GATE-FAILED / explore / not promoted / not live-ready`
- 边界：不是 LMML 的本地价格特征续调，也不使用 VIPR holdout；不得读取 HYPE metrics、label 或路径。
- 结论：官方 metrics 覆盖使冻结事件最多只剩 967 个，P0 四项容量门均不可达；未下载语料、未运行 P1。

## 入口

- [主账](binance-1d-ma7-dsml-core-ledger.md)
- [决策记录](decision-log.md)
- [P0/P1 数据与模型合同](specs/binance-1d-ma7-dsml-p0-p1-contract-2026-08-10.md)
- [P0 官方 archive 容量失败诊断](diagnostics/binance-1d-ma7-dsml-p0-capacity-2026-08-10.md)
- [产物索引](artifacts/README.md)
- [直接前驱 VIPR 失败诊断](../1h-volatility-impulse-pullback-reclaim/diagnostics/binance-1h-vipr-p1-development-2026-08-10.md)
