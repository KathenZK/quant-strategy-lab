# HYPE 15m MA7 退出冻结对照契约（2026-07-30）

## 研究问题

把 HYPE 日线 MA7/MA30 纯收益 observation 的参数值解释为 `15m bar` 数并原样迁移，只改变退出条件，回答：

1. 原控制组：持仓期间等待 EMA7/EMA30 反向交叉；
2. MA7 退出组：多仓 `close < EMA7`、空仓 `close > EMA7` 后，下一根 `15m` open 平仓。

目标是判断更快的 MA7 退出能否改善回撤和净收益，不根据结果搜索其他参数。

## 固定参数

| 参数 | 值 |
| --- | --- |
| MA | `EMA7 / EMA30`，均按 15m bars |
| entry | EMA7/EMA30 regime 内，价格重新穿越 EMA7，EMA7 斜率同向，双向 |
| ATR | Wilder-style `ATR10` |
| initial leverage | `0.5x` |
| add | campaign 浮盈、价格相对加权成本盈利、仍沿 EMA7，且相对上次加仓推进 `0.25 ATR10` 后，下一 open 重置目标 `3x` |
| initial stop | `3 ATR10` |
| trailing stop | 最高/最低收盘价回撤 `3 ATR10` |
| profit lock | 有利移动达到入场 `3 ATR10` 后，锁定入场价外 `0.5 ATR10` |
| timeout | `20` 根 15m bars，即最多约 5 小时 |
| cooldown | `2` 根 15m bars |
| immediate flip | `false` |

`confirm_days=2`、`breakout_window=7` 和 `add_increment=1.5` 在当前 entry/add 组合中不参与成交路径，只保留逐字段来源身份。

## 数据与冻结边界

- 市场：Binance USD-M `HYPEUSDT` perpetual。
- 数据：交易所原生、已收盘 `15m` K；实际 funding。
- 数据范围：从合约上线后的首根完整数据开始，终点使用最后一根已收盘 K 的 open 作为 terminal open，因此不依赖未收盘 K。
- prefit：终点 `2026-04-30 00:00 UTC`，exclusive。
- researcher-exposed holdout：`2026-05-01 00:00 UTC` 至 terminal，flat-start；仅作审计，不参与参数选择。
- full：全部可用数据。
- 两个退出组同时冻结；holdout 和 full 结果均不得反馈回参数。

## 成本、时序与冲突

- 手续费：每次实际成交名义金额的 `0.001`。
- 基础不利滑点：`4 bps/fill`；压力为 `8 bps/fill`。
- 信号只能使用已收盘 15m K，基础下一根 open 成交，另审计 `K+2`。
- “跌破/突破 MA7”是收盘确认，不是假设可以在当前 K 内按动态 MA7 无滑点成交。
- stop 由前一收盘后状态更新；下一根若 open 已穿越 stop，按 open，否则按 stop。
- 同一收盘退出与加仓冲突时退出优先；stop 成交时取消 pending。
- terminal open 禁止新开/加仓，已有仓位强制平仓并收费。
- 持仓数量只在实际成交时改变，不做每根 bar 免费再平衡。
- 目标数量按成交成本后的权益方程分段解析求解，避免极低权益路径中的迭代浮点误差；经济目标和硬上限仍为精确 `3x`，不构成参数变化。

## 判定

- 报告 full、prefit、flat-start holdout 的净值倍数、年化因子、保守 MDD、campaign、胜率、PF、加仓、成本、funding 和有效开盘杠杆。
- 同时报告 `8 bps`、`K+2` 与最近 `1d/7d/1m/3m/6m/1y` 切片。
- 额外运行零手续费、零滑点但保留 funding 的诊断，用于区分毛信号失败与交易摩擦；该诊断不作为可交易收益。
- 用户原硬目标仍为：年化因子严格 `>20x`、MDD `<=20%`、目标杠杆不超过 `3x`。
- 若 MA7 退出改善回撤但仍不通过联合硬目标，只能记为风险方向证据，不能登记或 promotion。
