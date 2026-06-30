# HYPE-15M-Multi-Indicator-Intraday-V1 实盘可行性审计 2026-06-29

Family：`HYPE-15M-Multi-Indicator-Intraday`（alias：`HYPE-15M-MII`）

版本：`HYPE-15M-Multi-Indicator-Intraday-V1`

审计结论：`NO-GO / not live-ready / not paper-live-ready`

## 直接结论

V1 现在不能实盘。它的闭合 K 信号和下一根 open 入场在机制上可以实现，但研究稳定性、真实成交模型和生产状态机都没有达到 promotion 门槛。把它命名为 V1 只是建立研究基线，不代表可以带资金运行。

## 已修复的回测时序问题

本轮没有直接沿用旧搜索模拟器，而是修复了两处不可实盘复现的时序：

1. 旧 timeout 逻辑可能先读取 timeout K 的 high/low，再按同一根 K 的 open 退出。V1 改为持满完整 K 后，下一根 open 先执行 timeout，不读取未来路径。
2. 旧单仓选择器可能允许上一单在本 K 盘中退出、下一单却回到同一根 K 的 open 入场。V1 改为盘中退出后最早下一根 K 才可重新入场；只有 open 退出允许同一 open 先平后开。

修正后 V1 在标准数据湖与 Binance 默认成本口径（`0.1000%` 手续费/fill、`0.0400%` 滑点/fill，round-trip `0.2800%`）下，年化为 `18.66%`、最大回撤 `-31.84%`、Last90 年化 `-41.44%`。旧搜索指标应继续视为历史诊断，不能作为实盘预期。

## 审计矩阵

| 审计项 | 状态 | 证据或缺口 |
| --- | --- | --- |
| 数据来源与字段 | `PASS` | Binance perp 标准 raw/normalized 数据湖，字段完整。 |
| 连续性与重复 | `PASS` | `37,607` 根；gap、duplicate、critical null、非法 OHLCV/VWAP 均为 `0`。 |
| raw/normalized 对齐 | `PASS` | 缺行 `0`，OHLCV/quote volume/trade count/VWAP 值不一致 `0`。 |
| 数据新鲜度 | `BLOCKED` | 本次标准数据湖截止 `2026-06-26 04:00 UTC`，尚未覆盖审计日之前的完整 forward tail。 |
| 闭合 K 信号 | `PASS` | 指标只读取信号 K 及以前数据。 |
| 下一根 open 入场 | `PASS` | 回测严格使用 `signal_i + 1` 的 open。 |
| timeout 时序 | `PASS` | 已改为下一根 open 先退出，不读取该根 high/low。 |
| 单仓不重叠 | `PASS` | 已区分 open 退出和盘中退出，禁止回到过去的 open 开仓。 |
| 同 K TP/SL | `PARTIAL` | OHLC 无法知道真实路径，当前保守按 stop-first。 |
| open 跳过 stop | `PARTIAL` | 15m open 可见跳价按 open 成交，但没有 tick 级路径。 |
| stop-market 成交 | `BLOCKED` | 没有盘口深度、尾部滑点、触发延迟和订单失败回放。 |
| 费用与滑点 | `PARTIAL` | 使用固定 `0.1000% fee/fill + 0.0400% slippage/fill`，不是该策略真实成交样本。 |
| 资金费 | `BLOCKED` | 当前未计入；跨 funding 时点的仓位没有逐笔结算。 |
| 仓位与保证金 | `BLOCKED` | `1.5x` 只是权益暴露，未定义杠杆、保证金模式、数量舍入和 liquidation buffer。 |
| 交易所规则 | `BLOCKED` | 未审计 tick size、step size、min notional、reduce-only、position mode 和 client order id。 |
| runner 状态机 | `BLOCKED` | 没有本家族 live runner。 |
| bracket 订单维护 | `BLOCKED` | 未证明入场成交后 TP/SL 原子性、部分成交和撤改单恢复。 |
| 重启恢复与对账 | `BLOCKED` | 没有 exchange-first reconciliation、幂等恢复和孤儿订单处理。 |
| 缺 K 行为 | `BLOCKED` | 没有 missing-bar fail-closed、时钟漂移和数据延迟策略。 |
| 风控与 kill switch | `BLOCKED` | 没有日损、连续亏损、最大持仓、API 异常和人工急停规则。 |
| paper/live reconciliation | `BLOCKED` | 没有逐单 signal/order/fill/fee/slippage 对账样本。 |
| 时间稳定性 | `BLOCKED` | Last90 年化 `-41.44%`，后半段年化 `-33.00%`。 |
| 原始收益目标 | `BLOCKED` | 年化 `18.66%`，远低于 `>=2000%`。 |

## 全参数消融对实盘判断的影响

- 共 `62` 行，包含 `1` 条基线与 `61` 条 OAT/结构探针，完整 gate `0/62`。
- 标准成本下 V1 单参数消融仍为 `0/62` 通过完整 gate；表面最好单因子年化仅 `38.81%`，且 Last90 为负。
- `TP=1.2%` 年化 `34.41%`，但最大回撤 `-24.37%` 且胜率降至 `68.31%`。
- `MACD` 过滤删除后年化约 `-99.80%`，说明策略对这一过滤高度敏感。
- 替换 MACD 周期后表现显著恶化；ATR 窗口变化也没有得到目标级稳健改进。
- 加杠杆可以放大年化，但同步放大回撤，不能视为策略优化。

## Promotion 决策

- `live`：禁止。
- `paper-live`：禁止。仓库术语里 paper-live 也是 promotion 状态，当前 runner 和对账链路不存在。
- `dry-run`：禁止作为候选状态发布；可以未来开发纯研究 replay，但不能包装成已通过审计的 dry-run 策略。
- `candidate` / `handoff`：禁止。
- 当前唯一允许状态：`diagnostic baseline only`。

若未来继续，顺序必须是：先做 walk-forward 与 forward holdout，再做 tick/盘口级 stop 压力测试和真实成本采样，最后实现带持久状态、重启恢复、对账与 kill switch 的 runner。任何一步失败都维持 NO-GO。
