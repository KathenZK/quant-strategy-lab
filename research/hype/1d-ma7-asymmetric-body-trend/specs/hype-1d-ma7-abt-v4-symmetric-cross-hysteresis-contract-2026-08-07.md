# HYPE V4 对称 MA7 Cross × 持仓迟滞诊断合同

> 冻结时间：2026-08-07（首次运行前）。状态：`explore / diagnostic-only / not promoted / not live-ready`。

## 研究问题

用户澄清的核心机制不是“入场也必须越过 ATR 容错带”，而是：

1. 空仓入场只要求完整日线收盘新鲜穿越 `SMA7`，多空完全对称；
2. `0.75×ATR7` 容错只在已经持仓时生效；
3. 持有 long 时，轻微跌破 `SMA7` 继续容忍，只有跌破下容错边界才反手 short；
4. 持有 short 时完全对称，只有突破上容错边界才反手 long。

本轮只检验这一套对称方向状态转换，不搜索阈值，不修改登记 V4，也不登记 V5。

## 冻结变体

### `V4_CONTROL`

登记的 `HYPE-1D-MA7-Asymmetric-Body-Trend-V4`。

### `SYMMETRIC_CROSS_D075`

日 `t` 收盘只使用已经闭合的 UTC 日 K：

- flat fresh long cross：
  `close[t-1] <= SMA7[t-1]` 且 `close[t] > SMA7[t]`；
- flat fresh short cross：
  `close[t-1] >= SMA7[t-1]` 且 `close[t] < SMA7[t]`；
- flat 入场不检查 `ATR7` 距离、MA7 slope、V4 entry buffer 或持续 regime；
- fresh cross 在 `t+1` open 成交；信号被 cooldown 阻挡后不保留 pending。

持仓方向迁移：

- 当前 long：当 `close[t] < SMA7[t] - 0.75×ATR7[t]` 时，在 `t+1` open 平 long 并同 open 建 short；
- 当前 short：当 `close[t] > SMA7[t] + 0.75×ATR7[t]` 时，在 `t+1` open 平 short 并同 open 建 long；
- 持仓期间仅穿越 `SMA7`、但未越过对应外边界时继续持仓；
- 外边界反手不检查 slope、entry buffer 或 fresh cross，平仓与开仓分别计一次 fill 成本；
- 同侧不加仓、不调仓；不存在“只因持续位于 MA7 某侧就重新入场”的 regime 逻辑。

## 风险层与优先级

- long 保留 V4 `trail_atr=1.5`、`max_hold_days=90`、`cooldown_days=2`，无 hard stop；
- short 保留 V4 `hard_stop_atr=1.5`、`trail_atr=4.0`、`max_hold_days=20`、`cooldown_days=5`；
- hard/trailing stop 只作保护性平仓，不自行决定反手方向；
- max hold 只平仓到 flat，不自行决定反手方向；
- 保护或 max-hold 退出后执行原方向 V4 cooldown；cooldown 结束后仍须等待新的 fresh MA7 cross；
- 已持仓时优先处理上一完整日产生的 `0.75×ATR7` 外边界反手，再处理 max hold；
- stop 使用真实 `1h` 路径：小时 open 跳空越过保护价时按 open 成交，小时内触发按冻结的保护成交规则执行；
- stop 后不使用未知的同小时后续路径；新方向在反手当日立即启用自己的保护规则。

以上风险数值全部继承 V4。本轮删除 short 独有的 MA7 slope exit，并把两侧日线方向退出统一为 `0.75×ATR7` 外边界反手；这是对称方向状态转换的一部分，不另行调参。

## 数据、仓位与成本

- Binance USD-M `HYPEUSDT` perpetual；
- accepted、closed-only 的真实 `1h` 数据聚合 UTC 日 K；
- `SMA7[t] = mean(close[t-6:t])`；
- `ATR7` 为日线 true range 的 7 日简单移动平均；
- 历史主路径与 V4 控制使用同一冻结数据截止点，最新延伸单列；
- 约 `1x`、单仓、非加仓，持仓期间数量固定；
- 手续费 `0.001/fill`、基准不利滑点 `4 bps/fill`、压力滑点 `8 bps/fill`；
- funding 使用真实 Binance event timestamp/rate，只在真实持仓区间结算。

## 必须输出

- `V4_CONTROL` 与 `SYMMETRIC_CROSS_D075` 的 prefit、最后 90 日 flat-start、full；
- `8 bps`、额外延迟一天、零 funding、`12h` 日界；
- 最近 `1d/7d/1m/3m/6m/1y`；
- 90 日窗口每 30 日滚动；
- 24 个日界相位及缺失原因；
- 最新数据延伸；
- 收益、MDD、Sharpe、PF、交易数、多空贡献、成本、funding、暴露率和简化破产检查；
- 每一次 flat fresh cross 入场、持仓外边界反手、保护退出、max-hold 退出和 cooldown 阻挡；
- 相对 V4 的逐笔新增、删除、提前、延后及仓位占用连锁变化；
- 自包含完整交易路径 HTML，逐笔连接 entry 与 exit。

## 裁决纪律

1. 本轮只回答该对称机制在冻结历史上的行为和结果，不把图形直觉当成收益证据；
2. 不根据某一笔已揭示赢家调整 `0.75`、增加 slope、增加 pending 或改变 cooldown；
3. 即使主路径高于 V4，也不能据此登记 V5 或 promotion；
4. 若历史失败，仍须区分“用户本意是否被正确实现”和“该机制是否具有历史优势”；
5. 任何后续变体必须重新冻结合同，并且一次只改变一个机制。
