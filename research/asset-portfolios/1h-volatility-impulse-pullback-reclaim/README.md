# Binance-1H-Volatility-Impulse-Pullback-Reclaim

- Alias：`BIN-1H-VIPR`
- 市场/周期：Binance USD-M perpetual；原生闭合 `1h` root 与下一小时开盘执行
- 资产：BTC/ETH/BNB/SOL/TRX development + locked holdout；HYPE 在本家族中完全锁定
- 机制：波动归一化 Donchian impulse/breakout 建 root，等待明确的 pullback 后跨回 breakout level，再以固定 ATR bracket/timeout 交易。
- 当前状态：`HARD-GATE-FAILED / explore / not promoted / not live-ready`
- 边界：不是 `BIN-1H-PIC` 的 4h impulse campaign，也不是失败 `BIN-1H-MA7-RHT` 的 root/模型变体；无 ML、无 daily MA7、无 asset-specific 参数。
- 结论：八配置 development 的五资产与全部 180 日块均为负，locked holdout 未揭示；停止同一局部价格机制。

## 入口

- [主账](binance-1h-vipr-core-ledger.md)
- [决策记录](decision-log.md)
- [P0/P1 预冻结合同](specs/binance-1h-vipr-p0-p1-contract-2026-08-10.md)
- [P1 development 失败诊断](diagnostics/binance-1h-vipr-p1-development-2026-08-10.md)
- [产物索引](artifacts/README.md)
- [前驱 RHT 失败诊断](../1h-ma7-root-hazard-timing/diagnostics/binance-1h-ma7-rht-p1-development-2026-08-10.md)
