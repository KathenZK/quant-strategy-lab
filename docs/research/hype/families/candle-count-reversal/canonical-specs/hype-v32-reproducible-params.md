# HYPE-CC-V32 可复现参数说明

V32 = `V30 + target_atr_pct 全局 0.006`。

核心含义：

```text
V30 逻辑不变
target_atr_pct: 0.005 -> 0.006
```

V32 不是新 alpha，主要是把 V30 的 ATR 目标仓位整体放大。交易逻辑、止盈止损、`3/3` 和反向 `14/10` 提前平仓都沿用 V30。

## 1. 数据与交易标的

| 项目 | 值 |
|---|---:|
| 标的 | `HYPE/USDT:USDT` 永续 |
| 回测交易所数据 | Binance `HYPEUSDT` USDT 永续 |
| 实盘执行映射 | Hyperliquid `HYPE/USDC:USDC` |
| K线周期 | `15m` |
| OHLCV | 15m 成交价 K 线 |
| 止盈止损触发 | 15m mark price high / low |
| 资金费 | funding rate 已计入 |
| 当前复现数据窗口 | `2025-05-30 10:30 UTC` 至 `2026-06-01 03:00 UTC` |

## 2. 信号参数

| 参数 | 值 |
|---|---:|
| `lookback` | `10` |
| `min_count` | `8` |
| 阳线触发 | 最近 10 根中阳线数 `>= 8` 时做空 |
| 阴线触发 | 最近 10 根中阴线数 `>= 8` 时做多 |
| 十字线 | 不计入阳线或阴线 |
| `entry_mode` | `signal_start` |

K 线方向定义：

```text
bullish = close > open
bearish = close < open
doji    = close == open
```

入场信号：

```text
if bullish_count_10 >= 8:
    desired_direction = -1  # short
elif bearish_count_10 >= 8:
    desired_direction = 1   # long
else:
    desired_direction = 0
```

`signal_start` 表示只在信号刚出现时入场：

```text
signal[t] != 0 and signal[t - 1] != signal[t]
```

## 3. 仓位参数

| 参数 | 值 |
|---|---:|
| `long_allocation` | `3.0` |
| `short_allocation` | `3.0` |
| `allocation_atr_window` | `672` |
| `target_atr_pct` | `0.006` |
| `stop_loss_risk_multiplier` | `0.5` |
| `min_risk_multiplier` | `0.0625` |

ATR 百分比：

```text
atr_pct_672[t] = ATR672[t] / close[t]
```

基础仓位：

```text
max_allocation = 3.0
base_allocation = min(
    max_allocation,
    max_allocation * target_atr_pct / atr_pct_672[t]
)
```

实际仓位：

```text
effective_allocation = base_allocation * risk_multiplier
```

`risk_multiplier` 规则：

```text
初始 risk_multiplier = 1.0
普通 ATR 止损后：risk_multiplier = max(0.0625, risk_multiplier * 0.5)
普通 ATR 止盈后：risk_multiplier = 1.0
early_main / early_counter 提前平仓：risk_multiplier 不变
```

## 4. 止损止盈参数

| 参数 | 值 |
|---|---:|
| `stop_loss_atr_window` | `672` |
| `stop_loss_atr_multiplier` | `5.0` |
| `min_stop_loss_pct` | `0.025` |
| `max_stop_loss_pct` | `0.035` |
| `take_profit_atr_window` | `672` |
| `take_profit_atr_multiplier` | `5.5` |
| `min_take_profit_pct` | `0.020` |
| `max_take_profit_pct` | `0.035` |

止损距离：

```text
raw_stop_pct = atr_pct_672[t] * 5.0
stop_loss_pct = clamp(raw_stop_pct, 0.025, 0.035)
```

止盈距离：

```text
raw_take_pct = atr_pct_672[t] * 5.5
take_profit_pct = clamp(raw_take_pct, 0.020, 0.035)
```

多单保护价：

```text
long_stop_price = entry_price * (1 - stop_loss_pct)
long_take_price = entry_price * (1 + take_profit_pct)
```

空单保护价：

```text
short_stop_price = entry_price * (1 + stop_loss_pct)
short_take_price = entry_price * (1 - take_profit_pct)
```

同一根 K 同时触发止损和止盈时，回测保守优先判定止损。

## 5. 趋势过滤与冷却

| 参数 | 值 |
|---|---:|
| `trend_window_bars` | `96` |
| `trend_block_pct` | `0.05` |
| `cooldown_bars` | `8` |
| `opposite_signal_gap_bars` | `8` |

24h 滚动涨跌幅：

```text
trend_return[t] = close[t] / close[t - 96] - 1
```

趋势禁入：

```text
if desired_direction == -1 and trend_return[t] > 0.05:
    block short

if desired_direction == 1 and trend_return[t] < -0.05:
    block long
```

反向信号间隔：

```text
新开仓前，最近 8 根 K 内不能出现过反向 signal
```

冷却：

```text
任意平仓后，冷却 8 根 15m K 线
```

## 6. V32 提前平仓规则

V32 有两类提前平仓：`3/3` 反向 K、反向 `14/10` counter。

### 6.1 `early_main`: 3/3 反向 K

开仓后，不含开仓 K，后续连续 3 根 15m K 全部反向，则提前平仓。

```text
多单：后 3 根全部 bearish
空单：后 3 根全部 bullish
```

触发后：

```text
按当前 close 平仓
exit_reason = early_main
risk_multiplier 不变
进入 8 根 K 冷却
```

### 6.2 `early_counter`: 14/10 反向 K

开仓后，不含开仓 K，后续 14 根 15m K 中至少 10 根反向，则提前平仓。

```text
多单：后 14 根里 bearish_count >= 10
空单：后 14 根里 bullish_count >= 10
```

触发后：

```text
按当前 close 平仓
exit_reason = early_counter
risk_multiplier 不变
进入 8 根 K 冷却
```

V32 不包含后续 V34 / V35 的顺向 counter 提前止盈。

## 7. 成本参数

| 参数 | 值 |
|---|---:|
| `fee_rate` | `0.00045` |
| `slippage_rate` | `0.0004` |
| 单边总成本 | `0.00085` |

每次入场和平仓都扣：

```text
cost = allocation * (fee_rate + slippage_rate)
```

资金费：

```text
funding_pnl = -direction * allocation * funding_rate
```

## 8. 每根 K 的处理顺序

```text
for each closed 15m bar:
    1. 如果已有持仓，先检查 mark high/low 是否触发 ATR 止损或 ATR 止盈
    2. 若 ATR 止损/止盈未触发，再检查 early_main
    3. 若 early_main 未触发，再检查 14/10 early_counter
    4. 若仍持仓，用 close-to-close 更新权益
    5. 若仍持仓，计入 funding
    6. 若本根发生平仓，扣出场成本，进入 cooldown，本根不再开仓
    7. 若当前无仓且无 cooldown，检查新入场信号
    8. 若入场，扣入场成本，记录 entry_bar_ts
```

## 9. 最新回测校验值

数据窗口：`2025-05-30 10:30 UTC` 至 `2026-06-01 03:00 UTC`

| 指标 | 值 |
|---|---:|
| 收益 | `+6265.50%` |
| 最大回撤 | `-35.70%` |
| Sharpe | `4.32` |
| 胜率 | `57.52%` |
| 开仓 | `339` |
| 止损 | `107` |
| 止盈 | `195` |
| 提前平仓 | `37` |
| 平均仓位 | `0.80x` |
| 交易成本 | `101.12%` |
| 资金费 PnL | `-1.29%` |
| 近90天收益 | `+482.69%` |
| 近90天最大回撤 | `-25.20%` |
| 近7天收益 | `-19.38%` |
| 近7天最大回撤 | `-23.76%` |

## 10. Python 配置等价写法

```python
StrategyConfig(
    symbol="HYPE/USDT:USDT",
    timeframe="15m",
    lookback=10,
    min_count=8,
    long_allocation=3.0,
    short_allocation=3.0,
    allocation_atr_window=672,
    target_atr_pct=0.006,
    stop_loss_atr_window=672,
    stop_loss_atr_multiplier=5.0,
    min_stop_loss_pct=0.025,
    max_stop_loss_pct=0.035,
    take_profit_atr_window=672,
    take_profit_atr_multiplier=5.5,
    min_take_profit_pct=0.020,
    max_take_profit_pct=0.035,
    opposite_candle_exit_bars=3,
    counter_exit_lookback_bars=14,
    counter_exit_min_opposite_bars=10,
    counter_exit_min_favorable_bars=None,
    trend_window_bars=96,
    trend_block_pct=0.05,
    cooldown_bars=8,
    opposite_signal_gap_bars=8,
    entry_mode="signal_start",
    stop_loss_risk_multiplier=0.5,
    min_risk_multiplier=0.0625,
    fee_rate=0.00045,
    slippage_rate=0.0004,
)
```

## 11. 与相邻版本的区别

| 版本 | 主要差异 |
|---|---|
| V30 | `target_atr_pct=0.005` |
| V31 | 同样三项稳健优化叠加到 V25 的 `target_atr_pct=0.004` |
| V32 | V30 的全局加仓版：`target_atr_pct=0.006` |
| V33 | `target_atr_pct=0.005` 中间仓位记录，参数等价于 V30 |
| V34 | 在 V32 上把 counter 改成反向 `10/8` + 顺向 `10/8` |
| V35 | 把 V34 的双向 `10/8` 改成双向 `12/9` |

