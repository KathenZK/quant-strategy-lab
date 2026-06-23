# HYPE-CC-V13 全部 ATR288 双向限制策略规格

本文档用于实现 HYPE 15m V13 实盘策略。目标是让另一个 AI 或工程师只看这份文档，就能在 Rust 中实现与当前 Python 版本一致的策略逻辑。

## 1. 策略概要

- 策略名称：`HYPE V13 全部 ATR288 双向限制`
- 交易标的：`HYPE/USDT:USDT` 永续合约
- 周期：`15m`
- 策略类型：K 线颜色计数反转策略
- 交易方向：多空双向
- 最大名义仓位：
  - 做多最大 `3.0x` 账户权益
  - 做空最大 `3.0x` 账户权益
- 核心信号：
  - 最近 10 根 15m K 线中，阳线数量大于等于 8：做空
  - 最近 10 根 15m K 线中，阴线数量大于等于 8：做多
- 仓位、止盈、止损全部使用 `ATR288` 动态计算
- 止盈和止损百分比均限制在 `2.5% - 3.5%`
- 无硬性最大持仓时间，持仓只通过止盈或止损退出

实盘实现时必须只使用已经收盘的 15m K 线，不允许使用正在形成的当前 K 线生成信号。

## 2. 完整参数表

| 参数 | 值 | 说明 |
|---|---:|---|
| `symbol` | `HYPE/USDT:USDT` | HYPE USDT 永续合约 |
| `timeframe` | `15m` | 信号周期 |
| `lookback` | `10` | 统计最近 10 根已收盘 K 线 |
| `min_count` | `8` | 阳线或阴线数量触发阈值 |
| `bullish_signal_direction` | `-1` | 阳线数量大于等于 8 时做空 |
| `bearish_signal_direction` | `1` | 阴线数量大于等于 8 时做多 |
| `long_allocation` | `3.0` | 做多最大名义仓位，等于账户权益的 3 倍 |
| `short_allocation` | `3.0` | 做空最大名义仓位，等于账户权益的 3 倍 |
| `allocation_atr_window` | `288` | 仓位使用 ATR288 |
| `target_atr_pct` | `0.004` | 目标 ATR，占价格 0.4% |
| `stop_loss_atr_window` | `288` | 止损使用 ATR288 |
| `stop_loss_atr_multiplier` | `5.0` | 动态止损距离等于 ATR288 百分比乘以 5 |
| `min_stop_loss_pct` | `0.025` | 止损下限 2.5% |
| `max_stop_loss_pct` | `0.035` | 止损上限 3.5% |
| `take_profit_atr_window` | `288` | 止盈使用 ATR288 |
| `take_profit_atr_multiplier` | `6.0` | 动态止盈距离等于 ATR288 百分比乘以 6 |
| `min_take_profit_pct` | `0.025` | 止盈下限 2.5% |
| `max_take_profit_pct` | `0.035` | 止盈上限 3.5% |
| `trend_window_bars` | `96` | 24 小时趋势过滤窗口，96 根 15m K 线 |
| `trend_block_pct` | `0.06` | 24 小时涨跌幅禁入阈值，6% |
| `entry_mode` | `signal_start` | 只在信号刚出现时开仓，不在连续同向信号中重复开仓 |
| `opposite_signal_gap_bars` | `8` | 最近 8 根 K 线出现过反向信号则不新开仓 |
| `cooldown_bars` | `8` | 每次平仓后冷却 8 根 K 线，即 2 小时 |
| `stop_loss_risk_multiplier` | `0.5` | 每次止损后，下一次开仓风险倍率减半 |
| `min_risk_multiplier` | `0.125` | 风险倍率最低降到 12.5% |
| `fee_rate` | `0.00045` | 回测使用 Hyperliquid taker 费率 0.045% |
| `slippage_rate` | `0.0004` | 回测使用滑点估计 0.04% |
| `total_cost_rate_per_side` | `0.00085` | 单边成本，手续费加滑点 |

如果实盘交易所费率或滑点不同，应以实盘环境为准；但为了复现当前回测，应使用上表成本参数。

## 3. Rust 配置示例

下面是建议在 Rust 中使用的配置结构，字段名可以按项目风格调整，但语义必须保持一致。

```rust
#[derive(Debug, Clone)]
pub struct HypeV13Config {
    pub symbol: String,
    pub timeframe: String,
    pub lookback: usize,
    pub min_count: usize,
    pub long_allocation: f64,
    pub short_allocation: f64,
    pub allocation_atr_window: usize,
    pub target_atr_pct: f64,
    pub stop_loss_atr_window: usize,
    pub stop_loss_atr_multiplier: f64,
    pub min_stop_loss_pct: f64,
    pub max_stop_loss_pct: f64,
    pub take_profit_atr_window: usize,
    pub take_profit_atr_multiplier: f64,
    pub min_take_profit_pct: f64,
    pub max_take_profit_pct: f64,
    pub trend_window_bars: usize,
    pub trend_block_pct: f64,
    pub cooldown_bars: usize,
    pub opposite_signal_gap_bars: usize,
    pub stop_loss_risk_multiplier: f64,
    pub min_risk_multiplier: f64,
    pub fee_rate: f64,
    pub slippage_rate: f64,
}

impl Default for HypeV13Config {
    fn default() -> Self {
        Self {
            symbol: "HYPE/USDT:USDT".to_string(),
            timeframe: "15m".to_string(),
            lookback: 10,
            min_count: 8,
            long_allocation: 3.0,
            short_allocation: 3.0,
            allocation_atr_window: 288,
            target_atr_pct: 0.004,
            stop_loss_atr_window: 288,
            stop_loss_atr_multiplier: 5.0,
            min_stop_loss_pct: 0.025,
            max_stop_loss_pct: 0.035,
            take_profit_atr_window: 288,
            take_profit_atr_multiplier: 6.0,
            min_take_profit_pct: 0.025,
            max_take_profit_pct: 0.035,
            trend_window_bars: 96,
            trend_block_pct: 0.06,
            cooldown_bars: 8,
            opposite_signal_gap_bars: 8,
            stop_loss_risk_multiplier: 0.5,
            min_risk_multiplier: 0.125,
            fee_rate: 0.00045,
            slippage_rate: 0.0004,
        }
    }
}
```

## 4. K 线和指标定义

### 4.1 K 线字段

每根 15m K 线至少需要：

- `timestamp`
- `open`
- `high`
- `low`
- `close`
- `mark_high`
- `mark_low`
- `funding_rate`

其中：

- `open/high/low/close` 用于计算信号、ATR、趋势过滤和持仓盯市。
- `mark_high/mark_low` 用于触发止盈止损。
- `funding_rate` 用于回测资金费；实盘由交易所实际结算。

如果实盘无法拿到 15m 的 `mark_high/mark_low`，应使用交易所原生的 mark price trigger stop/take order，而不是用普通成交价触发。

### 4.2 阳线和阴线

```text
bullish = close > open
bearish = close < open
doji    = close == open
```

十字线既不计入阳线，也不计入阴线。

### 4.3 阳线和阴线计数

在每根已收盘 K 线 `t` 上：

```text
bullish_count_10[t] = 最近 10 根已收盘 K 线中 bullish 的数量，包含 t
bearish_count_10[t] = 最近 10 根已收盘 K 线中 bearish 的数量，包含 t
```

如果历史 K 线不足 10 根，不产生信号。

### 4.4 ATR288 百分比

真实波幅 `TR`：

```text
previous_close[t] = close[t - 1]

TR[t] = max(
    high[t] - low[t],
    abs(high[t] - previous_close[t]),
    abs(low[t] - previous_close[t])
)
```

ATR288：

```text
ATR288[t] = 最近 288 根 TR 的简单移动平均，包含 t
```

ATR288 百分比：

```text
atr_pct_288[t] = ATR288[t] / close[t]
```

如果历史不足 288 根有效 TR，或者 `atr_pct_288 <= 0`，本根 K 线不允许开仓。

建议实盘启动时预热至少 300 根 15m K 线。

### 4.5 24 小时趋势收益

```text
ret_96[t] = close[t] / close[t - 96] - 1
```

因为 96 根 15m K 线等于 24 小时。如果历史不足 96 根，趋势过滤值为空，本根 K 线不允许开仓。

## 5. 信号生成

每根 15m K 线收盘后，按如下规则生成原始信号：

```text
if bullish_count_10 >= 8:
    signal = -1   // 做空
else if bearish_count_10 >= 8:
    signal = 1    // 做多
else:
    signal = 0    // 无信号
```

理论上 `bullish_count_10 >= 8` 和 `bearish_count_10 >= 8` 不会同时成立，因为两者数量之和最多为 10。

方向定义：

```text
1  = long
-1 = short
0  = flat / no signal
```

## 6. 入场过滤

只有当前没有持仓时才允许开仓。持仓期间忽略所有新信号，不加仓、不减仓、不反手。

### 6.1 signal_start 过滤

`entry_mode = signal_start` 表示只在信号刚出现时开仓。

如果当前信号方向和上一根 K 线信号方向相同，则不允许开仓：

```text
if signal[t] == signal[t - 1] and signal[t] != 0:
    block_entry
```

这个规则用于避免同一段连续信号中重复进场。

### 6.2 反向信号间隔过滤

参数：

```text
opposite_signal_gap_bars = 8
```

如果当前要做多，但过去 8 根 K 线中出现过做空信号，则不允许开仓。

如果当前要做空，但过去 8 根 K 线中出现过做多信号，则不允许开仓。

注意：检查窗口只包含当前 K 线之前的 8 根，不包含当前 K 线。

```text
recent = signal[t - 8 ... t - 1]

if desired_direction == 1 and recent contains -1:
    block_entry

if desired_direction == -1 and recent contains 1:
    block_entry
```

### 6.3 24 小时趋势禁入

参数：

```text
trend_window_bars = 96
trend_block_pct = 0.06
```

规则：

```text
if desired_direction == -1 and ret_96[t] > 0.06:
    block_entry

if desired_direction == 1 and ret_96[t] < -0.06:
    block_entry
```

解释：

- 最近 24 小时涨幅超过 6%，不做空。
- 最近 24 小时跌幅超过 6%，不做多。
- 其他情况允许通过。

如果 `ret_96[t]` 为空，禁止开仓。

### 6.4 冷却过滤

每次止盈或止损平仓后，进入 `8` 根 K 线冷却期。

```text
cooldown_bars = 8
```

15m 周期下，8 根 K 线等于 2 小时。冷却期间不允许新开仓。

如果某根 K 线刚刚触发平仓，则同一根 K 线不允许重新开仓。

## 7. 仓位计算

仓位使用账户权益倍数表示，而不是保证金比例。

例如：

- 当前账户权益 `equity = 10,000 USDT`
- 当前目标仓位 `allocation = 2.0`
- 目标名义价值 `target_notional = 20,000 USDT`

### 7.1 基础 ATR 动态仓位

多空最大仓位均为 `3.0x`：

```text
max_allocation = 3.0
target_atr_pct = 0.004
```

基础仓位：

```text
base_allocation = min(
    max_allocation,
    max_allocation * target_atr_pct / atr_pct_288[t]
)
```

也就是：

```text
base_allocation = min(
    3.0,
    3.0 * 0.004 / atr_pct_288[t]
)
```

含义：

- 当 ATR288 小于等于 0.4% 时，仓位达到最大 3x。
- 当 ATR288 大于 0.4% 时，仓位按波动率降低。

示例：

```text
atr_pct_288 = 0.004
base_allocation = min(3.0, 3.0 * 0.004 / 0.004) = 3.0

atr_pct_288 = 0.008
base_allocation = min(3.0, 3.0 * 0.004 / 0.008) = 1.5
```

### 7.2 止损后风险倍率

策略维护一个 `risk_multiplier`：

```text
初始 risk_multiplier = 1.0
```

每次止损后：

```text
risk_multiplier = max(0.125, risk_multiplier * 0.5)
```

每次止盈后：

```text
risk_multiplier = 1.0
```

最终开仓仓位：

```text
entry_allocation = base_allocation * risk_multiplier
```

示例：

```text
连续 0 次止损：risk_multiplier = 1.0
连续 1 次止损：risk_multiplier = 0.5
连续 2 次止损：risk_multiplier = 0.25
连续 3 次止损：risk_multiplier = 0.125
连续更多止损：risk_multiplier 维持 0.125
```

止损后风险倍率是单个标的维度的状态。HYPE 当前是单标的策略，因此全策略只有一个风险倍率状态。

### 7.3 下单数量

实盘下单时：

```text
target_notional = account_equity * entry_allocation
quantity = target_notional / entry_price
```

其中：

- `account_equity` 是分配给该策略的当前账户权益。
- `entry_price` 是实际下单成交价或预估成交价。
- `quantity` 需要按交易所合约精度、最小下单量和最小名义价值修正。

如果使用逐仓，应确保逐仓杠杆和保证金足以承载目标名义仓位。本文档中的 `3.0x` 指目标名义价值等于权益的 3 倍，不等同于必须把交易所杠杆参数固定为 3；但为了风险一致，实盘建议设置逐仓杠杆不低于目标最大仓位，且不要让交易所自动放大到策略外的仓位。

## 8. 止盈和止损

止盈、止损都在开仓时计算一次，持仓期间不动态更新。

### 8.1 动态止损距离

```text
raw_stop_loss_pct = atr_pct_288[t] * 5.0
stop_loss_pct = clamp(raw_stop_loss_pct, 0.025, 0.035)
```

也就是止损百分比最低 2.5%，最高 3.5%。

### 8.2 动态止盈距离

```text
raw_take_profit_pct = atr_pct_288[t] * 6.0
take_profit_pct = clamp(raw_take_profit_pct, 0.025, 0.035)
```

也就是止盈百分比最低 2.5%，最高 3.5%。

### 8.3 多单价格

开多时：

```text
entry_price = close[t] 或实际成交均价
stop_price = entry_price * (1 - stop_loss_pct)
take_price = entry_price * (1 + take_profit_pct)
```

### 8.4 空单价格

开空时：

```text
entry_price = close[t] 或实际成交均价
stop_price = entry_price * (1 + stop_loss_pct)
take_price = entry_price * (1 - take_profit_pct)
```

### 8.5 触发价格类型

回测使用 `mark_high` 和 `mark_low` 判断止盈止损是否触发。

实盘建议使用交易所的 mark price trigger：

- 止损单：reduce-only trigger market order
- 止盈单：reduce-only trigger market order
- 触发价格类型：mark price

开仓成交后，应立即挂出对应的止盈和止损保护单。两者应为互斥关系；一个成交后，另一个必须取消。如果交易所不支持原生 OCO，需要在本地订单管理中实现。

### 8.6 同一根 K 线同时触发止盈止损

当前回测逻辑是保守口径：

- 如果同一根 15m K 线内止损和止盈都可能触发，优先按止损处理。

实盘中以交易所真实触发先后为准。

## 9. 持仓和退出规则

策略没有时间止盈、时间止损或最大持仓时间。

持仓只会因为以下事件退出：

```text
1. 触发止损
2. 触发止盈
```

不会因为以下事件退出：

```text
1. 出现反向信号
2. 信号消失
3. 达到固定持仓时长
4. 24 小时趋势过滤变差
```

持仓期间不加仓、不减仓、不反手。新信号只在当前完全空仓时才用于开仓。

## 10. 每根 K 线的处理顺序

Rust 实现建议按以下顺序处理每根已收盘 15m K 线。

```text
for each closed 15m bar t:
    update candle history
    compute bullish_count_10
    compute bearish_count_10
    compute atr_pct_288
    compute ret_96

    if position is open:
        do not open new position
        rely on existing stop/take reduce-only trigger orders
        continue

    if cooldown_remaining > 0:
        cooldown_remaining -= 1
        continue

    desired_direction = build_signal(t)

    if desired_direction == 0:
        continue

    if not signal_start_allows(t, desired_direction):
        continue

    if not opposite_gap_allows(t, desired_direction):
        continue

    if not trend_filter_allows(t, desired_direction):
        continue

    base_allocation = compute_atr_allocation(t)
    entry_allocation = base_allocation * risk_multiplier

    stop_loss_pct = clamp(atr_pct_288[t] * 5.0, 0.025, 0.035)
    take_profit_pct = clamp(atr_pct_288[t] * 6.0, 0.025, 0.035)

    submit market entry order
    after entry fill:
        record actual average entry price
        submit reduce-only stop order
        submit reduce-only take-profit order
```

退出成交回报处理：

```text
on position exit:
    cancel remaining reduce-only protective order

    if exit_reason == stop:
        risk_multiplier = max(0.125, risk_multiplier * 0.5)

    if exit_reason == take:
        risk_multiplier = 1.0

    cooldown_remaining = 8
```

## 11. 回测成本和资金费

当前回测使用以下成本：

```text
fee_rate = 0.00045
slippage_rate = 0.0004
cost_rate = fee_rate + slippage_rate = 0.00085
```

每次开仓扣一次成本，每次平仓再扣一次成本：

```text
entry_cost = allocation * cost_rate
exit_cost = allocation * cost_rate
```

这些成本是按账户权益比例计的。例如仓位为 `3.0x` 时，单边成本约为：

```text
3.0 * 0.00085 = 0.00255 = 0.255% 账户权益
```

资金费回测口径：

```text
funding_pnl = -direction * allocation * funding_rate
```

其中：

- `direction = 1` 表示多单
- `direction = -1` 表示空单

实盘中资金费由交易所自动结算，Rust 程序只需要在账户权益和交易日志中记录实际资金费。

## 12. 状态变量

Rust 实盘程序至少需要持久化以下状态，避免重启后重复下单或丢失风险倍率。

```text
current_position_direction: -1 / 0 / 1
current_position_quantity
current_entry_price
current_entry_timestamp
current_stop_loss_pct
current_take_profit_pct
current_stop_order_id
current_take_order_id
risk_multiplier
cooldown_remaining
last_processed_bar_timestamp
last_signal
last_exit_timestamp
last_exit_reason
```

建议将这些状态写入本地数据库或持久化 KV 存储。程序重启后，应先从交易所查询真实持仓和未成交订单，再和本地状态对账。

## 13. 实盘订单要求

推荐订单语义：

```text
entry:
    type = market
    reduce_only = false

stop_loss:
    type = trigger_market
    trigger_by = mark_price
    reduce_only = true

take_profit:
    type = trigger_market
    trigger_by = mark_price
    reduce_only = true
```

必须保证：

- 开仓前没有残留旧保护单。
- 开仓成交后立即挂止盈和止损。
- 平仓后取消剩余保护单。
- 如果保护单部分成交，应检查真实剩余仓位并修正订单。
- 如果下单失败，不应继续开新仓，应进入人工检查或安全暂停。
- 如果本地状态和交易所真实持仓不一致，应以交易所真实持仓为准。

## 14. 复现当前 Python 行为的关键细节

实现时最容易出错的是以下几点：

1. 信号使用当前已经收盘的 K 线，rolling 窗口包含当前收盘 K 线。
2. `8/10` 阳线是做空，`8/10` 阴线是做多。
3. `entry_mode = signal_start`，连续同方向信号只允许第一根开仓。
4. 最近 8 根 K 线出现过反向信号，则当前信号不允许开仓。
5. 24 小时趋势过滤是 `close[t] / close[t - 96] - 1`，不是高低价振幅。
6. 做空时，如果 24 小时涨幅大于 6%，禁止开空。
7. 做多时，如果 24 小时跌幅小于 -6%，禁止开多。
8. 仓位、止盈、止损全部使用 `ATR288`。
9. ATR 是简单移动平均，不是 EMA。
10. 止盈和止损百分比在开仓时固定，持仓期间不更新。
11. 止盈和止损都限制在 `2.5% - 3.5%`。
12. 止损后下一笔仓位风险倍率减半，止盈后恢复为 1。
13. 平仓后冷却 8 根 K 线。
14. 策略没有最大持仓时间。
15. 持仓期间不根据反向信号平仓或反手。
16. 回测里同一根 K 线同时触发止盈止损时，优先算止损。

## 15. 最小实现伪代码

```text
initialize:
    risk_multiplier = 1.0
    cooldown_remaining = 0
    position = none

on_closed_bar(bar):
    append bar to history

    if history length < 300:
        return

    signal = build_signal(history)
    atr_pct = compute_atr_pct_288(history)
    ret_96 = compute_ret_96(history)

    if position exists:
        return

    if cooldown_remaining > 0:
        cooldown_remaining -= 1
        return

    desired_direction = signal

    if desired_direction == 0:
        return

    if previous_signal == desired_direction:
        return

    if recent_8_signals contain -desired_direction:
        return

    if desired_direction == -1 and ret_96 > 0.06:
        return

    if desired_direction == 1 and ret_96 < -0.06:
        return

    if atr_pct <= 0 or atr_pct is missing:
        return

    max_allocation = 3.0
    base_allocation = min(max_allocation, max_allocation * 0.004 / atr_pct)
    allocation = base_allocation * risk_multiplier

    if allocation <= 0:
        return

    stop_pct = clamp(atr_pct * 5.0, 0.025, 0.035)
    take_pct = clamp(atr_pct * 6.0, 0.025, 0.035)

    entry_price = submit_market_order(desired_direction, allocation)

    if desired_direction == 1:
        stop_price = entry_price * (1.0 - stop_pct)
        take_price = entry_price * (1.0 + take_pct)
    else:
        stop_price = entry_price * (1.0 + stop_pct)
        take_price = entry_price * (1.0 - take_pct)

    submit_reduce_only_stop_market(stop_price, mark_price_trigger)
    submit_reduce_only_take_market(take_price, mark_price_trigger)

on_position_closed(exit_reason):
    cancel_remaining_protective_orders()

    if exit_reason == "stop":
        risk_multiplier = max(0.125, risk_multiplier * 0.5)
    else if exit_reason == "take":
        risk_multiplier = 1.0

    cooldown_remaining = 8
```

## 16. 当前代码对应关系

当前 Python 策略参数来源：

- `src/strategy_lab/strategies/candle_count_short/strategy.py`
- `src/strategy_lab/strategies/candle_count_short/intrabar_backtest.py`

当前因子定义来源：

- `src/strategy_lab/data/factors/momentum.py`

当前 workflow 默认成本：

- `fee_bps = 4.5`
- `slippage_bps = 4.0`

这些对应 Hyperliquid 回测口径：

```text
fee_rate = 0.00045
slippage_rate = 0.0004
```
