# HYPE V30 可复现参数说明

本文档对应当前研究台账里的 **HYPE 趋势突破族 V30**：

```text
V30 = V29 去掉 DI 反向指标退出，只保留 ADX<22 指标退出
```

不要和旧的反向 K 系列 `hype-v29-reproducible-params.md` 混用；这里的 V30 是 15m 趋势突破策略。

## 1. 参数总表

```yaml
strategy_id: hype_v30
symbol: HYPE/USDT:USDT
timeframe: 15m

data:
  ohlcv_exchange: binance
  market_type: perp
  funding_exchange: binance
  backtest_end: 2026-06-01 03:00:00 UTC
  warmup_min_bars: 1600

execution:
  canonical_timing: next_bar_open
  signal_bar: t
  signal_calculation: bar_t_close
  entry_execution: bar_t_plus_1_open
  stop_take_execution: intrabar_high_low_after_entry
  legacy_lag1_close_backtest: deprecated_reference_only

features:
  ema_fast: 96
  ema_slow: 384
  adx_window: 28
  volume_window: 192
  atr_window_for_sizing_and_exits: 672
  one_hour_adx_window: 21
  one_hour_ema_fast: 24
  one_hour_ema_slow: 96

entry:
  long:
    ema_spread_min: 0.0
    adx_min: 28
    volume_surge_min: 0.25
    one_hour_confirm: adx_di
    use_di_entry_filter: false
  short:
    ema_spread_max: 0.0
    adx_min: 36
    volume_surge_min: 0.50
    one_hour_confirm: bear_ema
    use_di_entry_filter: false

sizing:
  long_target_atr_pct: 0.016
  short_target_atr_pct: 0.014
  max_allocation: 3.0
  use_drawdown_scale: false

exits:
  take_profit_atr: 4.30
  hard_stop_atr: 9.00
  indicator_exit:
    type: adx_only
    adx_exit: 22
    delayed_bars: 3
    disable_after_mfe_atr: 2.0
  max_hold_bars: 192
  cooldown_bars: 16
  use_trailing_stop: false
  use_ema_exit: false
  use_di_reverse_exit: false

costs:
  trade_cost_rate: 0.00085
  funding: true
```

## 2. 数据口径

| 项目 | 值 |
|---|---:|
| 主回测交易所 | Binance `HYPE/USDT:USDT` 永续 |
| K线周期 | `15m` |
| 使用字段 | `open/high/low/close/volume` |
| Funding | Binance funding rate |
| 主回测统计区间 | 预热后约 `2025-06-16` 至 `2026-06-01 03:00 UTC` |
| 成本 | 每次成交按 `0.00085 * allocation` 扣权益 |

说明：

```text
1. 可执行口径：在第 `t` 根 15m K 收盘后计算信号，在第 `t+1` 根 K 的 open 执行。
2. 1h 数据由 15m resample 得到，resample(rule="1h", label="left", closed="left")。
3. 1h 指标先 shift(1)，再 forward-fill 对齐到 15m。
4. ATR672 用于仓位、止盈、止损距离；当前研究回测使用开仓 bar 的 entry ATR 固定止盈止损。
5. 旧研究口径 `shift(1) + close[t]` 只作为 legacy 参考，不作为实盘可复现主基准。
```

## 3. 指标计算

### 3.1 EMA

```text
ema_n = close.ewm(span=n, adjust=false, min_periods=n).mean()

ema_fast = EMA96
ema_slow = EMA384
ema_spread = EMA96 / EMA384 - 1
```

### 3.2 ATR 百分比

```text
true_range = max(
  high - low,
  abs(high - previous_close),
  abs(low - previous_close)
)

ATR672 = true_range.rolling(672, min_periods=672).mean()
atr_pct_672 = ATR672 / close
```

### 3.3 ADX / DI

```text
up_move = high.diff()
down_move = -low.diff()

plus_dm  = up_move   if up_move > down_move and up_move > 0 else 0
minus_dm = down_move if down_move > up_move   and down_move > 0 else 0

atr_w = true_range.ewm(alpha=1/window, adjust=false, min_periods=window).mean()
plus_di  = 100 * ewm(plus_dm,  alpha=1/window) / atr_w
minus_di = 100 * ewm(minus_dm, alpha=1/window) / atr_w
dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
adx = ewm(dx, alpha=1/window)
```

V30 使用：

```text
15m ADX window = 28
1h  ADX window = 21
```

### 3.4 成交量放大

```text
volume_surge_192 = volume / rolling_mean(volume, 192) - 1
```

## 4. 入场规则

### 4.1 多单入场

在没有持仓、冷却结束、ATR 有效时：

```text
long_entry =
  ema_spread > 0
  and adx_28 >= 28
  and volume_surge_192 >= 0.25
  and one_hour_adx_di_confirm
```

1h 多头确认：

```text
one_hour_adx_di_confirm =
  1h_adx_21 > 18
  and 1h_plus_di_21 > 1h_minus_di_21
```

### 4.2 空单入场

```text
short_entry =
  ema_spread < 0
  and adx_28 >= 36
  and volume_surge_192 >= 0.50
  and one_hour_bear_ema_confirm
```

1h 空头确认：

```text
one_hour_bear_ema_confirm =
  1h_EMA24 / 1h_EMA96 - 1 < 0
```

### 4.3 入场冲突

```text
if long_entry and not short_entry:
    open long
elif short_entry and not long_entry:
    open short
else:
    no entry
```

V30 明确不使用：

```text
DI 入场过滤: 不要求 plus_di > minus_di 才做多
DI 入场过滤: 不要求 minus_di > plus_di 才做空
Keltner 突破: 不使用
EMA96 slope: 不使用
```

## 5. 仓位规则

第 `t` 根 K 收盘产生入场信号后，在第 `t+1` 根 K 的 open 开仓，并记录：

```text
signal_price = close[t]
entry_price = open[t + 1]
entry_atr_pct = atr_pct_672[t]
```

多单仓位：

```text
long_allocation = min(3.0, 0.016 / entry_atr_pct)
```

空单仓位：

```text
short_allocation = min(3.0, 0.014 / entry_atr_pct)
```

V30 不使用账户回撤降仓：

```text
use_drawdown_scale = false
```

## 6. 止盈止损

V30 使用固定 entry ATR。开仓后止盈止损距离不随后续 ATR 变化。

### 6.1 多单

```text
long_take_price = entry_price * (1 + 4.30 * entry_atr_pct)
long_stop_price = entry_price * (1 - 9.00 * entry_atr_pct)
```

### 6.2 空单

```text
short_take_price = entry_price * (1 - 4.30 * entry_atr_pct)
short_stop_price = entry_price * (1 + 9.00 * entry_atr_pct)
```

同一根 15m K 同时触发时，回测优先级：

```text
hard_stop > take_profit > indicator_exit > timeout
```

## 7. 指标退出

V30 是 `ADX exit only`：

```text
raw_indicator_exit = adx_28 < 22
```

需要连续 3 根满足才退出：

```text
if raw_indicator_exit:
    indicator_exit_streak += 1
else:
    indicator_exit_streak = 0

indicator_exit = indicator_exit_streak >= 3
```

但单笔浮盈达到 `2ATR` 后，关闭指标退出：

```text
long_mfe_pct = highest_high_since_entry / entry_price - 1
short_mfe_pct = entry_price / lowest_low_since_entry - 1

if mfe_pct >= 2.0 * entry_atr_pct:
    disable_indicator_exit = true
```

关闭后：

```text
indicator_exit = false
```

V30 明确不使用：

```text
DI 反向退出: 不使用
EMA 反向退出: 不使用
trailing stop: 不使用
```

## 8. Timeout 与冷却

最大持仓：

```text
max_hold_bars = 192  # 48 小时
```

任意平仓后冷却：

```text
cooldown_bars = 16  # 4 小时
```

冷却期间不允许新开仓。

## 9. PnL 与费用

多单每根 K 的收益：

```text
pnl = allocation * (current_price / previous_price - 1)
pnl -= allocation * funding_rate[t]
```

空单每根 K 的收益：

```text
pnl = allocation * (previous_price / current_price - 1)
pnl += allocation * funding_rate[t]
```

成交成本：

```text
equity *= 1 - 0.00085 * allocation
```

当前回测实现中，开仓和平仓各扣一次上述成本。

## 10. 回测执行伪代码

```python
for each completed 15m bar t:
    calculate indicators and signals using bar[t] close

    if position != 0:
        update indicator_exit_streak using adx_28[t] < 22
        if mfe_since_entry >= 2 * entry_atr_pct:
            disable_indicator_exit = True
        if indicator_exit_streak >= 3 and not disable_indicator_exit:
            queue exit at open[t + 1]
        if hold_bars >= 192:
            queue timeout exit at open[t + 1]

    if position == 0 and cooldown == 0:
        if long_entry[t] and not short_entry[t]:
            queue long entry at open[t + 1]
            queued_entry_atr = atr_pct_672[t]
        elif short_entry[t] and not long_entry[t]:
            queue short entry at open[t + 1]
            queued_entry_atr = atr_pct_672[t]

for each execution bar t + 1:
    execute queued entry / queued indicator exit at open[t + 1]
    after entry, evaluate hard_stop and take_profit with that bar high/low
    any completed exit pays cost and starts cooldown = 16
```

## 11. Binance 主基准结果

当前应以可执行口径为主：`bar[t] close 生成信号 -> bar[t+1] open 成交`。

| 指标 | 值 |
|---|---:|
| 收益 | `+456.51%` |
| 最大回撤 | `-34.30%` |
| Sharpe | `3.01` |
| 交易数 | `79` |
| 胜率 | `75.64%` |
| 止盈 / 指标或 timeout / 止损 | `54 / 17 / 7` |

旧研究口径对照：

| 口径 | 收益 | 最大回撤 | 说明 |
|---|---:|---:|---|
| 可执行 next-open | `+456.51%` | `-34.30%` | 主基准 |
| Legacy `shift(1)+close[t]` | `+2188.01%` | `-16.36%` | 只作研究上限，不作实盘复现基准 |

## 12. 跨交易所复现备注

实盘或跨交易所验证可映射为：

```text
Hyperliquid: HYPE/USDC:USDC
OKX:         HYPE/USDT:USDT
```

可执行 next-open 口径最近复跑结果：

| 数据源 | 收益 | 最大回撤 | Sharpe |
|---|---:|---:|---:|
| Binance V30 | `+456.51%` | `-34.30%` | `3.01` |
| Hyperliquid V30 | `+189.92%` | `-41.29%` | `2.16` |
| OKX V30 | `+362.01%` | `-36.07%` | `2.57` |

跨交易所数据窗口、funding 完整度不同，不能直接当作严格同区间排名。
