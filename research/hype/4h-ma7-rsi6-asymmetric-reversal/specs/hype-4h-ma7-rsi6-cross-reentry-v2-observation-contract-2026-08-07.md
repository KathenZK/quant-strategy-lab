# HYPE 4H MA7-RSI6 Cross-Reentry V2 观察合同（2026-08-07）

## 身份与状态

- Family：`HYPE-4H-MA7-RSI6-Asymmetric-Reversal`
- Observation：`V2 Cross-Reentry`，`not registered`
- 市场/周期：Binance USD-M `HYPEUSDT` perpetual，UTC `4h`
- 状态：`explore / not promoted / not live-ready`
- 变更目的：保留 V1 的 RSI6 超买过滤做空，但允许空头在重新站上 SMA7 时直接反手做多，避免等待 RSI6 超卖退出后才重新进入多头。

## 冻结状态机

所有信号只读取闭合的 `4h`，在下一根 `4h` open 执行：

1. `flat -> long`：`close[t] > SMA7[t]`。
2. `long -> short`：同时满足：
   - `close[t] < SMA7[t]`；
   - 最近三根（含当前）至少一根 Wilder RSI6 严格 `>70`。
3. `short -> long`：`close[t] > SMA7[t]`；该条件优先于 RSI6 `<30`，下一根 open 平空并直接反手做多，按两次 fill。
4. `short -> flat`：未满足 `close[t] > SMA7[t]`，但当前 RSI6 严格 `<30`。
5. 其他情况保持当前状态。

用户明确保留 `long -> short` 的最近三根 RSI6 超买过滤；本观察不是任何跌破 SMA7 都反手做空的纯 MA7 flip。

## 其余继承口径

- `SMA7`、TradingView/Wilder `RSI6` 公式、严格阈值、数据、funding、费用、滑点、约 `1x` 固定数量、terminal flatten 与审计窗口均继承[V1 冻结合同](hype-4h-ma7-rsi6-asymmetric-reversal-contract-2026-08-06.md)。
- 无 hard stop、trailing stop、cooldown 或 max hold。
- 全期 base、`8 bps`、额外延迟一根、gross、最后 `120d`、近期、rolling 90 日与 `0h/1h/2h/3h` 相位全部重跑。

## 判定纪律

- 本轮只改变 `short -> long`；不得根据结果再改多头过滤、RSI 阈值或优先级。
- 所有历史已经揭示，不是 clean OOS。
- 本轮不登记版本、不创建 live spec、不推进 runner。
