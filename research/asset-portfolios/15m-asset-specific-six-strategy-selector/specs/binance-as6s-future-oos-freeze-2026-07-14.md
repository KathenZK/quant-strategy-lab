# BIN-15M-AS6S-V1 未来 OOS 冻结规格（2026-07-14）

## 身份与状态

- Freeze id：`BIN-15M-AS6S-FUTURE-OOS-FREEZE-2026-07-14`
- Family：`Binance-15M-Asset-Specific-Six-Strategy-Selector`
- Registered version：`Binance-15M-Asset-Specific-Six-Strategy-Selector-V1`（`BIN-15M-AS6S-V1`）。
- Status：`registered / not promoted / not live-ready`。
- Canonical route：Route A `nonpreemptive`；Route B 只保留为冻结对照 observation，不属于 V1 交易路径。
- 机器冻结清单：[`../artifacts/binance_as6s_future_oos_freeze_2026-07-14.json`](../artifacts/binance_as6s_future_oos_freeze_2026-07-14.json)
- Freeze SHA-256：`a675d7de8d1a5784b7f6121174497cc31be2313578d50de6fb4a4d3c768394bf`

## 时间窗

- 参数选择截止（exclusive）：`2026-04-14T09:00:00Z`
- Reused diagnostic：`[2026-04-14T09:00:00Z, 2026-07-14T09:00:00Z)`
- Future final OOS：`[2026-07-14T09:00:00Z, 2026-10-14T09:00:00Z)`

最终 OOS 结束前，不得修改候选腿、参数、暴露、账户缩放、仲裁、cooldown 或抢占条件；任何修改都必须建立新 observation 和新未来窗口。

## 候选腿与风险

| Sleeve | 腿暴露 | 不抢占有效暴露 | 抢占有效暴露 |
|---|---:|---:|---:|
| `15m:ETHUSDT:reversal` | `1.5x` | `1.125x` | `0.75x` |
| `15m:SOLUSDT:breakout` | `1.0x` | `0.75x` | `0.50x` |
| `15m:BNBUSDT:breakout` | `1.5x` | `1.125x` | `0.75x` |
| `15m:HYPEUSDT:trend_state` | `1.0x` | `0.75x` | `0.50x` |
| `15m:HYPEUSDT:reversal` | `0.5x` | `0.375x` | `0.25x` |
| `1h:BTCUSDT:keltner_break` | `1.0x` | `0.75x` | `0.50x` |
| `1h:ETHUSDT:rsi_reversal` | `1.0x` | `0.75x` | `0.50x` |
| `1h:HYPEUSDT:di_cross` | `1.5x` | `1.125x` | `0.75x` |
| `1h:TRXUSDT:macd_flip` | `2.5x` | `1.875x` | `1.25x` |

不抢占账户缩放为 `0.75`，最大有效暴露 `1.875x`；抢占路线缩放为 `0.50`，最大有效暴露 `1.25x`。两者均低于 `3x`。

15m 腿的完整 `StrategyConfig` 已内嵌在机器冻结清单。1h 腿由冻结迁移脚本、源配置和输入 SHA-256 共同锁定，禁止在未来 OOS 前替换为后续资产家族版本。

## 统一账户状态机

- 全账户最多一个持仓。
- 候选按 `entry_ts` 排序；同一时刻按冻结 strength 降序。
- 新入场必须严格晚于上一笔退出，即 `entry_ts > blocked_until`。
- 被阻塞信号立即丢弃，不排队，不在平仓后补单。
- 旧 1h 腿先产生逐信号无状态机会；只有该腿被账户真实执行后，才从真实退出时点写入该腿 cooldown。
- 15m 腿没有额外 cooldown。
- 持仓回撤按逐笔 MAE trough 计入，不只检查平仓权益点。

## V1 路线与冻结对照

### V1 / Route A：nonpreemptive

当前交易必须按自身退出规则走完；其他币再强的信号也不能提前平仓。

### 对照 observation / Route B：strong_breakout_preemptive

只有满足全部条件的其他币 breakout 可以抢占：

- challenger symbol 与当前 symbol 不同；
- challenger strength `>=0.70`；
- challenger strength 至少高于当前腿 `0.05`；
- 当前持仓时间 `>=8h`。

抢占时按挑战信号时点的市场 open、对应情景滑点、手续费和实际 funding 平掉当前仓；被抢占腿从该真实退出时点进入 cooldown。

## 成本与执行

- 闭合信号 K 后下一根 open 入场；K+2 压力为延迟一根额外 K。
- 手续费：`0.001/fill`。
- 基础 adverse slippage：`4 bps/fill`。
- 压力 adverse slippage：`8 bps/fill`。
- Funding：Binance 实际历史 funding。
- Stop 即时有效；同 K stop/target 双触发按 stop-first；gap 穿 stop 按 open。

## 最终 OOS 硬门槛

每条路线独立判定：

- full trades `>=200`；
- future OOS trades `>=30`；
- full 和 future OOS 胜率均 `>=80%`；
- full 和 future OOS 最大回撤均严格 `<20%`；
- full 和 future OOS 收益均为正；
- 最大有效暴露 `<=3x`。

8bps 与 K+2 必须另行报告；若收益为负或最大回撤达到/超过 `20%`，不得进入 promotion。

## 当前边界

当前 reused diagnostic 两条路线均通过，但 `future final OOS` 尚未完成。最早在 `2026-10-14T09:00:00Z` 数据齐备、质量门禁通过后执行一次性最终评估；在此之前 V1 状态保持 `registered / not promoted / not live-ready`。
