# HYPE-1D-Multi-Horizon-EMA-Forecast Decision Log

## 2026-07-14

日线保留四组 EMA 与原权重，因 HYPE 历史不足以支持 intraday 滚动校准，改用经典 EWMAC 固定 scalar `5.30 / 3.75 / 2.65 / 1.87`。`0.10` 缓冲基线在仅 153 根有效日 K 上净收益 `+11.17%`，但大幅落后同期买入持有且样本不足，保留为未编号 `explore / not promoted / not live-ready` 观察；证据见 [基线回测](notes/hype-1d-mhef-classic-ewmac-backtest-2026-07-14.md)。
