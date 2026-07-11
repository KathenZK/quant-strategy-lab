---
spec_role: lab_handoff
strategy_id: HYPE-5M-PBTR-V3.2
family_id: HYPE-5M-PBTR
runner_kind: hype_pullback
spec_status: superseded
superseded_by: hype-5m-pbtr-v6-2-1-live-spec.md
approval_level_max: none
---

# HYPE-5M-PBTR-V3.2 实盘复现规格（已被 V6.2.1 取代）

规格 id：`HYPE-5M-PBTR-V3.2-LIVE-SPEC`

Family id：`HYPE-5M-PBTR`

状态：paper-live / 小资金 dry-run 候选。本文档用于精确复现策略，不代表大资金生产批准。

创建时间：2026-06-24

## 目的

本文档面向需要复现 `HYPE-5M-PBTR-V3.2` 的实现同事。

V3.2 是 Binance HYPEUSDT 永续 `5m` 回踩恢复 + ATR trailing 策略：

```text
EMA21/EMA96 判断方向
-> 当前 5m K 线触碰 EMA21 附近
-> 同一根 K 线收盘重新回到趋势方向
-> 同一根 K 线颜色确认方向恢复
-> 下一根 5m K 线开盘成交
-> 至少持有 9 根 5m K
-> 使用 ATR trailing stop 平仓
```

这是 `HYPE-5M-PBTR` 家族的本地版本，不要与其他 HYPE 家族的 `V3.2` 或裸版本号混用。

## 规范身份

| 字段 | 值 |
| --- | --- |
| 策略名称 | `HYPE-5M-PBTR-V3.2` |
| 交易所 | Binance USDT 永续 |
| 交易标的 | `HYPEUSDT` 永续；CCXT 风格可写为 `HYPE/USDT:USDT` |
| 时间级别 | `5m` |
| 方向 | 多空双向 |
| 持仓模型 | 单策略单仓，不叠仓，不加仓 |
| 研究杠杆 | `1x` |
| 信号 K 线 | 已收盘 `5m` K 线，记为 `K0` |
| 回测进场 | 下一根 K 线 `K1` 开盘价，并计入滑点 |
| 实盘进场 | `K0` 收盘确认后立即下单，目标近似 `K1` 开盘成交 |
| 主要退出 | ATR trailing stop |
| 固定止盈 | `99 * ATR14`，基本等于禁用 |
| 冷却 | `0` 根 K 线；但持仓期间忽略所有新信号 |

## 完整参数

| 参数 | 值 | 状态 | 含义 |
| --- | ---: | --- | --- |
| `side_mode` | `both` | 生效 | 多空双向 |
| `ema_fast` | `21` | 生效 | 趋势方向与回踩参考 EMA |
| `ema_slow` | `96` | 生效 | 趋势方向慢 EMA |
| `entry_style` | `pullback_resume` | 生效 | 只做回踩/反抽后的方向恢复 |
| `donchian` | `96` | 兼容保留 | V3.2 入场不用 Donchian |
| `roc_window` | `96` | 兼容保留 | ROC 过滤已关闭，窗口不影响 V3.2 |
| `min_regime_age` | `0` | 关闭 | 不限制趋势已持续 K 线数 |
| `max_regime_age` | `100000` | 关闭 | 不限制趋势最大持续 K 线数 |
| `breakout_buffer` | `0.002` | 兼容保留 | V3.2 入场不用 breakout |
| `pullback_buffer` | `0.01` | 生效 | EMA21 触碰容忍度，1% |
| `max_dist_ema` | `99.0` | 关闭 | 不限制收盘价距离 EMA21 |
| `min_dir_roc` | `-99.0` | 关闭 | 不做方向 ROC 过滤 |
| `min_dir_rsi` | `0.0` | 关闭 | 不做 RSI 下界过滤 |
| `max_dir_rsi` | `100.0` | 关闭 | 不做 RSI 上界过滤 |
| `min_adx` | `0.0` | 仅作有限值保护 | ADX14 不是有效过滤器 |
| `max_chop` | `100.0` | 关闭 | 不做 CHOP 过滤 |
| `max_atr_ratio` | `99.0` | 基本关闭 | 仅过滤极端异常/NaN |
| `min_rvol` | `0.0` | 基本关闭 | 仅过滤 NaN |
| `min_dir_cmf` | `-99.0` | 关闭 | 不做 CMF 过滤 |
| `require_macd` | `false` | 关闭 | 不要求 MACD 同向 |
| `require_obv` | `false` | 关闭 | 不要求 OBV 同向 |
| `require_htf` | `false` | 关闭 | 不要求 HTF 同向 |
| `min_efficiency` | `0.0` | 基本关闭 | 仅过滤 NaN |
| `stop_atr` | `0.5` | 生效 | 初始硬止损距离 |
| `tp_atr` | `99.0` | 基本关闭 | 固定止盈距离极远 |
| `trail_atr` | `0.75` | 生效 | ATR trailing stop 距离 |
| `max_hold_bars` | `96` | 生效但通常不触发 | 最长持仓扫描到 96 根 5m K |
| `min_hold_bars` | `9` | 生效 | 进场后前 9 根 K 不触发策略退出 |
| `exit_ema` | `0` | 关闭 | 不使用 EMA 退出 |
| `cooldown_bars` | `0` | 关闭 | 平仓后不额外冷却 |
| `final_dir_htf_filter` | disabled | 关闭 | 不做最终 `dir_htf` 过滤 |

## 数据要求

输入 K 线字段：

```text
ts, open, high, low, close, volume
```

要求：

- `ts` 使用 UTC，表示该根 `5m` K 线的开盘时间。
- K 线必须严格按 `5min` 递增。
- 若有重复时间戳，保留最新 K 线。
- 不允许缺失 5m K 线；发现缺失时暂停信号生成。
- 所有指标和信号只能使用已经完全收盘的 K 线。
- 不得用未收盘的当前 K 线生成信号或更新 trailing stop。

预热：

- 最低需要 `800` 根已收盘 5m K 线。
- 推荐启动时加载 `2000+` 根 5m K 线，或完整可用历史。
- EMA 是递归指标，重启后不能随意缩短历史导致 EMA21/EMA96 数值漂移。

## 指标计算

### EMA

使用 pandas 兼容写法：

```text
EMA(span) = close.ewm(span=span, adjust=false, min_periods=span).mean()
```

V3.2 必需：

```text
EMA21
EMA96
```

若复用研究代码，也会计算 EMA384 等其他周期；它们不参与 V3.2 信号。

### ATR14

```text
prev_close = close.shift(1)
TR = max(high - low, abs(high - prev_close), abs(low - prev_close))
ATR14 = rolling_mean(TR, window=14, min_periods=14)
```

`ATR14` 用于初始止损、固定止盈和 trailing stop。

### 兼容特征

研究代码会同时计算 RSI、CMF、CHOP、ADX、RVOL、efficiency、ROC、HTF spread 等特征。V3.2 不把它们作为有效过滤器，但由于历史研究代码用 `NaN -> false` 处理，实盘复现时应保证这些特征已完成预热，避免启动初期信号数量不一致。

## 入场逻辑

### 方向

```text
spread = EMA21 - EMA96
```

方向定义：

```text
EMA21 > EMA96 -> direction = +1，允许做多
EMA21 < EMA96 -> direction = -1，允许做空
EMA21 == EMA96 或指标非有限 -> direction = 0，不交易
```

### 多头信号

在同一根已收盘 K 线 `K0` 上，必须同时满足：

```text
EMA21 > EMA96
low <= EMA21 * (1 + 0.01)
close > EMA21
close > open
```

含义：

- `EMA21 > EMA96`：局部趋势向上。
- `low <= EMA21 * 1.01`：这根 K 线盘中下探到 EMA21 上方 1% 范围内或更低，视为触碰/回踩 EMA21 附近。
- `close > EMA21`：这根 K 线收盘重新站回 EMA21 上方。
- `close > open`：这根 K 线是阳线，确认恢复方向向上。

信号确认后：

```text
K0 收盘确认信号
K1 开盘做多
```

### 空头信号

在同一根已收盘 K 线 `K0` 上，必须同时满足：

```text
EMA21 < EMA96
high >= EMA21 * (1 - 0.01)
close < EMA21
close < open
```

含义：

- `EMA21 < EMA96`：局部趋势向下。
- `high >= EMA21 * 0.99`：这根 K 线盘中反抽到 EMA21 下方 1% 范围内或更高，视为触碰/反抽 EMA21 附近。
- `close < EMA21`：这根 K 线收盘重新跌回 EMA21 下方。
- `close < open`：这根 K 线是阴线，确认恢复方向向下。

信号确认后：

```text
K0 收盘确认信号
K1 开盘做空
```

### 连续信号处理

研究代码会删除相邻同方向重复信号：

```text
如果当前 signal 与上一根 K 的 signal 同方向，则当前 signal 置 0
```

同时，单仓模型下持仓期间所有新信号都忽略。

## 实盘开仓

回测口径：

```text
entry_i = signal_i + 1
多头 entry_price = open[entry_i] * (1 + entry_slippage_rate)
空头 entry_price = open[entry_i] * (1 - entry_slippage_rate)
```

实盘执行建议：

- 在 `K0` 收盘确认后立即下单。
- 可使用市价单或激进限价单，目标是尽量接近下一根 5m K 的开盘成交。
- 必须记录真实成交价、maker/taker、滑点、订单失败和限价错过。
- 若已有策略持仓，不开新仓。

线上实盘统计成本口径：

```text
fee_rate_per_fill = 4.1466 bps / 成交额
entry_slippage = +10.73 bps
exit_slippage = -2.64 bps
net_slippage = +4.0449 bps / 总成交额
```

## 持仓与退出

### 通用规则

- 开仓后前 `9` 根 5m K 不触发策略退出。
- 第 `10` 根 5m K 起，允许 stop / target / trailing / time exit 生效。
- `max_hold_bars=96`，最长约 8 小时。
- 固定止盈 `tp_atr=99` 通常不会触发，主要依赖 trailing stop。
- 平仓后 `cooldown_bars=0`，但必须等仓位完全清理后才允许下一笔。

### 多头退出

开仓时，用信号 K 的 `ATR14` 计算：

```text
initial_stop = entry_price - 0.5 * ATR14(signal_bar)
target = entry_price + 99.0 * ATR14(signal_bar)
```

持仓过程中，每根已收盘 K 线更新：

```text
previous_peak = 持仓以来、当前 K 之前的最高价峰值
trail_stop = previous_peak - 0.75 * ATR14(current_bar)
active_stop = max(initial_stop, trail_stop)
```

若第 `10` 根 K 以后：

```text
low <= active_stop
```

则多头按 stop 平仓。

### 空头退出

开仓时，用信号 K 的 `ATR14` 计算：

```text
initial_stop = entry_price + 0.5 * ATR14(signal_bar)
target = entry_price - 99.0 * ATR14(signal_bar)
```

持仓过程中，每根已收盘 K 线更新：

```text
previous_trough = 持仓以来、当前 K 之前的最低价谷值
trail_stop = previous_trough + 0.75 * ATR14(current_bar)
active_stop = min(initial_stop, trail_stop)
```

若第 `10` 根 K 以后：

```text
high >= active_stop
```

则空头按 stop 平仓。

### Stop 只能向有利方向移动

实盘实现中：

- 多头 stop 只能上移，不能下移。
- 空头 stop 只能下移，不能上移。
- ATR 变大时不能放宽已有 stop。

### 时间退出

若到 `entry_i + 96` 仍未触发 stop / target：

```text
按当前 close 退出
```

研究样本里 V3.2 主要由 trailing stop 退出，时间退出通常不是主要退出来源。

## 订单管理建议

交易所原生 trailing stop 通常无法精确表达本策略的 ATR trailing 规则。建议由策略程序维护 reduce-only stop-market 订单。

流程：

1. `K0` 收盘后计算信号。
2. `K1` 开盘附近开仓。
3. 记录 `entry_price`、`entry_ts`、`signal_atr14`、`side`、`bars_held`、`peak/trough`。
4. 前 9 根 K 不提交策略退出单，或只提交独立灾难保护单。
5. 第 9 根 K 收盘后，计算第一张策略 trailing stop。
6. 第 10 根 K 起，每根 5m K 收盘后更新 stop。
7. 如果 stop 需要向有利方向移动，则 cancel/replace 旧 reduce-only stop。
8. stop 成交后，清理本地状态并撤销残留 reduce-only 订单。
9. 程序重启时，必须从交易所仓位和本地状态恢复。

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

线上实盘成本口径下：

| 交易数 | 年化 | 胜率 | payoff | profit factor | 最大回撤 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| `8025` | `1324019761.54x` | `55.66%` | `3.31` | `4.15` | `-8.69%` |

注意：该年化是高频复利数学结果，不是实盘收益承诺。实盘重点看 `300-500` 笔后的 PF、payoff、滑点和订单失败率。

## Dry-run 验收线

至少跑 `300-500` 笔 paper-live / 小资金实盘后再评估：

- profit factor `>= 1.8`。
- payoff `>= 2.2`。
- 净胜率不长期低于 `47%`。
- 多头和空头不能单边失效。
- 新增交易子集不能单独失效；新增交易子集 PF 若低于 `1.5`，回退到 V3.1。
- 实际开仓滑点若超过回测假设 `2x`，必须重新压测。
- 必须记录限价错过、订单失败、maker/taker 占比、重启恢复事件。

## 复现入口

研究脚本：

```text
research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v32_clean_entry_filters.py
research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v32_full_ablation.py
```

研究报告：

```text
research/hype/5m-pullback-trail/diagnostics/hype-5m-pbtr-v32-clean-entry-filters-2026-06-24.md
research/hype/5m-pullback-trail/ablations/hype-5m-pbtr-v32-full-parameter-ablation-2026-06-24.md
```
