# HYPE-1D-Pyramiding-Trend

- Alias：`HYPE-1D-PT`
- 市场/周期：Binance USD-M `HYPEUSDT` perpetual，UTC `1d`
- 机制：日线趋势突破/动量入场，初始 `1x`，仅在浮盈后按 ATR 台阶加到最多 `3x`，以 channel/trailing/profit-lock 退出。
- 当前状态：`explore / not promoted / not live-ready`

## 边界

本家族是独立的日线离散 campaign 与浮盈加仓研究，不是连续仓位的 `HYPE-1D-MHEF`，也不继承任何 15m/1h HYPE 家族的版本、参数或结论。

## 入口

- 主账：[hype-1d-pt-core-ledger.md](hype-1d-pt-core-ledger.md)
- 决策记录：[decision-log.md](decision-log.md)
- 冻结搜索契约：[hype-1d-pt-search-contract-2026-07-22.md](specs/hype-1d-pt-search-contract-2026-07-22.md)
- 广搜结论：[hype-1d-pt-hard-target-search-2026-07-22.md](diagnostics/hype-1d-pt-hard-target-search-2026-07-22.md)
- 研究脚本：[scripts/README.md](scripts/README.md)
- 产物说明：[artifacts/README.md](artifacts/README.md)
