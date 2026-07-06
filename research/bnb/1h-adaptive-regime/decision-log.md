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

## 2026-07-06：1h 趋势/反转 rerun 仍未达标

- 按用户要求在 Binance USD-M Futures `BNBUSDT` perpetual `1h` 上再做一次宽搜索，覆盖趋势、反转及二者 ensemble；成本仍为 `0.001` fee/fill、`4 bps` slippage/fill，并计入真实 funding。
- 本轮为 `500,000` random + `250,000` neighbors；first-pass eligible `55,282`、neighbor eligible `117,627`，两阶段 prefit hard-gate 命中均为 `0`。
- 唯一冻结 primary 为 `ENS__BNB_1H_AR_N0559088__BNB_1H_AR_N0610751`，机制为趋势 `keltner_break` + 反转 `cci_reversal`。
- prefit 为 `3.13x annual / -19.44% DD / 91.49% win`，未达到 `10x` 年化倍率；locked OOS 为 `0.31x annual / -37.14% DD / 75.00% win / 4 trades`，同时低于最低 OOS 交易数 `12`。
- full 为 `2.30x annual / -37.14% DD / 91.03% win / 145 trades`；回撤穿越 `20%` 硬边界。
- 结论维持：`BNB-1H-Adaptive-Regime` 仍为 `NO-GO / not promoted / not live-ready`，不登记版本；证据见 `diagnostics/bnb-1h-adaptive-regime-search-2026-07-06-rerun.md`。

## 2026-07-06：用户约束 BNB 1h 最大杠杆不超过 3x

- 用户明确指出 4x 版本回撤过大，后续 BNB `1h` 研究最大只能使用 `3x` 杠杆。
- 对 2026-07-06 rerun primary 做 3x cap 重放：train `2.42x / -14.58% DD / 91.26% win`，validation `2.52x / -13.74% DD / 92.11% win`。
- locked OOS 仍为 `0.44x / -28.30% DD / 75.00% win / 4 trades`；full 为 `1.95x / -28.30% DD / 91.03% win / 145 trades`。
- 结论：3x cap 降低尾部亏损，但仍未通过 `20%` 回撤 hard gate；未来搜索必须硬性约束 `max_leverage <= 3.0`，并继续降低单笔权益风险。证据见 `diagnostics/bnb-1h-ar-rerun-cap3-replay-2026-07-06.md`。
