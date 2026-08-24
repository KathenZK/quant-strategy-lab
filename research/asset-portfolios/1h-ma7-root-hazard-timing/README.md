# Binance-1H-MA7-Root-Hazard-Timing

- Alias：`BIN-1H-MA7-RHT`
- 市场/周期：Binance USD-M perpetual；完整 UTC `1d` soft MA7 cross 建 root，闭合 `1h` 逐时择时
- 资产：BTC/ETH/BNB/SOL/TRX development；HYPE 在本合同中完全锁定
- 机制：raw cross 后最多 120 小时生成 causal landmark，pooled Logistic 通过 first-hit 选择一次 `0.25x` probe 入场；退出为日线 MA7 recross 或入场后 120 小时。
- 当前状态：`HARD-GATE-FAILED / explore / not promoted / not live-ready`
- 边界：materially new successor，不是失败 LMML 的 P2；不使用旧 maturity、CTLS、HYPE label、asset id 或事后最优小时。
- 结论：逐小时 first-hit OOF 经济性、覆盖、排序、bootstrap、立即入场配对和压力门全部失败；关闭跨资产共享 daily MA7 root prior，HYPE 未读取。

## 入口

- [主账](binance-1h-ma7-rht-core-ledger.md)
- [决策记录](decision-log.md)
- [P0/P1 非 HYPE hazard 合同](specs/binance-1h-ma7-rht-p0-p1-contract-2026-08-10.md)
- [P1 development 失败诊断](diagnostics/binance-1h-ma7-rht-p1-development-2026-08-10.md)
- [产物索引](artifacts/README.md)
- [直接前驱 LMML 失败诊断](../1d-ma7-later-maturity-meta-label/diagnostics/binance-1d-ma7-lmml-p1-development-2026-08-10.md)
