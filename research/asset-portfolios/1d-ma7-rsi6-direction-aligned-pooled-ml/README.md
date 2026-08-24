# Binance-1D-MA7-RSI6-Direction-Aligned-Pooled-ML

- Alias：`BIN-1D-MA7-RSI6-DAPML`
- 市场：Binance USD-M Futures perpetual
- 资产：`BTCUSDT / ETHUSDT / BNBUSDT / SOLUSDT / TRXUSDT`
- 周期：完整 UTC `1d`；`1h` 只解析 stop path
- 机制：严格 SMA7 穿越产生候选，把 K 线、MA7 与 RSI6 转为相对候选方向的统一特征，再用跨资产 pooled Logistic-EV / LightGBM 判断事件质量。
- 边界：独立于单资产 `BTC-1D-MA7-RSI6-LGBM`；不继承其版本或 promotion 证据，只继承已证伪教训与未揭示 validation 边界。
- 当前状态：P1 `HARD-GATE-FAILED / explore / not promoted / not live-ready`

## 入口

- [主账](binance-1d-ma7-rsi6-dapml-core-ledger.md)
- [决策记录](decision-log.md)
- [P0 数据与方向对齐特征合同](specs/binance-1d-ma7-rsi6-dapml-p0-data-feature-contract-2026-08-10.md)
- [P0 数据与事件容量审计](diagnostics/binance-1d-ma7-rsi6-dapml-p0-data-capacity-2026-08-10.md)
- [P1 pooled development 合同](specs/binance-1d-ma7-rsi6-dapml-p1-pooled-development-contract-2026-08-10.md)
- [P1 pooled development 失败诊断](diagnostics/binance-1d-ma7-rsi6-dapml-p1-pooled-development-2026-08-10.md)
- [产物索引](artifacts/README.md)
