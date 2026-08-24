# BTC-1D-Classic-CTA-Trend

- Alias：`BTC-1D-CCTA`
- 市场/周期：Binance USD-M `BTCUSDT` perpetual，UTC `1d`
- 机制：文献 EWMAC 四速统一信号 + 20% 波动率缩放 + BTC 永续成本/资金费执行。
- 当前状态：`explore / not promoted / not live-ready`

## 边界

独立日线家族。不是 [`HYPE-1D-MHEF`](../../hype/1d-multi-horizon-ema-forecast/README.md) 的迁移，也不是已关闭的 [`XA-1D-EWMAC-UT`](../../asset-portfolios/1d-ewmac-universal-trend/README.md) 或传统市场 [`XA-1D-CLASSIC-EWMAC`](../../asset-portfolios/1d-classic-ewmac-replication/README.md)。Alpha 参数取自 Carver 文献，不对 BTC 调参。

## 入口

- 主账：[btc-1d-ccta-core-ledger.md](btc-1d-ccta-core-ledger.md)
- 决策记录：[decision-log.md](decision-log.md)
- 文献契约：[specs/btc-1d-ccta-literature-baseline-2026-08-17.md](specs/btc-1d-ccta-literature-baseline-2026-08-17.md)
- 基线诊断：[diagnostics/btc-1d-ccta-classic-cta-backtest-2026-08-17.md](diagnostics/btc-1d-ccta-classic-cta-backtest-2026-08-17.md)
- 脚本：[scripts/README.md](scripts/README.md)
- 产物：[artifacts/README.md](artifacts/README.md)
