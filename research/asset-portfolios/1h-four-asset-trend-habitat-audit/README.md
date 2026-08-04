# Binance-1H-Four-Asset-Trend-Habitat-Audit

- Full family name：`Binance-1H-Four-Asset-Trend-Habitat-Audit`（alias：`BIN-1H-FATHA`）
- 市场/标的：Binance USD-M perpetual；`HYPE/BTC/ETH/SOL`。
- 周期：完整 `1h` 价格路径；日频锚点；未来 `3d/7d/14d` 趋势生态。
- 机制：分离“事后是否存在顺滑大趋势”和“事前 `7d/28d` 日周方向是否可识别”，并审计延迟 `4h/12h/24h` 后的剩余空间、MFE/MAE、回吐与成本。
- 当前状态：`explore / diagnostic-only / not promoted / not live-ready`；不产生订单，尚无策略版本。

## 边界

- 这是跨资产 habitat diagnostic，不是多资产策略、selector、TSMOM 或现有 HYPE 策略的变体。
- 四币分别报告，Long/Short 分开；共同窗口负责横向比较，各自全历史只负责长期背景。
- 任何资产在本轮排名领先，都不自动获得进入未来 Trend Campaign Engine 的资格。

## 入口

- 主账：[binance-1h-fatha-core-ledger.md](binance-1h-fatha-core-ledger.md)
- 决策记录：[decision-log.md](decision-log.md)
- 冻结合同：[初始研究合同](specs/binance-1h-fatha-initial-research-contract-2026-08-03.md)
- 复现入口：[scripts/README.md](scripts/README.md)
- 产物说明：[artifacts/README.md](artifacts/README.md)
- 结论报告：[HYPE/BTC/ETH/SOL 趋势生态丈量报告](diagnostics/binance-1h-fatha-trend-ecology-report-2026-08-03.md)
