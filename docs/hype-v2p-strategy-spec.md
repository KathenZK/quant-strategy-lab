# HYPE V2P 趋势突破策略说明

这份文档给同事和 AI 复现用。核心目标是把 V2P 讲清楚：它在什么行情开仓、怎么控制仓位、怎么止盈止损、做多和做空哪里不一样。

## 1. 一句话说明

V2P 是一个 **15m 趋势突破 + 1h 趋势确认** 的 HYPE 永续合约策略。

大白话讲：

- 它不是低吸回调。
- 它是等价格已经突破通道，趋势已经变强，再顺势追进去。
- 做多时，要求 15m 已经向上突破，而且 1h 也在多头趋势里。
- 做空时，要求更严格，因为 HYPE 空头容易被反抽，所以空头必须更强下跌、更强放量、更明确弱势才开。

## 2. 当前状态

V2P 是 V2O 周边参数重扫得到的高收益候选。

回测口径：

- 标的：Binance `HYPE/USDT:USDT` 永续
- 主周期：`15m`
- 高周期确认：`1h`
- 数据：本地 Binance HYPE/USDT 永续 OHLCV + funding
- 成本：研究脚本里 `ROUND_TRIP_COST = 0.00085`
- 注意：当前脚本实现是在开仓和平仓各扣一次 `0.00085 * 仓位`
- funding：多单扣 funding，空单加 funding
- warmup：前 `1600` 根 15m K 线只用于指标预热，不参与正式统计

当前主回测结果：

| 指标 | V2P |
|---|---:|
| 1y 收益 | `+361.02%` |
| 最大回撤 | `-13.89%` |
| Sharpe | `约 3.9` |
| 总交易数 | `76` |
| 做多次数 | `58` |
| 做空次数 | `18` |
| 总胜率 | `64.47%` |
| 做多胜率 | `68.97%` |
| 做空胜率 | `50.00%` |

## 3. 策略直觉

### 3.1 为什么用突破

HYPE 有很强的趋势段。V2P 不试图预测底部，也不在普通震荡里频繁交易。

它只在这种场景进场：

- 价格突破 Keltner 通道
- EMA 快线在慢线上方或下方
- ADX 表示趋势强度足够
- DI 方向和交易方向一致
- 成交量有放大
- 1h 方向不逆着当前交易

这相当于问一句：

> “现在是不是已经走出一段像样的趋势了？”

如果答案是是，就顺势进场。

### 3.2 为什么做空更严格

V2P 不是多空完全对称。

原因很简单：HYPE 的上涨 squeeze 和反抽很猛，空头如果按多头同样宽松的条件开，会多出很多质量差的空单。

已经做过镜像测试：

- 当前 V2P：`+361.02% / -13.89% / 76笔`
- 完全镜像空头：`+221.54% / -38.25% / 105笔`

所以空头必须更挑剔。

## 4. 指标定义

所有 15m 入场判断都使用上一根已经收盘的 K 线，避免看未来。

### 4.1 15m 指标

| 指标 | 参数 | 用途 |
|---|---:|---|
| `EMA_fast` | `96` | 趋势快线 |
| `EMA_slow` | `384` | 趋势慢线 |
| `ATR_channel` | `144` | Keltner 通道宽度 |
| `ADX` / `+DI` / `-DI` | `28` | 趋势强度和方向 |
| `volume_surge` | `192` | 成交量是否放大 |
| `ATR_position` | `672` | 仓位大小、止盈止损距离 |

计算方式：

```python
ema_fast = EMA(close, 96)
ema_slow = EMA(close, 384)
atr_channel = ATR(144)
adx, plus_di, minus_di = ADX(28)
volume_surge = volume / rolling_mean(volume, 192) - 1
atr_position = ATR(672) / close
```

为了不看未来，实际用于信号的是：

```python
close_signal = close.shift(1)
ema_fast_signal = ema_fast.shift(1)
ema_slow_signal = ema_slow.shift(1)
atr_channel_signal = atr_channel.shift(1)
adx_signal = adx.shift(1)
plus_di_signal = plus_di.shift(1)
minus_di_signal = minus_di.shift(1)
volume_surge_signal = volume_surge.shift(1)
```

### 4.2 1h 确认

先把 15m K 线 resample 成 1h K 线，再计算 1h 指标，然后对齐回 15m。

多头 1h 确认：

```python
long_confirm_1h = adx_1h_21 > 18 and plus_di_1h_21 > minus_di_1h_21
```

空头 1h 确认：

```python
short_confirm_1h = ema_1h_24 / ema_1h_96 - 1 < 0
```

也就是说：

- 多头要求 1h ADX/DI 也偏多
- 空头只要求 1h EMA 结构偏空

## 5. 完整参数表

| 参数 | V2P 值 | 说明 |
|---|---:|---|
| 主周期 | `15m` | 15m 生成信号和执行 |
| 确认周期 | `1h` | 只做方向过滤 |
| `ema_fast` | `96` | 15m 快 EMA |
| `ema_slow` | `384` | 15m 慢 EMA |
| `atr_channel_window` | `144` | Keltner 通道 ATR |
| `keltner_multiplier` | `2.4` | 通道宽度 |
| `adx_window` | `28` | 15m ADX |
| `adx_min` | `28` | 多头最低 ADX |
| `short_adx_boost` | `8` | 空头额外 ADX 门槛 |
| `volume_window` | `192` | 成交量均线窗口 |
| `min_volume_surge` | `0.25` | 多头成交量放大要求 |
| `short_volume_boost` | `0.25` | 空头额外成交量要求 |
| `adx_exit` | `20` | 趋势变弱退出阈值 |
| `target_atr_pct` | `0.014` | 多头目标波动仓位 |
| `short_target_atr_pct` | `0.012` | 空头目标波动仓位 |
| `max_allocation` | `3.0x` | 多头最大仓位 |
| `short_max_allocation` | `3.0x` | 空头最大仓位 |
| `stop_atr` | `12` | 止损距离 |
| `take_atr` | `4` | 止盈距离 |
| `trail_atr` | `10` | 移动止损距离 |
| `max_hold_bars` | `192` | 最长持仓，约 48 小时 |
| `cooldown_bars` | `16` | 平仓后冷却，约 4 小时 |
| 回撤半仓 | 关闭 | V2P 不使用 V2O 的回撤半仓 |

## 6. 入场规则

### 6.1 多头开仓

满足以下全部条件才开多：

```python
upper_channel = ema_fast_signal + 2.4 * atr_channel_signal

long_entry =
    close_signal > upper_channel
    and ema_fast_signal / ema_slow_signal - 1 > 0
    and ema_fast_signal.pct_change(24) > 0
    and adx_signal >= 28
    and plus_di_signal > minus_di_signal
    and volume_surge_signal >= 0.25
    and long_confirm_1h
```

大白话：

- 价格已经突破上轨
- 中期趋势是向上的
- 快线还在继续往上走
- ADX 说明趋势够强
- `+DI > -DI` 说明上涨力量占优
- 成交量比过去 192 根 15m 均量至少高 25%
- 1h 也确认偏多

### 6.2 空头开仓

满足以下全部条件才开空：

```python
lower_channel = ema_fast_signal - 2.4 * atr_channel_signal

short_entry =
    close_signal < lower_channel
    and ema_fast_signal / ema_slow_signal - 1 < 0
    and ema_fast_signal.pct_change(24) < 0
    and adx_signal >= 36
    and minus_di_signal > plus_di_signal
    and volume_surge_signal >= 0.50
    and short_confirm_1h
```

这里的 `36` 来自：

```python
adx_min + short_adx_boost = 28 + 8
```

这里的 `0.50` 来自：

```python
min_volume_surge + short_volume_boost = 0.25 + 0.25
```

大白话：

- 价格跌破下轨
- EMA 结构已经偏空
- 快线继续向下
- 下跌趋势必须比多头更强
- `-DI > +DI`
- 成交量也必须更明显放大
- 1h EMA 结构必须偏空

### 6.3 多空冲突

如果同一根 K 线同时出现多头和空头信号，不开仓。

实现逻辑：

```python
if long_entry and not short_entry:
    open_long()
elif short_entry and not long_entry:
    open_short()
else:
    do_nothing()
```

## 7. 仓位规则

仓位不是固定 3x，而是按波动率动态计算。

### 7.1 多头仓位

```python
long_allocation = min(3.0, 0.014 / atr_position)
```

例如：

- 如果 `ATR672 / close = 0.007`
- 那么仓位是 `0.014 / 0.007 = 2.0x`

### 7.2 空头仓位

```python
short_allocation = min(3.0, 0.012 / atr_position)
```

空头比多头稍微保守。

例如：

- 如果 `ATR672 / close = 0.007`
- 空头仓位是 `0.012 / 0.007 = 1.71x`

### 7.3 为什么这样做

波动越大，仓位越小；波动越小，仓位越大。

这样可以避免在高波动时期还用满仓杠杆。

## 8. 持仓和退出规则

开仓后最多持有 `192` 根 15m K 线，约 `48` 小时。

持仓期间，每根 15m K 线都检查：

1. 是否打止损
2. 是否打移动止损
3. 是否打止盈
4. 是否指标转弱
5. 是否超时

如果多个条件同时触发，当前脚本优先级是：

```text
止损 > 移动止损 > 止盈 > 指标退出 / 超时
```

### 8.1 多头退出

多头开仓价记为 `entry_price`。

```python
long_stop = entry_price * (1 - 12 * atr_position)
long_take = entry_price * (1 + 4 * atr_position)
long_trail = highest_price_since_entry * (1 - 10 * atr_position)
```

多头退出条件：

```python
stop_hit = low <= long_stop
take_hit = high >= long_take
trail_hit = low <= long_trail and close > entry_price
indicator_exit =
    close_signal < ema_fast_signal
    or minus_di_signal > plus_di_signal
    or adx_signal < 20
timeout = hold_bars >= 192
```

大白话：

- 跌太多，止损
- 涨到 4ATR，止盈
- 涨过之后又从高点回撤 10ATR，移动止损
- 价格跌回 EMA96 下方，或者 DI 转空，或者 ADX 低于 20，说明趋势弱了，退出
- 持仓超过 48 小时还没结果，也退出

### 8.2 空头退出

空头开仓价记为 `entry_price`。

```python
short_stop = entry_price * (1 + 12 * atr_position)
short_take = entry_price * (1 - 4 * atr_position)
short_trail = lowest_price_since_entry * (1 + 10 * atr_position)
```

空头退出条件：

```python
stop_hit = high >= short_stop
take_hit = low <= short_take
trail_hit = high >= short_trail and close < entry_price
indicator_exit =
    close_signal > ema_fast_signal
    or plus_di_signal > minus_di_signal
    or adx_signal < 20
timeout = hold_bars >= 192
```

大白话：

- 空单被拉太多，止损
- 跌到 4ATR，止盈
- 跌过之后又从低点反弹 10ATR，移动止损
- 价格重新站上 EMA96，或者 DI 转多，或者 ADX 低于 20，说明下跌趋势弱了，退出
- 超过 48 小时也退出

## 9. 冷却规则

平仓后进入冷却：

```python
cooldown_bars = 16
```

也就是约 `4` 小时内不立刻重新开仓。

目的：

- 避免刚被震出去又马上追进去
- 降低震荡区间的来回打脸

## 10. 收益计算口径

### 10.1 多头每根 K 的收益

```python
period_return = allocation * (current_price / previous_price - 1)
period_return -= allocation * funding_rate
```

如果平仓，再扣成本：

```python
equity *= 1 - 0.00085 * allocation
```

### 10.2 空头每根 K 的收益

```python
period_return = allocation * (previous_price / current_price - 1)
period_return += allocation * funding_rate
```

如果平仓，也扣成本：

```python
equity *= 1 - 0.00085 * allocation
```

### 10.3 开仓成本

开仓时也扣一次：

```python
equity *= 1 - 0.00085 * allocation
```

所以复现时要注意：当前研究脚本是开仓和平仓都扣一次 `0.00085 * allocation`。

## 11. AI 复现伪代码

下面这段是最小复现逻辑。

```python
for i in range(start_bar, end_bar + 1):
    if position != 0:
        update_hold_bars()
        update_high_water_and_low_water()

        if position == 1:
            stop = entry_price * (1 - 12 * atr_pct_672[i])
            take = entry_price * (1 + 4 * atr_pct_672[i])
            trail = high_water * (1 - 10 * atr_pct_672[i])

            stop_hit = low[i] <= stop
            trail_hit = low[i] <= trail and close[i] > entry_price
            take_hit = high[i] >= take
            indicator_exit = (
                close_signal[i] < ema96_signal[i]
                or minus_di_signal[i] > plus_di_signal[i]
                or adx28_signal[i] < 20
            )
            timeout = hold_bars >= 192

            if stop_hit:
                exit_price = stop
            elif trail_hit:
                exit_price = trail
            elif take_hit:
                exit_price = take
            else:
                exit_price = close[i]

            equity *= 1 + allocation * (exit_price / previous_price - 1)
            equity *= 1 - allocation * funding_rate[i]

        if position == -1:
            stop = entry_price * (1 + 12 * atr_pct_672[i])
            take = entry_price * (1 - 4 * atr_pct_672[i])
            trail = low_water * (1 + 10 * atr_pct_672[i])

            stop_hit = high[i] >= stop
            trail_hit = high[i] >= trail and close[i] < entry_price
            take_hit = low[i] <= take
            indicator_exit = (
                close_signal[i] > ema96_signal[i]
                or plus_di_signal[i] > minus_di_signal[i]
                or adx28_signal[i] < 20
            )
            timeout = hold_bars >= 192

            if stop_hit:
                exit_price = stop
            elif trail_hit:
                exit_price = trail
            elif take_hit:
                exit_price = take
            else:
                exit_price = close[i]

            equity *= 1 + allocation * (previous_price / exit_price - 1)
            equity *= 1 + allocation * funding_rate[i]

        if stop_hit or trail_hit or take_hit or indicator_exit or timeout:
            equity *= 1 - 0.00085 * allocation
            position = 0
            allocation = 0
            cooldown = 16

        previous_price = close[i]

    if position == 0:
        if cooldown > 0:
            cooldown -= 1
            continue

        if long_entry[i] and not short_entry[i]:
            position = 1
            allocation = min(3.0, 0.014 / atr_pct_672[i])
            entry_price = close[i]
            previous_price = close[i]
            high_water = high[i]
            low_water = low[i]
            hold_bars = 0
            equity *= 1 - 0.00085 * allocation

        elif short_entry[i] and not long_entry[i]:
            position = -1
            allocation = min(3.0, 0.012 / atr_pct_672[i])
            entry_price = close[i]
            previous_price = close[i]
            high_water = high[i]
            low_water = low[i]
            hold_bars = 0
            equity *= 1 - 0.00085 * allocation
```

## 12. 参数 JSON

可以把下面这份 JSON 丢给 AI 或回测框架生成策略。

```json
{
  "name": "HYPE_V2P",
  "symbol": "HYPE/USDT:USDT",
  "exchange": "binance",
  "market_type": "perp",
  "signal_timeframe": "15m",
  "confirm_timeframe": "1h",
  "ema_fast": 96,
  "ema_slow": 384,
  "atr_channel_window": 144,
  "atr_position_window": 672,
  "keltner_multiplier": 2.4,
  "adx_window": 28,
  "adx_min": 28,
  "short_adx_boost": 8,
  "volume_window": 192,
  "min_volume_surge": 0.25,
  "short_volume_boost": 0.25,
  "long_confirm_1h": {
    "adx_window": 21,
    "adx_min": 18,
    "condition": "plus_di > minus_di"
  },
  "short_confirm_1h": {
    "ema_fast": 24,
    "ema_slow": 96,
    "condition": "ema_fast / ema_slow - 1 < 0"
  },
  "target_atr_pct": 0.014,
  "short_target_atr_pct": 0.012,
  "max_allocation": 3.0,
  "short_max_allocation": 3.0,
  "stop_atr": 12,
  "take_atr": 4,
  "trail_atr": 10,
  "adx_exit": 20,
  "max_hold_bars": 192,
  "cooldown_bars": 16,
  "round_trip_cost_variable": 0.00085,
  "cost_implementation": "charge 0.00085 * allocation on entry and again on exit",
  "drawdown_position_scale": false
}
```

## 13. 注意事项

V2P 虽然收益高、回撤小，但不是无脑主线。

当前判断：

- 优点：收益高，回撤控制好，成本压力下仍能跑。
- 优点：90天滚动窗口全部为正。
- 风险：参数比 V2O 更多，拟合风险中等。
- 风险：空头只有 18 笔，空头参数更容易过拟合。
- 风险：Train 段不如 V2O，说明它更依赖后半段行情。

建议：

- 可以作为高收益候选继续跟踪。
- 不建议继续细调空头参数。
- 不建议改成完全多空对称。
- 不建议改成只做多。
- 如果要实盘或 dry-run，先用最近新增数据做 walk-forward 跟踪。
