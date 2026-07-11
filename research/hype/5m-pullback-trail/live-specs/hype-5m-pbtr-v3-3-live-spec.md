---
spec_role: lab_handoff
strategy_id: HYPE-5M-PBTR-V3.3
family_id: HYPE-5M-PBTR
runner_kind: hype_pullback
spec_status: superseded
superseded_by: hype-5m-pbtr-v6-2-1-live-spec.md
approval_level_max: none
---

# HYPE-5M-PBTR-V3.3 最小实盘复现规格（已被 V6.2.1 取代）

规格 id：`HYPE-5M-PBTR-V3.3-LIVE-SPEC`

Family id：`HYPE-5M-PBTR`

状态：paper-live / 小资金 dry-run 候选。本文档用于精确复现最小策略逻辑，不代表大资金生产批准。

创建时间：2026-06-24

## 目的

`HYPE-5M-PBTR-V3.3` 是 `V3.2` 的最小化表达。它删除所有已经证明无贡献、仅兼容保留、关闭、有限值保护或基本不触发的参数，只保留真正参与策略行为的内容：

```text
EMA21/EMA96 方向
-> EMA21 回踩/反抽恢复
-> 下一根 5m K 开盘入场
-> 至少持有 9 根 5m K
-> ATR trailing stop 平仓
```

## 最小参数

| 参数 | 值 | 含义 |
| --- | ---: | --- |
| `ema_fast` | `21` | 趋势方向与回踩参考 EMA |
| `ema_slow` | `96` | 趋势方向慢 EMA |
| `pullback_buffer` | `0.01` | EMA21 触碰容忍度，1% |
| `stop_atr` | `0.5` | 初始硬止损距离 |
| `trail_atr` | `0.75` | ATR trailing stop 距离 |
| `min_hold_bars` | `9` | 进场后前 9 根 K 不触发策略退出 |

## 已删除参数

V3.3 不再定义以下参数：

```text
side_mode
entry_style
donchian
roc_window
min_regime_age
max_regime_age
breakout_buffer
max_dist_ema
min_dir_roc
min_dir_rsi
max_dir_rsi
min_adx
max_chop
max_atr_ratio
min_rvol
min_dir_cmf
require_macd
require_obv
require_htf
min_efficiency
tp_atr
max_hold_bars
exit_ema
cooldown_bars
final_dir_htf_filter
```

含义：

- 不做 ROC/RSI/ADX/CHOP/RVOL/CMF/MACD/OBV/HTF/efficiency 过滤。
- 不做 final HTF 过滤。
- 不做固定止盈。
- 不做 EMA exit。
- 不做 cooldown。
- 不做固定最长持仓退出；正常退出完全交给 ATR trailing stop。若程序停止、数据结束或人工风控触发，按外部风控处理。

## 数据要求

输入 `5m` K 线字段：

```text
ts, open, high, low, close, volume
```

要求：

- `ts` 使用 UTC，表示该根 `5m` K 线的开盘时间。
- K 线必须严格按 `5min` 递增。
- 若有重复时间戳，保留最新 K 线。
- 不允许缺失 5m K 线；发现缺失时暂停信号生成。
- 所有指标和信号只能使用已经完全收盘的 K 线。
- 不得用未收盘 K 线生成信号或更新 trailing stop。
- 推荐启动时加载 `2000+` 根 5m K 线，避免 EMA 递归值漂移。

## 指标计算

### EMA

```text
EMA(span) = close.ewm(span=span, adjust=false, min_periods=span).mean()
```

只需要：

```text
EMA21
EMA96
```

### ATR14

```text
prev_close = close.shift(1)
TR = max(high - low, abs(high - prev_close), abs(low - prev_close))
ATR14 = rolling_mean(TR, window=14, min_periods=14)
```

`ATR14` 用于初始止损和 trailing stop。

## 入场逻辑

### 方向

```text
spread = EMA21 - EMA96
```

```text
EMA21 > EMA96 -> 多头方向
EMA21 < EMA96 -> 空头方向
EMA21 == EMA96 或 EMA 非有限 -> 不交易
```

### 多头信号

在同一根已收盘 K 线 `K0` 上同时满足：

```text
EMA21 > EMA96
low <= EMA21 * 1.01
close > EMA21
close > open
ATR14 is finite
```

解释：

- 趋势向上。
- K0 盘中下探到 EMA21 上方 1% 范围内或更低。
- K0 收盘重新站回 EMA21 上方。
- K0 是阳线。

执行：

```text
K0 收盘确认信号
K1 开盘做多
```

### 空头信号

在同一根已收盘 K 线 `K0` 上同时满足：

```text
EMA21 < EMA96
high >= EMA21 * 0.99
close < EMA21
close < open
ATR14 is finite
```

解释：

- 趋势向下。
- K0 盘中反抽到 EMA21 下方 1% 范围内或更高。
- K0 收盘重新跌回 EMA21 下方。
- K0 是阴线。

执行：

```text
K0 收盘确认信号
K1 开盘做空
```

### 连续信号处理

如果相邻两根 K 线都出现同方向信号，只保留第一根：

```text
如果 signal[i] != 0 且 signal[i] == signal[i-1]，则 signal[i] = 0
```

单仓模型下，持仓期间忽略所有新信号。

## 成本口径

线上实盘统计成本：

```text
fee_rate_per_fill = 4.1466 bps / 成交额
entry_slippage = +10.73 bps
exit_slippage = -2.64 bps
net_slippage = +4.0449 bps / 总成交额
```

回测进场价：

```text
多头 entry_price = next_open * (1 + entry_slippage)
空头 entry_price = next_open * (1 - entry_slippage)
```

回测出场价：

```text
多头 exit_price = raw_exit_price * (1 - exit_slippage)
空头 exit_price = raw_exit_price * (1 + exit_slippage)
```

## 持仓与平仓

### 通用规则

- 单策略单仓，不叠仓，不加仓。
- 开仓后前 `9` 根 5m K 不触发策略退出。
- 第 `10` 根 5m K 起，允许 ATR trailing stop 生效。
- 不设固定止盈。
- 不设固定最长持仓时间。
- 平仓后可接受下一笔新信号。

### 多头退出

开仓时计算：

```text
initial_stop = entry_price - 0.5 * ATR14(signal_bar)
```

持仓过程中，每根已收盘 K 线更新：

```text
previous_peak = 持仓以来、当前 K 之前的最高价
trail_stop = previous_peak - 0.75 * ATR14(current_bar)
active_stop = max(initial_stop, trail_stop)
```

第 `10` 根 K 起：

```text
if low <= active_stop:
    stop 平仓
```

### 空头退出

开仓时计算：

```text
initial_stop = entry_price + 0.5 * ATR14(signal_bar)
```

持仓过程中，每根已收盘 K 线更新：

```text
previous_trough = 持仓以来、当前 K 之前的最低价
trail_stop = previous_trough + 0.75 * ATR14(current_bar)
active_stop = min(initial_stop, trail_stop)
```

第 `10` 根 K 起：

```text
if high >= active_stop:
    stop 平仓
```

### Stop 移动约束

- 多头 stop 只能上移，不能下移。
- 空头 stop 只能下移，不能上移。
- ATR 变大时不能放宽已有 stop。

## 本地状态字段

建议至少保存：

```text
strategy_id
symbol
timeframe
side
position_size
signal_ts
entry_ts
entry_price
signal_atr14
initial_stop
active_stop
peak_price
trough_price
bars_held
last_processed_kline_ts
order_ids
realized_exit_price
fees
slippage
```

## 回测参考结果

数据范围：Binance HYPEUSDT `5m`，约 `2025-05-30 10:30 UTC` 到 `2026-06-23 04:20 UTC`。

线上实盘成本口径：

| 版本 | 信号数 | 交易数 | 年化 | 胜率 | payoff | profit factor | 最大回撤 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `V3.2` | `21282` | `8025` | `1324019761.54x` | `55.66%` | `3.31` | `4.15` | `-8.69%` |
| `V3.3` | `21289` | `8027` | `1327928815.51x` | `55.66%` | `3.31` | `4.15` | `-8.69%` |

V3.3 与 V3.2 基本一致，仅因移除旧代码中的额外 NaN 预热保护，多出 `2` 笔交易。策略核心行为未变。

## Dry-run 验收线

至少跑 `300-500` 笔 paper-live / 小资金实盘后评估：

- profit factor `>= 1.8`。
- payoff `>= 2.2`。
- 净胜率不长期低于 `47%`。
- 多头和空头不能单边失效。
- 实际开仓滑点若超过回测假设 `2x`，必须重新压测。
- 必须记录限价错过、订单失败、maker/taker 占比、重启恢复事件。

## 复现入口

```text
research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v3-3_minimal.py
research/hype/5m-pullback-trail/diagnostics/hype-5m-pbtr-v3-3-minimal-2026-06-24.md
```
