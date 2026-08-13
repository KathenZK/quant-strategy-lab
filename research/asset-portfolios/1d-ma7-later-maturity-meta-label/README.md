# Binance-1D-MA7-Later-Maturity-Meta-Label

- Alias：`BIN-1D-MA7-LMML`
- 市场/周期：Binance USD-M perpetual，完整 UTC `1d` 决策，`1h` 路径与因果上下文
- 资产：训练 `BTC/ETH/BNB/SOL/TRX`；`HYPE` 只允许在模型与阈值锁定后作一次性 exposed-target transfer 诊断
- 机制：soft MA7 raw cross 后沿用 HYPE V6 的非对称 buffer/slope 五日成熟规则，以成本后短持有 probe 结果作 meta-label；跨资产 pooled 模型只筛选机会，不修改 V6 core 状态。
- 当前状态：P1 `HARD-GATE-FAILED / explore / not promoted / not live-ready`；无 frozen model，HYPE 未解锁
- 边界：不是已失败的 `BIN-1D-MA7-RSI6-DAPML` 标签微调，也不是 `HYPE-1D-MA7-ABT-V7`；CTLS 事后标签不得进入训练、特征或阈值。

## 入口

- [主账](binance-1d-ma7-lmml-core-ledger.md)
- [决策记录](decision-log.md)
- [P0/P1 非 HYPE 数据与模型合同](specs/binance-1d-ma7-lmml-p0-p1-contract-2026-08-10.md)
- [P1 非 HYPE development 失败诊断](diagnostics/binance-1d-ma7-lmml-p1-development-2026-08-10.md)
- [产物索引](artifacts/README.md)
- [关联 HYPE V6 漏趋势诊断](../../hype/1d-ma7-asymmetric-body-trend/diagnostics/hype-1d-ma7-v6-missed-trend-attribution-2026-08-10.md)
