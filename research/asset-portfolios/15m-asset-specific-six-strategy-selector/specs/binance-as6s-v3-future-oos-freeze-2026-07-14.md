# BIN-15M-AS6S-V3 observation 未来 OOS 冻结规格（2026-07-14）

## 身份与状态

- Freeze id：`BIN-15M-AS6S-V3-FUTURE-OOS-FREEZE-2026-07-14`
- Family：`Binance-15M-Asset-Specific-Six-Strategy-Selector`
- Candidate：`BIN-15M-AS6S-V3-observation`
- Status：`frozen observation / not registered / not promoted / not live-ready`
- 机器冻结清单：[../artifacts/binance_as6s_v3_future_oos_freeze_2026-07-14.json](../artifacts/binance_as6s_v3_future_oos_freeze_2026-07-14.json)
- Freeze SHA-256：`d949d73b071d6db26df28e0195f842d1409692aea1c421c0b3a276a0b6a30d87`

该冻结不会替换已登记的 `BIN-15M-AS6S-V1`。V3 只有在未来最终 OOS 完成后，才允许讨论是否登记为新版本。

## 时间边界

- 选择和诊断数据截止（exclusive）：`2026-07-14T09:00:00Z`
- Future final OOS：`[2026-07-14T09:00:00Z, 2026-10-14T09:00:00Z)`
- 最早揭示：完整窗口数据、funding 和质量审计全部齐备后的 `2026-10-14T09:00:00Z`

禁止提前查看未来窗口的部分结果。参数、候选腿、暴露、账户缩放、strength、仲裁、cooldown、退出与抢占规则中任意一项发生变化，都必须建立新的 observation 和新的未来 OOS 窗口。

## 冻结候选腿

| Sleeve | 腿暴露 | 不抢占有效暴露 | 抢占有效暴露 |
|---|---:|---:|---:|
| HYPE 15m Clean-RSI reversal | 1.25x | 0.50x | 0.4125x |
| BNB 15m breakout | 2.00x | 0.80x | 0.66x |
| ETH 15m breakout | 2.00x | 0.80x | 0.66x |
| ETH 15m trend state | 2.00x | 0.80x | 0.66x |
| HYPE 15m breakout | 2.50x | 1.00x | 0.825x |
| HYPE 15m reversal | 3.00x | 1.20x | 0.99x |
| SOL 15m breakout | 1.50x | 0.60x | 0.495x |
| SOL 15m reversal | 2.00x | 0.80x | 0.66x |
| SOL 15m trend state | 2.50x | 1.00x | 0.825x |
| BNB 1h wick reject | 1.00x | 0.40x | 0.33x |
| BTC 1h Keltner breakout | 2.40x | 0.96x | 0.792x |
| ETH 1h RSI reversal | 2.00x | 0.80x | 0.66x |
| HYPE 1h DI cross | 3.00x | 1.20x | 0.99x |
| SOL 1h Donchian breakout | 3.00x | 1.20x | 0.99x |
| TRX 1h MACD flip | 3.00x | 1.20x | 0.99x |

机器冻结清单内嵌 15m 配置、候选强度、全部路线参数，并锁定 122 个研究依赖文件，其中包括未来一次性揭示程序。六币截至选择截止时点的 OHLCV 和 funding 采用逻辑行哈希冻结，后续追加未来数据不得改变历史行。

## 冻结路线

### Route A：nonpreemptive

- `account_scale=0.40`
- 最大有效暴露 `1.20x`
- 当前持仓必须按自身退出规则结束；其他候选不得抢占

### Route B：strong-breakout-preemptive

- `account_scale=0.33`
- 最大有效暴露 `0.99x`
- challenger 必须来自其他币的 breakout
- `strength>=0.75`
- strength 至少高于当前腿 `0.05`
- 当前仓位至少持有 `1h`

## 账户与执行状态机

- 全账户同时最多一个持仓；被阻塞信号立即丢弃，不排队。
- 平仓后重新计算当时最新候选，不执行持仓期间积压信号。
- 闭合 K 产生信号；K+1 为下一根 open，K+2 为再延迟一根 K 的压力路径。
- gap stop 按真实 open 加不利滑点；同根 stop/target 双触发按 stop-first。
- timeout 在指定 K 的 open 执行，不读取该 K 的 high/low。
- 1h 状态仅在整根 1h K 闭合后才能进入 15m 行。
- 手续费 `0.001/fill`；基准滑点 `4 bps/fill`；压力滑点 `8 bps/fill`。
- Funding 使用 Binance 历史记录。标准边界和相反事件排序均已审计；逐笔选择两者较差 funding 时，账户门槛仍通过。

执行语义证据：[../artifacts/binance_as6s_v3_execution_semantics_2026-07-14.json](../artifacts/binance_as6s_v3_execution_semantics_2026-07-14.json)；资金费边界证据：[../artifacts/binance_as6s_v3_funding_boundary_2026-07-14.json](../artifacts/binance_as6s_v3_funding_boundary_2026-07-14.json)。

冻结揭示程序为 [../scripts/reveal_binance_as6s_v3_future_oos.py](../scripts/reveal_binance_as6s_v3_future_oos.py)。该程序已在冻结期数据上重建全部 15 条腿和两条账户路径，逐字段复现原候选指标；证据见[../artifacts/binance_as6s_v3_reveal_reproduction_2026-07-14.json](../artifacts/binance_as6s_v3_reveal_reproduction_2026-07-14.json)。在未来窗口结束前，程序只允许 `--check-only`，不得输出部分 OOS 指标。

## 最终 OOS 硬门槛

每条路线独立判定：

- full trades `>=200`；
- future OOS trades `>=30`；
- full 和 future OOS 胜率均 `>=80%`；
- full 和 future OOS 最大回撤均严格 `<20%`；
- full 和 future OOS 收益均为正；
- 最大有效暴露 `<=3x`；
- 8 bps 与 K+2 的 future OOS 收益均为正且最大回撤 `<20%`。

任一门槛失败，V3 observation 不得登记和 promotion。当前结果只证明冻结前诊断通过，不证明未来 OOS 通过。
