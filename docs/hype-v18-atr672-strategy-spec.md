# HYPE V18 ATR672 稳健版策略规格

本文档用于实现 HYPE 15m V18 实盘策略。目标是让另一个 AI 或工程师只看这份文档，就能在 Rust 中实现与当前 Python 回测口径一致的版本。

## 1. 策略概要

- 策略名称：`HYPE V18 ATR672 稳健版`
- 交易标的：`HYPE/USDT:USDT` 永续合约
- 回测数据源：Binance `HYPEUSDT` USDT 永续 15m K 线、mark price K 线、funding rates
- 周期：`15m`
- 策略类型：K 线颜色计数反转策略
- 交易方向：多空双向
- 最大名义仓位：
  - 做多最大 `3.0x` 账户权益
  - 做空最大 `3.0x` 账户权益
- 核心信号：
  - 最近 10 根 15m K 线中，阳线数量大于等于 8：做空
  - 最近 10 根 15m K 线中，阴线数量大于等于 8：做多
- 仓位、止盈、止损全部使用 `ATR672`
- `ATR672` 在 15m 周期上等于 7 天 ATR，因为 `672 / 96 = 7`
- 24h 趋势禁入阈值为 `5%`
- 止盈和止损百分比均限制在 `2.5% - 3.5%`
- 无硬性最大持仓时间，持仓只通过止盈或止损退出

实盘实现时必须只使用已经收盘的 15m K 线，不允许使用正在形成的当前 K 线生成信号。

## 2. 与 V13 / V15 的区别

V18 是 V15 的 ATR 拉长版本，也是 V13 的更进攻/更平滑变体。

| 项目 | V13 | V15 | V18 |
|---|---:|---:|---:|
| 信号 | 10根里8根同色反转 | 同 V13 | 同 V13 |
| 最大杠杆 | 3x | 3x | 3x |
| 仓位 ATR | ATR288 | ATR384 | ATR672 |
| 止盈 ATR | ATR288 | ATR384 | ATR672 |
| 止损 ATR | ATR288 | ATR384 | ATR672 |
| 24h 趋势禁入 | 6% | 5% | 5% |
| 止盈止损限制 | 2.5%-3.5% | 2.5%-3.5% | 2.5%-3.5% |
| 定位 | 主线稳健版 | 进攻版 | V15 的更平滑稳健版 |

## 3. 完整参数表

| 参数 | 值 | 说明 |
|---|---:|---|
| `symbol` | `HYPE/USDT:USDT` | HYPE USDT 永续合约。不同交易所可映射为对应 instrument id |
| `timeframe` | `15m` | 信号周期 |
| `lookback` | `10` | 统计最近 10 根已收盘 K 线 |
| `min_count` | `8` | 阳线或阴线数量触发阈值 |
| `bullish_signal_direction` | `-1` | 阳线数量大于等于 8 时做空 |
| `bearish_signal_direction` | `1` | 阴线数量大于等于 8 时做多 |
| `long_allocation` | `3.0` | 做多最大名义仓位，等于账户权益的 3 倍 |
| `short_allocation` | `3.0` | 做空最大名义仓位，等于账户权益的 3 倍 |
| `allocation_atr_window` | `672` | 仓位使用 ATR672 |
| `target_atr_pct` | `0.004` | 目标 ATR，占价格 0.4% |
| `stop_loss_atr_window` | `672` | 止损使用 ATR672 |
| `stop_loss_atr_multiplier` | `5.0` | 动态止损距离等于 ATR672 百分比乘以 5 |
| `min_stop_loss_pct` | `0.025` | 止损下限 2.5% |
| `max_stop_loss_pct` | `0.035` | 止损上限 3.5% |
| `take_profit_atr_window` | `672` | 止盈使用 ATR672 |
| `take_profit_atr_multiplier` | `6.0` | 动态止盈距离等于 ATR672 百分比乘以 6 |
| `min_take_profit_pct` | `0.025` | 止盈下限 2.5% |
| `max_take_profit_pct` | `0.035` | 止盈上限 3.5% |
| `trend_window_bars` | `96` | 24 小时趋势过滤窗口，96 根 15m K 线 |
| `trend_block_pct` | `0.05` | 24 小时涨跌幅禁入阈值，5% |
| `entry_mode` | `signal_start` | 只在信号刚出现时开仓，不在连续同向信号中重复开仓 |
| `opposite_signal_gap_bars` | `8` | 最近 8 根 K 线出现过反向信号则不新开仓 |
| `cooldown_bars` | `8` | 每次平仓后冷却 8 根 K 线，即 2 小时 |
| `stop_loss_risk_multiplier` | `0.5` | 每次止损后，下一次开仓风险倍率减半 |
| `min_risk_multiplier` | `0.125` | 风险倍率最低降到 12.5% |
| `fee_rate` | `0.00045` | 回测使用 taker 费率 0.045% |
| `slippage_rate` | `0.0004` | 回测使用滑点估计 0.04% |
| `total_cost_rate_per_side` | `0.00085` | 单边成本，手续费加滑点 |

如果实盘交易所费率或滑点不同，应以实盘环境为准；但为了复现当前回测，应使用上表成本参数。

## 4. Rust 配置示例

字段名可以按项目风格调整，但语义必须保持一致。

```rust
#[derive(Debug, Clone)]
pub struct HypeV18Config {
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

impl Default for HypeV18Config {
    fn default() -> Self {
        Self {
            symbol: "HYPE/USDT:USDT".to_string(),
            timeframe: "15m".to_string(),
            lookback: 10,
            min_count: 8,
            long_allocation: 3.0,
            short_allocation: 3.0,
            allocation_atr_window: 672,
            target_atr_pct: 0.004,
            stop_loss_atr_window: 672,
            stop_loss_atr_multiplier: 5.0,
            min_stop_loss_pct: 0.025,
            max_stop_loss_pct: 0.035,
            take_profit_atr_window: 672,
            take_profit_atr_multiplier: 6.0,
            min_take_profit_pct: 0.025,
            max_take_profit_pct: 0.035,
            trend_window_bars: 96,
            trend_block_pct: 0.05,
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

## 5. K 线和指标定义

### 5.1 K 线字段

每根 15m K 线至少需要：

- `timestamp`
- `open`
- `high`
- `low`
- `close`
- `mark_high`
- `mark_low`
- `funding_rate`

字段用途：

- `open/high/low/close` 用于计算信号、ATR、趋势过滤和持仓盯市。
- `mark_high/mark_low` 用于触发止盈止损。
- `funding_rate` 用于回测资金费；实盘由交易所实际结算。

如果实盘无法拿到 15m 的 `mark_high/mark_low`，应使用交易所原生的 mark price trigger stop/take order，而不是用普通成交价触发。

### 5.2 阳线和阴线

```text
bullish = close > open
bearish = close < open
doji    = close == open
```

十字线既不计入阳线，也不计入阴线。

### 5.3 阳线和阴线计数

在每根已收盘 K 线 `t` 上：

```text
bullish_count_10[t] = 最近 10 根已收盘 K 线中 bullish 的数量，包含 t
bearish_count_10[t] = 最近 10 根已收盘 K 线中 bearish 的数量，包含 t
```

如果历史 K 线不足 10 根，不产生信号。

### 5.4 ATR672 百分比

真实波幅 `TR`：

```text
previous_close[t] = close[t - 1]

TR[t] = max(
    high[t] - low[t],
    abs(high[t] - previous_close[t]),
    abs(low[t] - previous_close[t])
)
```

ATR672：

```text
ATR672[t] = 最近 672 根 TR 的简单移动平均，包含 t
```

ATR672 百分比：

```text
atr_pct_672[t] = ATR672[t] / close[t]
```

如果历史不足 672 根有效 TR，或者 `atr_pct_672 <= 0`，本根 K 线不允许开仓。

建议实盘启动时预热至少 `700` 根 15m K 线。更稳妥的实盘预热为 `800-1000` 根。

### 5.5 24 小时趋势收益

```text
ret_96[t] = close[t] / close[t - 96] - 1
```

因为 96 根 15m K 线等于 24 小时。如果历史不足 96 根，趋势过滤值为空，本根 K 线不允许开仓。

## 6. 信号生成

每根 15m K 线收盘后，按如下规则生成原始信号：

```text
if bullish_count_10 >= 8:
    signal = -1   // 做空
else if bearish_count_10 >= 8:
    signal = 1    // 做多
else:
    signal = 0    // 无信号
```

方向定义：

```text
1  = long
-1 = short
0  = flat / no signal
```

## 7. 入场过滤

只有当前没有持仓时才允许开仓。持仓期间忽略所有新信号，不加仓、不减仓、不反手。

### 7.1 signal_start 过滤

`entry_mode = signal_start` 表示只在信号刚出现时开仓。

如果当前信号方向和上一根 K 线信号方向相同，则不允许开仓：

```text
if signal[t] == signal[t - 1] and signal[t] != 0:
    reject_entry
```

### 7.2 反向信号间隔过滤

如果最近 8 根 K 线中出现过反向信号，则不允许开仓：

```text
recent = signal[t - 8], ..., signal[t - 1]

if desired_direction == 1 and any(recent == -1):
    reject_long

if desired_direction == -1 and any(recent == 1):
    reject_short
```

### 7.3 24 小时趋势禁入过滤

V18 使用 `5%` 的 24h 趋势禁入。

```text
ret_96[t] = close[t] / close[t - 96] - 1
```

开空过滤：

```text
if desired_direction == -1 and ret_96[t] > 0.05:
    reject_short
```

开多过滤：

```text
if desired_direction == 1 and ret_96[t] < -0.05:
    reject_long
```

解释：

- 过去 24h 涨幅超过 `+5%`，禁止逆势做空。
- 过去 24h 跌幅超过 `-5%`，禁止逆势做多。
- 这个过滤不禁止顺势方向。

### 7.4 平仓后冷却

每次止盈或止损平仓后，进入 8 根 K 线冷却期。

```text
cooldown_remaining = 8
```

冷却期间不允许开新仓。每处理完一根 K 线，`cooldown_remaining -= 1`，直到归零。

## 8. 动态仓位计算

基础最大仓位：

```text
max_allocation = 3.0
```

ATR 动态仓位：

```text
base_allocation = min(
    max_allocation,
    max_allocation * target_atr_pct / atr_pct_672[t]
)
```

其中：

```text
target_atr_pct = 0.004
```

连续止损风险倍率：

```text
effective_allocation = base_allocation * risk_multiplier
```

初始：

```text
risk_multiplier = 1.0
```

止损后：

```text
risk_multiplier = max(0.125, risk_multiplier * 0.5)
```

止盈后：

```text
risk_multiplier = 1.0
```

名义下单金额：

```text
notional = account_equity_usdt * effective_allocation
```

下单张数或币数量由交易所合约规格决定：

```text
quantity = notional / entry_price
```

实盘必须按交易所的最小下单单位、价格精度、数量精度、最大杠杆、保证金模式进行取整和校验。

## 9. 止盈止损计算

动态止损百分比：

```text
raw_stop_pct = atr_pct_672[t] * 5.0
stop_loss_pct = clamp(raw_stop_pct, 0.025, 0.035)
```

动态止盈百分比：

```text
raw_take_pct = atr_pct_672[t] * 6.0
take_profit_pct = clamp(raw_take_pct, 0.025, 0.035)
```

`clamp(x, min, max)` 定义：

```text
if x < min: return min
if x > max: return max
else: return x
```

### 9.1 多单保护价

```text
long_stop_price = entry_price * (1 - stop_loss_pct)
long_take_price = entry_price * (1 + take_profit_pct)
```

### 9.2 空单保护价

```text
short_stop_price = entry_price * (1 + stop_loss_pct)
short_take_price = entry_price * (1 - take_profit_pct)
```

实盘下单后应立即挂 reduce-only 的止损和止盈保护单，触发源应优先使用 mark price。

## 10. 回测处理顺序

Python 回测口径按每根 15m K 线顺序处理。Rust 回测若要对齐，应使用同样顺序。

每根 K 线 `t`：

1. 如果上一根已有持仓，先检查本根 `mark_high/mark_low` 是否触发止损或止盈。
2. 若持仓未平仓，用 close-to-close 收益更新权益。
3. 若有持仓，计入本根 funding PnL。
4. 若本根触发平仓，则：
   - 计算止损/止盈退出 PnL。
   - 扣除退出单边成本。
   - 如果是止损，风险倍率减半。
   - 如果是止盈，风险倍率恢复为 1。
   - 设置 8 根 K 线冷却。
   - 本根不再开新仓。
5. 如果当前无仓、无冷却、未刚刚平仓，则基于本根已收盘 K 线信号尝试开仓。
6. 开仓时扣除入场单边成本。
7. 记录本根权益、仓位、风险状态。

### 10.1 同一根 K 同时触发止损和止盈

为了保守，回测中优先判定止损。

多单：

```text
if mark_low <= stop_price:
    stop
else if mark_high >= take_price:
    take
```

空单：

```text
if mark_high >= stop_price:
    stop
else if mark_low <= take_price:
    take
```

实盘中应由交易所条件单实际触发结果决定。

## 11. 成本和资金费

回测中每次入场和出场都扣除：

```text
cost = allocation * (fee_rate + slippage_rate)
```

默认：

```text
fee_rate = 0.00045
slippage_rate = 0.0004
total_cost_rate_per_side = 0.00085
```

资金费按持仓方向计入：

```text
funding_pnl = -direction * allocation * funding_rate
```

解释：

- 多单 `direction = 1`
- 空单 `direction = -1`
- funding rate 为正时，多单支付、空单收取。
- funding rate 为负时，多单收取、空单支付。

实盘中资金费由交易所实际结算，不需要手动下单；但本地记账应同步计入权益变化。

## 12. 实盘状态变量

Rust 实盘程序至少需要持久化以下状态：

```rust
#[derive(Debug, Clone)]
pub struct StrategyState {
    pub position_direction: i8,      // 1 long, -1 short, 0 flat
    pub entry_price: f64,
    pub effective_allocation: f64,
    pub stop_loss_pct: f64,
    pub take_profit_pct: f64,
    pub risk_multiplier: f64,
    pub cooldown_remaining: usize,
    pub last_processed_bar_ts: i64,
    pub last_entry_bar_ts: Option<i64>,
    pub last_exit_bar_ts: Option<i64>,
}
```

启动时必须从交易所查询真实持仓，并与本地状态对齐：

- 如果交易所有仓、本地无仓：以交易所仓位为准，重建保护单或停止程序等待人工处理。
- 如果本地有仓、交易所无仓：清空本地仓位状态，检查是否为手动平仓或保护单触发。
- 如果保护单缺失：立即补挂，或暂停策略。

## 13. 实盘下单语义

### 13.1 K 线收盘后的入场时机

策略使用第 `t` 根已收盘 K 线生成信号。实盘推荐：

```text
第 t 根 15m K 线收盘
-> 等交易所确认该 K 线已 closed
-> 用第 t 根 close 和指标生成决策
-> 如果允许开仓，在下一根 K 线开始后尽快下市价单
```

也就是说，不应在 K 线未收盘时提前下单。

### 13.2 订单类型

入场：

- 市价单或可控滑点的 IOC/marketable limit order。
- 回测按 taker 成本处理，所以实盘也应假设 taker。

保护单：

- 止损：reduce-only trigger market。
- 止盈：reduce-only trigger market 或 reduce-only limit/trigger。
- 触发源：优先 mark price。

### 13.3 保证金和杠杆

建议使用逐仓。

实际交易所杠杆设置应大于等于策略最大名义仓位需求，但下单大小必须按策略计算的 `notional` 控制，不应因为交易所杠杆设置更高而扩大仓位。

## 14. 回测基准结果

以下结果基于更新后的本地 HYPE 数据湖：

- OHLCV：`2025-05-30 10:30 UTC` 到 `2026-05-19 09:00 UTC`
- Mark price：`2025-05-30 09:30 UTC` 到 `2026-05-19 09:00 UTC`
- Funding：`2025-05-30 12:00 UTC` 到 `2026-05-19 08:00 UTC`

固定窗口结果：

| 窗口 | 收益 | 最大回撤 | 开仓 | 止损 / 止盈 | 均仓 |
|---|---:|---:|---:|---:|---:|
| 1周 | `-0.33%` | `-13.60%` | `7` | `4 / 3` | `0.69x` |
| 1月 | `+14.87%` | `-21.42%` | `22` | `9 / 13` | `1.01x` |
| 3个月 | `+221.07%` | `-21.42%` | `73` | `23 / 50` | `0.99x` |
| 1年 | `+838.25%` | `-27.96%` | `310` | `124 / 186` | `0.59x` |

1年详细：

```text
return      = +838.25%
max_drawdown = -27.96%
entries     = 310
long / short = 153 / 157
stops / takes = 124 / 186
avg_allocation = 0.5947x
max_allocation = 2.8989x
blocked_by_24h_trend = 145
costs = 0.6160
funding_pnl = -0.0114
```

## 15. 实盘安全建议

V18 是参数优化后的 HYPE 专用品种候选，存在过拟合风险。实盘建议：

- 先用 dry-run 或小资金跑至少 1-2 周。
- 设置单笔最大名义金额上限。
- 设置每日最大亏损上限。
- 检查保护单是否与实际持仓一致。
- 每根 15m K 线只处理一次，使用 `last_processed_bar_ts` 防止重复下单。
- 若交易所 API 延迟、断线、保护单失败，应暂停新开仓。
- 若本地状态与交易所状态不一致，应停止交易并等待人工确认。

## 16. 最小伪代码

```text
on_closed_15m_bar(bar):
    append bar to history
    if history not enough for ATR672 or ret96:
        return

    sync_exchange_position()
    ensure_protection_orders_if_position_exists()

    if just_processed(bar.ts):
        return

    if position is open:
        // 实盘中主要由交易所保护单触发
        record_mark_to_market()
        return

    if cooldown_remaining > 0:
        cooldown_remaining -= 1
        mark_processed(bar.ts)
        return

    signal = compute_candle_count_signal(history, lookback=10, min_count=8)
    if signal == 0:
        mark_processed(bar.ts)
        return

    if signal == previous_signal:
        mark_processed(bar.ts)
        return

    if recent_8_bars_contains_opposite_signal(signal):
        mark_processed(bar.ts)
        return

    ret96 = close[t] / close[t - 96] - 1
    if signal == short and ret96 > 0.05:
        mark_processed(bar.ts)
        return
    if signal == long and ret96 < -0.05:
        mark_processed(bar.ts)
        return

    atr_pct = atr672 / close[t]
    base_allocation = min(3.0, 3.0 * 0.004 / atr_pct)
    effective_allocation = base_allocation * risk_multiplier

    stop_pct = clamp(atr_pct * 5.0, 0.025, 0.035)
    take_pct = clamp(atr_pct * 6.0, 0.025, 0.035)

    submit_market_entry(signal, effective_allocation)
    submit_reduce_only_stop_and_take(signal, stop_pct, take_pct, mark_price_trigger=true)
    persist_state()
    mark_processed(bar.ts)
```
