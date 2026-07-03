# BNB-1H-Adaptive-Regime Decision Log

## 2026-07-03：建立独立研究家族

- 使用 Binance USD-M Futures `BNBUSDT` perpetual `1h` 最近两年闭合 K。
- 最近三个月严格锁定为 OOS；搜索和排序只读取更早的 train/validation。
- 硬目标保持原义：年化权益倍率 `>=10.0x`、胜率 `>=50%`、最大回撤严格小于 `20%`。
- Binance 成本固定为 `0.001` fee/fill、`4 bps` adverse slippage/fill，并计入历史资金费。
- 在 locked OOS 与 live-executable 审计完成前保持 `not promoted / not live-ready`。
