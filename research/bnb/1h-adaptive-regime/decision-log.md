# BNB-1H-Adaptive-Regime Decision Log

## 2026-07-03：建立独立研究家族

- 使用 Binance USD-M Futures `BNBUSDT` perpetual `1h` 最近两年闭合 K。
- 最近三个月严格锁定为 OOS；搜索和排序只读取更早的 train/validation。
- 硬目标保持原义：年化权益倍率 `>=10.0x`、胜率 `>=50%`、最大回撤严格小于 `20%`。
- Binance 成本固定为 `0.001` fee/fill、`4 bps` adverse slippage/fill，并计入历史资金费。
- 在 locked OOS 与 live-executable 审计完成前保持 `not promoted / not live-ready`。

## 2026-07-05：完整搜索 NO-GO，转向独立 15m 家族

- 完成 `1,000,000` 组随机配置、`500,000` 组邻域请求与 `200` 个保留组合；prefit hard-gate 命中为 `0`。
- 唯一预冻结 primary 为 `bb_break + stoch_reversal`，prefit 年化倍率 `6.36x`、胜率 `77.05%`、最大回撤 `-19.75%`，仍未达到 `10x`。
- locked OOS 年化倍率 `0.28x`、胜率 `42.86%`、最大回撤 `-31.90%`；full 也因 `-31.90%` 回撤失败。
- 结论：`BNB-1H-Adaptive-Regime` 为 `NO-GO / not promoted / not live-ready`，不登记版本。
- 后续单独建立 `BNB-15M-Adaptive-Regime`，不在 1h 失效 primary 上继续 OOS 后调参。
