# HYPE 15m V21 复现参数

这份文档用于让同事只按参数和规则即可复现 HYPE V21 回测。

## 1. 数据口径

| 项目 | 值 |
|---|---|
| 交易所 | Binance Futures |
| 合约 | `HYPEUSDT` USDT 永续 |
| 统一 symbol | `HYPE/USDT:USDT` |
| 周期 | `15m` |
| OHLCV | Binance futures trade kline |
| 止盈止损触发 | Binance futures mark price kline 的 `mark_high` / `mark_low` |
| 资金费 | Binance futures funding rate |
| 本地最新数据 | `2025-05-30 10:30 UTC` 到 `2026-05-28 12:30 UTC` |

每根 K 线字段至少需要：

```text
ts, open, high, low, close, mark_high, mark_low, funding_rate
```

## 2. 成本参数

| 参数 | 值 |
|---|---:|
| `fee_rate` | `0.00045` |
| `slippage_rate` | `0.00040` |
| `total_cost_rate_per_side` | `0.00085` |

开仓和平仓各收一次 `total_cost_rate_per_side * 当前名义仓位`。

## 3. 信号参数

| 参数 | 值 |
|---|---:|
| `lookback` | `10` |
| `min_count` | `8` |
| `bullish_signal_direction` | `-1` |
| `bearish_signal_direction` | `1` |

K 线颜色：

```text
bullish = close > open
bearish = close < open
doji    = close == open
```

信号：

```text
最近 10 根已收盘 K 线中 bullish_count >= 8 -> 做空
最近 10 根已收盘 K 线中 bearish_count >= 8 -> 做多
```

`doji` 不计入 bullish 或 bearish。

## 4. 仓位参数

| 参数 | 值 |
|---|---:|
| `long_allocation` | `3.0` |
| `short_allocation` | `3.0` |
| `allocation_atr_window` | `672` |
| `target_atr_pct` | `0.004` |

仓位计算：

```text
atr_pct_672 = ATR672 / close
base_allocation = min(3.0, 3.0 * target_atr_pct / atr_pct_672)
actual_allocation = base_allocation * risk_multiplier
```

ATR 使用 trade kline 的 `high / low / close`：

```text
true_range = max(
    high - low,
    abs(high - previous_close),
    abs(low - previous_close)
)
ATR672 = rolling_mean(true_range, 672)
```

## 5. 原 V18 止盈止损

| 参数 | 值 |
|---|---:|
| `stop_loss_atr_window` | `672` |
| `stop_loss_atr_multiplier` | `5.0` |
| `min_stop_loss_pct` | `0.025` |
| `max_stop_loss_pct` | `0.035` |
| `take_profit_atr_window` | `672` |
| `take_profit_atr_multiplier` | `6.0` |
| `min_take_profit_pct` | `0.025` |
| `max_take_profit_pct` | `0.035` |

```text
stop_loss_pct = clamp(atr_pct_672 * 5.0, 0.025, 0.035)
take_profit_pct = clamp(atr_pct_672 * 6.0, 0.025, 0.035)
```

多单：

```text
stop_price = entry_price * (1 - stop_loss_pct)
take_price = entry_price * (1 + take_profit_pct)

if mark_low <= stop_price: stop
else if mark_high >= take_price: take
```

空单：

```text
stop_price = entry_price * (1 + stop_loss_pct)
take_price = entry_price * (1 - take_profit_pct)

if mark_high >= stop_price: stop
else if mark_low <= take_price: take
```

同一根 K 线内如果止损和止盈都可能触发，按上面顺序保守处理：先止损。

## 6. 入场过滤和冷却

| 参数 | 值 |
|---|---:|
| `entry_mode` | `signal_start` |
| `opposite_signal_gap_bars` | `8` |
| `cooldown_bars` | `8` |
| `trend_window_bars` | `96` |
| `trend_block_pct` | `0.05` |

入场条件：

```text
只在信号刚出现时入场。
如果上一根 K 线已经是同方向信号，不入场。

最近 8 根 K 线出现过反向信号，不入场。

做空时，如果 ret96 > +5%，不入场。
做多时，如果 ret96 < -5%，不入场。
```

`ret96`：

```text
ret96 = close[t] / close[t - 96] - 1
```

每次平仓后冷却 `8` 根 15m K 线。

## 7. 止损后风险倍率

| 参数 | 值 |
|---|---:|
| `initial_risk_multiplier` | `1.0` |
| `stop_loss_risk_multiplier` | `0.5` |
| `min_risk_multiplier` | `0.125` |

规则：

```text
如果原 ATR 止损触发：
    risk_multiplier = max(0.125, risk_multiplier * 0.5)

如果原 ATR 止盈触发：
    risk_multiplier = 1.0

如果 V21 提前平仓触发：
    risk_multiplier 不按 ATR 止损衰减
```

## 8. V21 新增规则

V21 是 V18 + 双向三反向提前平仓。

| 参数 | 值 |
|---|---:|
| `early_exit_bars` | `3` |
| `early_exit_include_entry_bar` | `false` |
| `early_exit_directions` | `both` |
| `early_exit_price` | `next_open` |

多单：

```text
买入后，不包含开仓 K。
如果 entry_index + 1、entry_index + 2、entry_index + 3 这三根 K 线全部为阴线：
    在 entry_index + 4 的 open 平仓
```

空单：

```text
卖空后，不包含开仓 K。
如果 entry_index + 1、entry_index + 2、entry_index + 3 这三根 K 线全部为阳线：
    在 entry_index + 4 的 open 平仓
```

注意：

- V21 是提前止损，不是止盈。
- 三根反向 K 不包含开仓 K。
- V21 平仓后进入正常 `cooldown_bars = 8` 冷却。
- V21 平仓不触发 `risk_multiplier *= 0.5`。

## 9. 每根 K 线处理顺序

对每根 15m K：

```text
1. 如果已有持仓：
   1.1 先用本根 mark_high / mark_low 检查原 ATR 止损/止盈
   1.2 如果原 ATR 止损/止盈未触发，再检查 V21 三反向提前平仓
   1.3 如果仍未平仓，按 close 做 mark-to-market

2. 结算 funding_rate

3. 如果空仓且不在冷却：
   3.1 计算 candle-count 信号
   3.2 检查 signal_start
   3.3 检查 opposite_signal_gap_bars
   3.4 检查 24h 趋势禁入
   3.5 计算 ATR 仓位、止损、止盈
   3.6 在本根 close 开仓
```

## 10. 预期回测校验

本地最新数据湖结果，数据截至 `2026-05-28 12:30 UTC`：

| 窗口 | V18 收益 | V21 收益 | V21 最大回撤 | V21 开仓 | V21 止损 / 原止盈 / 提前平 |
|---|---:|---:|---:|---:|---:|
| 近7d | `+9.65%` | `+5.16%` | `-11.10%` | `7` | `2 / 3 / 1` |
| 近30d | `+34.52%` | `+51.13%` | `-17.52%` | `28` | `7 / 15 / 5` |
| 近90d | `+264.19%` | `+304.89%` | `-19.87%` | `74` | `19 / 47 / 7` |
| 全样本 | `+899.87%` | `+1537.79%` | `-26.48%` | `328` | `113 / 188 / 26` |

如果复现结果和上表差距很大，优先检查：

1. 是否使用 mark price K 线触发止盈止损。
2. V21 三根反向 K 是否不包含开仓 K。
3. V21 是否在原 ATR 止损/止盈之后检查。
4. V21 平仓是否在第 4 根 K 的 open。
5. V21 平仓是否没有降低 `risk_multiplier`。
6. 成本是否按单边 `0.00085` 收取。
