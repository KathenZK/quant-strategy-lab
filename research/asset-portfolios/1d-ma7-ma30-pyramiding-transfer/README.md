# Binance-1D-MA7-MA30-Pyramiding-Transfer

- Alias：`BIN-1D-MA-PT-XFER`
- 市场/周期：Binance USD-M perpetual，`BTCUSDT` / `ETHUSDT`，UTC `1d`
- 机制：把 `HYPE-1D-Pyramiding-Trend` MA7/MA30 纯收益 observation 原参数、原执行账本直接迁移到 BTC/ETH，不在目标资产调参。
- 当前状态：`explore / not promoted / not live-ready`

## 边界

本目录是跨资产迁移诊断，不是 BTC 或 ETH 的已登记单资产策略，也不改变来源 `HYPE-1D-Pyramiding-Trend` 的状态。

## 入口

- 主账：[binance-1d-ma-pt-xfer-core-ledger.md](binance-1d-ma-pt-xfer-core-ledger.md)
- 决策记录：[decision-log.md](decision-log.md)
- 冻结契约：[binance-1d-ma7-ma30-pyramiding-transfer-contract-2026-07-30.md](specs/binance-1d-ma7-ma30-pyramiding-transfer-contract-2026-07-30.md)
- 迁移报告：[binance-1d-ma7-ma30-pyramiding-transfer-2026-07-30.md](diagnostics/binance-1d-ma7-ma30-pyramiding-transfer-2026-07-30.md)
- 研究脚本：[scripts/README.md](scripts/README.md)
- 产物说明：[artifacts/README.md](artifacts/README.md)
