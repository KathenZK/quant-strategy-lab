# Binance 1D MA7/MA30 浮盈加仓跨资产直迁契约（2026-07-30）

## 目的与冻结原则

把 `HYPE-1D-Pyramiding-Trend` 在 2026-07-30 搜索所得的 MA7/MA30 纯收益 observation 原样迁移到 `BTCUSDT`、`ETHUSDT`。本次不搜索、不变异、不依据 BTC/ETH 结果选择参数；因此回答的是“来源参数能否直接迁移”，不是“BTC/ETH 上能否重新优化出类似策略”。

## 冻结参数

| 参数 | 值 |
| --- | --- |
| MA | `EMA7 / EMA30` |
| entry | `ma7_reclaim`，双向 |
| slope | `EMA7` 相对前 1 日同向 |
| ATR | Wilder-style `ATR10` |
| initial leverage | `0.5x` |
| add | 浮盈且沿趋势、相对上次加仓价推进 `0.25 ATR10` 后，下一 open 重置目标 `3x` |
| initial stop | `3 ATR10` |
| trailing stop | 最高/最低收盘价回撤 `3 ATR10` |
| profit lock | 有利移动达到入场 `3 ATR10` 后，锁定入场价外 `0.5 ATR10` |
| signal exit | `EMA7/EMA30` 反向交叉 |
| timeout | `20` 日 |
| cooldown | `2` 日 |
| immediate flip | `false` |
| maximum trade target | `3x` |

`confirm_days=2`、`breakout_window=7` 和 `add_increment=1.5` 在本 entry/add 组合中不参与路径，保留仅用于逐字段复刻来源配置，不解释为有效 alpha。

## 数据与窗口

- 数据源：Binance USD-M Futures public API；`BTCUSDT`、`ETHUSDT` perpetual。
- 原始周期：已收盘 `1h` K；只聚合含恰好 24 根连续小时 K 的 UTC 自然日。
- funding：Binance 历史 funding rate，按持仓跨过的 open 区间实际累加。
- 主比较窗口：`2025-05-31 00:00 UTC` 至 `2026-07-30 00:00 UTC` terminal open，与 HYPE full 窗口一致。
- 扩展窗口：当前两年数据能形成的所有完整 UTC 日，终点同为 `2026-07-30 00:00 UTC`。
- 目标资产结果在参数冻结前未参与任何选择；这是横截面 direct-transfer test，不是未来时间 prospective OOS。

## 成本与执行

- 手续费：每次实际成交名义金额的 `0.001`。
- 基础滑点：每次实际成交 `4 bps` 不利滑点成本。
- 压力滑点：`8 bps`。
- 信号在 UTC 日 K 收盘后确认，基础场景下一日 open 成交；另审计 `K+2`。
- 持仓数量只在入场、加仓、减仓、平仓时变化并收费；不做每日免费再平衡。
- stop 只能由前一已收盘日更新；下一日若 open 已穿越 stop，按 open 成交，否则按 stop 成交。
- 同一收盘退出与加仓冲突时退出优先；terminal open 禁止新开或加仓，已有仓位强制平仓。
- 保守 MDD 同时计入日内可能达到的有利峰值和不利谷值，不假定未知 OHLC 顺序对策略有利。

## 判定

- 主要报告净值倍数、年化因子、保守 MDD、campaign 数、胜率、profit factor、加仓次数、下单目标最大杠杆、有效开盘最大杠杆、成本与 funding。
- 来源用户硬目标保持为：年化因子严格 `>20x`、保守 MDD `<=20%`、目标杠杆不超过 `3x`。
- 任一 BTC/ETH 直迁失败，不通过调参覆写本次结论；后续目标资产调参必须作为新的单资产研究。
