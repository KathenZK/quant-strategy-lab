# HYPE-D15-HTO-V3 冻结研究规格

## 身份与状态

- Family：`HYPE-1D-15M-Hierarchical-Trend-Opportunity`
- Version：`HYPE-D15-HTO-V3`
- Status：`registered / not promoted / not live-ready`
- Market：Binance USD-M Futures `HYPEUSDT`
- Config SHA256：`a11c2a019564e57359fd2cad19c0b8a9dcedece9a28d6443d9c94acead1e6703`

本文件是研究侧冻结规格，不是 runner handoff 或 live spec。V3 已在 prefit 与 locked OOS 门禁失败，不得用于真实下单。

## 数据与时序

- 输入：连续、已收盘的 Binance `15m` OHLCV、quote volume、trade count、VWAP 与资金费事件。
- 日线：UTC 自然日，只有恰好 96 根已收盘 `15m` 才完整；时刻 `t` 只能读取前一完整 UTC 日。
- `15m` 信号：仅在 K 线收盘后计算；订单在下一根 `15m` 开盘成交。
- 单一净仓，不叠加仓位；信号与现有持仓同向时不重复入场。
- OOS：`[2026-04-29 03:00 UTC, 2026-07-29 03:00 UTC)`，冻结后一次性揭示。

## 冻结参数

| 组件 | 参数 | 值 |
| --- | --- | ---: |
| 日线方向 | EMA fast / slow | `40 / 60` |
| 日线方向 | momentum | `15d` |
| 日线方向 | DMI window | `7d` |
| 日线方向 | Donchian state | `10d` |
| 日线方向 | vote | 四项必须同向 |
| 交易方向 | long / short | both |
| `15m` 微趋势 | EMA fast / slow | `24 / 288` |
| `15m` 入场 | prior Donchian | `16` bars |
| `15m` 入场 | breakout buffer | `0.3 * ATR192` |
| `15m` 过滤 | ADX14 | `>=18` |
| `15m` 过滤 | volume / prior 96-bar median | `>=1.0` |
| 初始止损 | ATR multiple | `8.0 * ATR192` |
| 固定止盈 | ATR multiple | `2.5 * ATR192` |
| 追踪启动 / 距离 | ATR multiple | `1.5 / 2.5` |
| 保本启动 | ATR multiple | `4.0` |
| 指标退出 | prior Donchian | `24` bars |
| 冷却 | closed bars | `96` |
| 杠杆 | gross leverage | `2.5x` |
| timeout | - | 无；V1 的 288-bar timeout 经消融 path-equal，V2/V3 删除 |

## 信号

前一完整日的四个方向项分别为：

1. `sign(EMA40 - EMA60)`；
2. `sign(close[t-1d] - close[t-16d])`，即 15 日动量；
3. Wilder `DMI7` 的 `sign(+DI - -DI)`；
4. `Donchian10` 状态：日收盘突破此前 10 日最高为多，跌破此前 10 日最低为空，否则延续最近状态。

只有四项全部为 `+1` 才允许做多，全部为 `-1` 才允许做空。日线状态只控制新开仓方向；冻结 V3 的在途仓位由保护单与 `15m Donchian24` 退出，不因日线翻转直接市价退出。

多头 `15m` 入场要求：日线方向为多、`EMA24 > EMA288`、`ADX14 >= 18`、当前量能不低于此前 96 根中位数，且收盘价高于此前 16 根最高价加 `0.3 * ATR192`。空头完全镜像。

## 撮合与风险

- 下一根开盘以不利 `4 bps` 成交；每次成交手续费为 filled notional 的 `0.001`。
- 进场后立即建立初始 stop 与 take-profit；同一根 K 同时穿越时按 stop-first。
- 若开盘越过 stop，按开盘价再计不利滑点；take-profit 的有利跳空仍保守按目标价成交。
- 追踪止损只在当前 K 完整结束后根据该 K 的 favorable extreme 更新，下一根起生效。
- `15m Donchian24` 退出在闭合 K 确认，下一根开盘成交。
- 资金费只按实际持仓跨越的资金费事件、方向和 `2.5x` 名义计入。
- 冷却从平仓后的下一根开始计算 96 根，期间不得新开仓。

## 已知失败

- prefit：年化 `1.838x`、胜率 `60.00%`、MDD `20.98%`、50 笔。
- locked OOS：净收益 `-29.76%`、年化 `0.242x`、胜率 `29.41%`、MDD `36.75%`、17 笔。
- OOS 即使零手续费、零滑点仍为 `-20.72%`。
- 真实 `1m` 聚合 +5/+10 分钟相位分别为 `+6.31% / -8.81%`，MDD `41.00% / 28.57%`。
- 缺少 runner 指标对拍、保护单/拒单状态机、重启恢复、missing-bar fail-closed、kill switch 与线上开平仓对账。

证据：[prefit 稳健性](../diagnostics/hype-d15-hto-v3-prefit-robustness-2026-07-29.md)、[locked OOS](../diagnostics/hype-d15-hto-v3-locked-oos-final-2026-07-29.md)、[主账](../hype-d15-hto-core-ledger.md)。

