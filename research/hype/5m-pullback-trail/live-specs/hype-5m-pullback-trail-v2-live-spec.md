# HYPE-5M-PBTR-V2 实盘复现规格

规格 id: `HYPE-5M-PBTR-V2-LIVE-SPEC`

Family id: `HYPE-5M-PBTR`

状态：研究性 live-dry-run 候选。本文档是小资金 / paper-live 复现规格，不代表大资金生产批准。

创建时间：2026-06-23

## 目的

本文档面向需要足够精确复现 `HYPE-5M-PBTR-V2`、以便进行小规模实盘试运行的实现 agent。

该策略是 Binance HYPE USDT 永续 `5m` 回调-恢复策略：

```text
EMA21/EMA96 局部趋势
-> 价格触及 EMA21 区域
-> K 线按趋势方向重新收回
-> 最终 EMA96/EMA384 方向过滤
-> 下一根 K 线进场
-> 至少持有 6 根已收盘 K 线
-> 使用 ATR 移动止损退出
```

这不是 legacy `HYPE-EMA-TB` 15m trend-breakout family。诸如 `V2` 的版本名只在 `HYPE-5M-PBTR` 内部有效。

## 规范身份

| 字段 | 值 |
| --- | --- |
| 策略名称 | `HYPE-5M-PBTR-V2` |
| 来源组合标签 | `ema21_96_pb0.01_tp99_sl0.5_chop62_eff0_rsi55_roc96_htf0.5` |
| 交易所 | Binance USDT 永续 |
| 交易标的 | `HYPEUSDT` 永续，CCXT 风格为 `HYPE/USDT:USDT` |
| 时间级别 | `5m` |
| 方向 | 多空双向 |
| 持仓模型 | 同一时间只允许一个策略持仓，不加仓 |
| 研究杠杆 | `1x` |
| 手续费假设 | 单边 `0.04%` |
| 滑点假设 | 单边 `0.01%` |
| 信号 K 线 | 已收盘 `5m` K 线 `K0` |
| 回测进场 | 下一根 K 线 `K1` 开盘价，并计入滑点 |
| 实盘进场 | `K0` 收盘后立即进场，使用市价单或激进限价单，并采用实际成交价 |
| 主要退出 | ATR 移动止损 |
| 固定止盈 | 配置为 `99 ATR`，等同于基本禁用 |
| 冷却 | `0` 根 K 线，但持仓期间不允许新进场 |

## 精确参数

| 参数 | 值 | 含义 |
| --- | ---: | --- |
| `side_mode` | `both` | EMA 趋势向上时允许做多，EMA 趋势向下时允许做空 |
| `ema_fast` | `21` | 用于局部趋势和回调参考的快 EMA |
| `ema_slow` | `96` | 用于局部趋势的慢 EMA |
| `entry_style` | `pullback_resume` | 只在触及 EMA21 并发生方向性收回后进场 |
| `donchian` | `96` | `pullback_resume` 不使用，保留用于兼容 |
| `roc_window` | `96` | `dir_roc` 使用的动量回看窗口 |
| `min_regime_age` | `3` | 当前 EMA21/EMA96 方向开始后的最少 K 线数 |
| `max_regime_age` | `2000` | 当前 EMA21/EMA96 方向开始后的最多 K 线数 |
| `breakout_buffer` | `0.002` | `pullback_resume` 不使用，保留用于兼容 |
| `pullback_buffer` | `0.01` | EMA21 触及容忍度，等于 1% |
| `max_dist_ema` | `0.06` | 信号收盘价与 EMA21 的距离必须在 6% 以内 |
| `min_dir_roc` | `-0.01` | 方向调整后的 ROC96 至少为 -1% |
| `min_dir_rsi` | `55.0` | 方向调整后的 RSI14 下界 |
| `max_dir_rsi` | `72.0` | 方向调整后的 RSI14 上界 |
| `min_adx` | `0.0` | ADX14 必须有限且非负 |
| `max_chop` | `62.0` | CHOP14 上界 |
| `max_atr_ratio` | `99.0` | ATR14/ATR96 极端值保护，实际基本不生效 |
| `min_rvol` | `0.0` | RVOL96 下界，除 NaN 保护外实际基本不生效 |
| `min_dir_cmf` | `-0.30` | 方向调整后的 CMF20 下界 |
| `require_macd` | `false` | MACD 不是 V2 过滤条件 |
| `require_obv` | `false` | OBV 不是 V2 过滤条件 |
| `require_htf` | `false` | 内部 HTF 布尔开关关闭；V2 改用最终 `dir_htf >= 0.5` 过滤 |
| `min_efficiency` | `0.0` | efficiency 过滤放宽到 0 |
| `stop_atr` | `0.5` | 初始硬止损距离，基于信号 K 线 ATR14 |
| `tp_atr` | `99.0` | 固定止盈距离，实际禁用 |
| `trail_atr` | `0.75` | ATR 移动止损距离 |
| `max_hold_bars` | `576` | 时间退出扫描到 `entry_i + 576`；V2 通常不会触发 |
| `min_hold_bars` | `6` | 进场后的前 6 根 K 线不能因策略止损/止盈/EMA 退出 |
| `exit_ema` | `0` | EMA 退出禁用 |
| `cooldown_bars` | `0` | 退出后，后续更晚的信号可以进场 |
| `final_dir_htf_threshold` | `0.5` | 最终过滤：`side * (EMA96 - EMA384) >= 0.5` |

## 必需 K 线数据

输入 K 线列：

```text
ts, open, high, low, close, volume
```

要求：

- `ts` 必须为 UTC，并表示已收盘 5m K 线的开盘时间。
- K 线必须严格按 `5min` 递增。
- 重复时间戳必须去重，保留最新一行。
- 不允许缺失 5m K 线。如果有缺失，必须暂停信号生成直到数据被修复。
- 所有信号决策只能使用已经完全收盘的 K 线。
- 不得使用尚未成形的 K 线计算指标、信号、峰值/谷值更新或移动止损重算。

预热：

- 最低就绪门槛：`800` 根已收盘 5m K 线。
- 推荐实盘预加载：`2000+` 根已收盘 5m K 线，或完整可用的 HYPE 历史数据。
- EMA 值依赖递归历史。重启后不得以会改变 EMA21/EMA96/EMA384 数值的方式裁剪历史。

## 指标定义

以下全部公式都必须只基于已收盘 K 线计算。

### EMA

使用与 pandas 兼容的指数移动平均：

```text
EMA(span) = close.ewm(span=span, adjust=false, min_periods=span).mean()
```

必需周期：

```text
EMA21, EMA96, EMA384
```

如果通用实现还会计算 EMA9/12/34/55/144/192/288，它们不得影响 V2。

### True Range 与 ATR

```text
prev_close = close.shift(1)
TR = max(high - low, abs(high - prev_close), abs(low - prev_close))
ATR14 = rolling_mean(TR, window=14, min_periods=14)
ATR96 = rolling_mean(TR, window=96, min_periods=96)
atr_ratio_14_96 = ATR14 / ATR96
```

### RSI14

使用 Wilder 风格 EWM：

```text
delta = close.diff()
gain = max(delta, 0)
loss = max(-delta, 0)
avg_gain = gain.ewm(alpha=1/14, adjust=false, min_periods=14).mean()
avg_loss = loss.ewm(alpha=1/14, adjust=false, min_periods=14).mean()
RS = avg_gain / avg_loss
RSI14 = 100 - 100 / (1 + RS)
```

### CMF20

```text
money_flow_multiplier = ((close - low) - (high - close)) / (high - low)
money_flow_volume = money_flow_multiplier * volume
CMF20 = rolling_sum(money_flow_volume, 20) / rolling_sum(volume, 20)
```

如果 `high == low`，该 K 线的 multiplier 分母无效，生成的特征应为 `NaN`。

### CHOP14

使用精确的研究实现：它使用 `high - low` 的区间和，而不是 TR 和：

```text
high14 = rolling_max(high, 14)
low14 = rolling_min(low, 14)
range_sum14 = rolling_sum(high - low, 14)
CHOP14 = 100 * log10(range_sum14 / (high14 - low14)) / log10(14)
```

### Efficiency 96

```text
eff96 = abs(close.pct_change(96)) / rolling_sum(abs(close.pct_change()), 96)
```

### Relative Volume 96

```text
rvol96 = volume / rolling_mean(volume, 96)
```

### ADX14

由于 `min_adx=0`，ADX14 只作为有限且非负的保护条件。

使用 Wilder 风格 EWM：

```text
up = high.diff()
down = -low.diff()
plus_dm = up if up > down and up > 0 else 0
minus_dm = down if down > up and down > 0 else 0
ATR_ADX = TR.ewm(alpha=1/14, adjust=false, min_periods=14).mean()
plus_di = 100 * EWM(plus_dm, alpha=1/14, min_periods=14) / ATR_ADX
minus_di = 100 * EWM(minus_dm, alpha=1/14, min_periods=14) / ATR_ADX
DX = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
ADX14 = DX.ewm(alpha=1/14, adjust=false, min_periods=14).mean()
```

### ROC96

```text
ROC96 = close.pct_change(96)
```

### HTF 代理

这不是真实重采样的 1h K 线，而是 5m 序列上的 EMA96/EMA384 价差：

```text
htf_spread = EMA96 - EMA384
```

## 方向性特征

对每一根已收盘 K 线：

```text
spread = EMA21 - EMA96
direction = sign(spread)
```

方向取值：

```text
EMA21 > EMA96 时 direction = +1
EMA21 < EMA96 时 direction = -1
spread 为零或非有限值时 direction = 0
```

由于 `side_mode=both`，`+1` 与 `-1` 都允许。

方向性变换：

```text
dir_roc = direction * ROC96
dir_rsi = RSI14 if direction > 0 else 100 - RSI14
dir_cmf = direction * CMF20
dir_htf = direction * htf_spread
abs_dist_ema = abs(close / EMA21 - 1)
```

对空头交易，`dir_rsi = 100 - RSI14`，因此同一个 `55 <= dir_rsi <= 72` 规则意味着 RSI14 位于 `28` 到 `45` 之间。

## Regime Age

`regime_age` 是当前非零 `direction` 开始后经过的 K 线数量。

精确行为：

```text
方向变化后的第一根 K 线上 age = 0
下一根 K 线上 age = 1
再下一根 K 线上 age = 2
该方向的第四根 K 线上 age = 3
```

如果 `direction` 为 `0`，则重置 regime。

实现草图：

```text
current = 0
last_change_index = 0
for i in bars:
    if direction[i] == 0 or direction[i] != current:
        current = direction[i]
        last_change_index = i
    regime_age[i] = i - last_change_index
```

V2 要求：

```text
3 <= regime_age <= 2000
```

## 基础信号过滤

对某根 K 线 `K0`，只有所有条件都为真时才构造基础信号：

```text
direction != 0
regime_age >= 3
regime_age <= 2000
abs(close / EMA21 - 1) <= 0.06
dir_roc >= -0.01
dir_rsi >= 55
dir_rsi <= 72
ADX14 >= 0
CHOP14 <= 62
atr_ratio_14_96 <= 99
rvol96 >= 0
dir_cmf >= -0.30
eff96 >= 0
```

NaN 处理：

- 任何涉及 `NaN` 的比较都必须视为 false。
- 指标不完整的 K 线不能产生信号。

V2 中不活跃的过滤器：

- `require_macd=false`
- `require_obv=false`
- `require_htf=false`

不得额外加入 MACD、OBV 或内部 `dir_htf > 0` 过滤。只有下方最终 `dir_htf >= 0.5` 过滤属于 V2。

## 进场形态：Pullback Resume

通过基础过滤后，该 K 线还必须满足 `pullback_resume` 形态。

### 多头候选

当 `direction = +1` 时为多头候选：

```text
low <= EMA21 * (1 + 0.01)
close > EMA21
close > open
```

含义：

- 价格从上方或下方触及 EMA21 的 1% 区域；
- K 线收盘重新站上 EMA21；
- K 线实体为阳线。

### 空头候选

当 `direction = -1` 时为空头候选：

```text
high >= EMA21 * (1 - 0.01)
close < EMA21
close < open
```

含义：

- 价格从下方或上方触及 EMA21 的 1% 区域；
- K 线收盘重新跌回 EMA21 下方；
- K 线实体为阴线。

## 信号数组构造

对每一根已收盘 K 线：

```text
raw_signal = 0
if base_filter and pullback_resume_entry:
    raw_signal = direction
```

然后抑制相邻同方向信号：

```text
if raw_signal[i] != 0 and raw_signal[i] == raw_signal[i - 1]:
    base_signal[i] = 0
else:
    base_signal[i] = raw_signal[i]
```

这个抑制只检查紧邻的上一根 K 线。它不会抑制中间隔着一根或多根零信号 K 线的同方向信号。

## 最终 HTF 过滤

在构造 `base_signal` 后应用最终过滤：

```text
仅在 dir_htf >= 0.5 时保留信号
```

其中：

```text
dir_htf = signal_side * (EMA96 - EMA384)
```

对多头：

```text
EMA96 - EMA384 >= 0.5
```

对空头：

```text
EMA384 - EMA96 >= 0.5
```

最终过滤后，对过滤后的信号数组再次执行相同的相邻同方向抑制：

```text
if filtered_signal[i] != 0 and filtered_signal[i] == filtered_signal[i - 1]:
    final_signal[i] = 0
else:
    final_signal[i] = filtered_signal[i]
```

## 进场执行

信号时序：

```text
K0 收盘
使用截至并包含 K0 的 K 线计算所有指标和 final_signal
如果 final_signal[K0] 非零，则在 K1 进场
```

回测进场价：

```text
long_entry_price = open[K1] * (1 + 0.0001)
short_entry_price = open[K1] * (1 - 0.0001)
```

实盘进场：

- `K0` 确认收盘后立即提交市价单或激进限价单。
- 使用交易所实际成交价作为 `entry_price`。
- 如果订单在下一次策略决策周期前仍未成交，取消该订单，不保留过期进场单。
- 存储幂等 key，例如 `HYPE-5M-PBTR-V2:{signal_ts}:{side}`。

小规模实盘仓位规模：

```text
research_notional = account_equity * 1.0
live_notional = min(config.fixed_notional_usdt, account_equity * config.max_equity_fraction, config.max_notional_usdt)
quantity = live_notional / actual_entry_price
```

小规模实盘试运行应使用逐仓，并保持交易所杠杆为 `1x`，除非单独的风险文档明确修改。改变杠杆或名义本金会改变账户层面的回撤和爆仓风险，但不得改变信号逻辑。

## 单持仓规则

同一时间只能存在一个活跃策略持仓。

回测等价规则：

```text
for signal in chronological_order:
    entry_i = signal_i + 1
    if entry_i >= number_of_bars:
        skip
    if entry_i <= blocked_until:
        skip
    open trade and simulate until exit_i
    blocked_until = exit_i + cooldown_bars
```

V2 中：

```text
cooldown_bars = 0
```

由于 `blocked_until = exit_i`，任何进场 K 线位于当前持仓退出 K 线及之前的信号都会被跳过。前一笔交易完全平仓后，更晚的信号可以进场。

实盘等价规则：

- 如果已有持仓，忽略所有新信号。
- 持仓完全关闭且交易所状态确认空仓后，下一根更晚的已收盘 K 线信号才可以进场。
- 绝不在同一事件中从多头直接反手为空头，或从空头直接反手为多头。
- 绝不加仓。

## 退出逻辑

退出扫描从进场 K 线 `K1` 开始。

回测变量：

```text
signal_i = 信号 K 线 K0 的索引
entry_i = signal_i + 1
atr_signal = ATR14[signal_i]
entry_price = 计入滑点后的 open[entry_i]
```

初始多头价位：

```text
long_initial_stop = entry_price - 0.5 * atr_signal
long_target = entry_price + 99.0 * atr_signal
```

初始空头价位：

```text
short_initial_stop = entry_price + 0.5 * atr_signal
short_target = entry_price - 99.0 * atr_signal
```

`tp_atr=99.0` 保留用于精确配置身份，但实际基本禁用。历史 V2 退出为止损/移动止损退出。

### 多头移动止损

对从 `entry_i` 开始的每一根 K 线：

```text
previous_peak[current_offset] =
    entry_price                         当 current_offset == 0
    max(high[entry_i : current_i])       其他情况，排除 current_i 的 high

trail_level = previous_peak - 0.75 * ATR14[current_i]
stop_level = max(long_initial_stop, trail_level)
```

触发止损：

```text
low[current_i] <= stop_level
```

触发目标：

```text
high[current_i] >= long_target
```

### 空头移动止损

对从 `entry_i` 开始的每一根 K 线：

```text
previous_trough[current_offset] =
    entry_price                         当 current_offset == 0
    min(low[entry_i : current_i])        其他情况，排除 current_i 的 low

trail_level = previous_trough + 0.75 * ATR14[current_i]
stop_level = min(short_initial_stop, trail_level)
```

触发止损：

```text
high[current_i] >= stop_level
```

触发目标：

```text
low[current_i] <= short_target
```

### 最短持仓

进场后的前 `6` 根 K 线，策略止损、目标和 EMA 退出都禁用：

```text
if offset < 6:
    stop_hit = false
    target_hit = false
    ema_exit = false
```

由于 `offset=0` 是进场 K 线，第一次策略管理退出可能发生在：

```text
offset = 6
bars_held = offset + 1 = 7
```

实盘等价规则：

- 进场后的前 6 根已收盘 K 线内，不允许策略移动止损关闭持仓。
- 第 6 根进场后 K 线收盘后，为下一根符合条件的 K 线提交或激活第一张 reduce-only stop-market 订单。
- 可以使用单独的灾难止损保护账户，但它不属于研究策略，并且必须单独记录。

### 事件优先级

在第一根发生任意退出事件的 K 线上：

```text
if stop_hit:
    exit_reason = "stop"
    raw_exit_price = stop_level
elif target_hit:
    exit_reason = "target"
    raw_exit_price = target
elif ema_exit:
    exit_reason = "ema_exit"
    raw_exit_price = close[current_i]
```

如果同一根 K 线同时触发止损和目标，止损优先。

V2 中 `exit_ema=0`，因此 `ema_exit` 始终为 false。

### 时间退出

如果扫描到 `entry_i + max_hold_bars` 前都没有发生止损、目标或 EMA 退出，则在该 K 线收盘价退出：

```text
end_i = min(last_bar_i, entry_i + 576)
if no event:
    exit_reason = "time"
    raw_exit_price = close[end_i]
```

这个包含端点的扫描意味着记录的 `bars_held` 为：

```text
bars_held = exit_i - entry_i + 1
```

V2 历史交易通常更早退出；当前研究摘要中记录的最大值为 `13` 根 K 线。

### 回测退出价与净收益

应用退出滑点：

```text
long_exit_price = raw_exit_price * (1 - 0.0001)
short_exit_price = raw_exit_price * (1 + 0.0001)
```

`1x` 净收益：

```text
gross = side * (exit_price / entry_price - 1)
net_ret_1x = gross - 2 * 0.0004
```

其中：

```text
side = +1 表示多头
side = -1 表示空头
```

实盘 PnL 应使用实际成交和实际手续费。人工滑点常数只用于回放校验。

## 实盘订单管理

不要依赖 Binance 原生 trailing-stop callback rate 来复现该策略。研究规则基于 ATR：

```text
long_stop = max(previous_stop, previous_peak - 0.75 * ATR14)
short_stop = min(previous_stop, previous_trough + 0.75 * ATR14)
```

使用策略管理的 reduce-only stop-market 订单。

### 多头止损维护

维护：

```text
peak = max(进场以来已收盘 K 线的 high, actual_entry_price)
candidate_stop = peak_before_latest_closed_bar - 0.75 * ATR14[latest_closed_bar]
new_stop = max(current_stop, long_initial_stop, candidate_stop)
```

规则：

- 多头止损只能上移。
- 不得因为 ATR 增大而下调多头止损。
- 只有四舍五入后的新止损价比现有止损价至少高一个 tick 时，才替换交易所止损单。

### 空头止损维护

维护：

```text
trough = min(进场以来已收盘 K 线的 low, actual_entry_price)
candidate_stop = trough_before_latest_closed_bar + 0.75 * ATR14[latest_closed_bar]
new_stop = min(current_stop, short_initial_stop, candidate_stop)
```

规则：

- 空头止损只能下移。
- 不得因为 ATR 增大而上调空头止损。
- 只有四舍五入后的新止损价比现有止损价至少低一个 tick 时，才替换交易所止损单。

### 撤单/改单协议

对每一根符合条件的已收盘 5m K 线：

1. 获取当前交易所持仓。
2. 如果空仓，清除本地持仓状态并取消过期 reduce-only 订单。
3. 如果有持仓，计算新的目标止损价。
4. 如果没有止损单，提交 reduce-only stop-market。
5. 如果旧止损单存在且新止损价更有利，在交易所能够安全支持多张 reduce-only 止损单时，先挂替代止损单；否则立即先撤旧单再挂新单。
6. 验证策略持仓最终只剩一张活跃 reduce-only 止损单。
7. 持久化新的止损订单 id 和止损价。

如果撤单/改单失败，不得开新仓。必须在下一次信号动作前重试订单维护。

## 持久化状态

每次发生重要事件后，都必须将状态持久化到本地数据库或 durable 文件。

必需字段：

```text
strategy_id
symbol
timeframe
position_status
side
signal_ts
signal_bar_index_or_ts
entry_ts
entry_price
entry_order_id
quantity
entry_atr14
initial_stop
target_price
current_stop
stop_order_id
bars_held
peak
trough
last_processed_closed_candle_ts
last_raw_signal
last_base_signal
last_final_signal
blocked_until_ts
realized_exit_ts
realized_exit_price
realized_exit_reason
```

幂等 key：

```text
entry_key = "HYPE-5M-PBTR-V2:{signal_ts}:{side}:entry"
stop_key = "HYPE-5M-PBTR-V2:{entry_ts}:{side}:stop:{stop_price}"
```

将所有订单请求和交易所响应存入 append-only 审计日志。

## 重启恢复

进程启动时：

1. 加载已持久化的策略状态。
2. 获取交易所 `HYPEUSDT` 未平仓持仓。
3. 获取 `HYPEUSDT` 未成交订单。
4. 对账本地状态与交易所状态。
5. 从交易所/数据湖重建近期 K 线框架和指标。
6. 如果交易所空仓但本地状态显示持仓中，将本地持仓标记为外部事件关闭，并取消过期订单。
7. 如果交易所有持仓但本地状态缺失，停止交易并要求人工对账。
8. 如果交易所有持仓且本地状态匹配，从 `entry_ts` 以来的已收盘 K 线重算 `bars_held`、`peak/trough` 和目标止损。
9. 一旦持仓符合策略退出条件，确保只存在一张 reduce-only 止损单。
10. 只有对账干净后才恢复信号处理。

在恢复状态不干净时，绝不打开新仓。

## 实盘信号循环

以下循环是预期运行时行为：

```text
while service_running:
    wait until a Binance 5m candle is confirmed closed
    fetch or update candles through latest closed candle
    validate no missing candles
    compute indicators on closed candles
    reconcile exchange position and local state

    if position is open:
        update bars_held, peak/trough, and ATR trailing stop
        maintain reduce-only stop order if eligible
        persist state
        continue

    compute final_signal on the latest closed candle
    if final_signal == 0:
        persist last_processed_closed_candle_ts
        continue

    if signal_ts was already processed:
        continue

    submit entry order
    if filled:
        initialize position state
        persist state
    else:
        cancel stale entry order
        record missed signal
```

## 参考伪代码

该伪代码有意贴近研究脚本。

```text
function compute_v2_signal(frame):
    add EMA21, EMA96, EMA384
    add ATR14, ATR96, RSI14, CMF20, CHOP14, ADX14, eff96, rvol96, ROC96

    direction = sign(EMA21 - EMA96)
    direction = 0 where spread is not finite
    age = regime_age(direction)

    dir_roc = direction * ROC96
    dir_rsi = RSI14 where direction > 0 else 100 - RSI14
    dir_cmf = direction * CMF20
    dir_htf = direction * (EMA96 - EMA384)
    dist = abs(close / EMA21 - 1)

    base =
        direction != 0
        and age >= 3
        and age <= 2000
        and dist <= 0.06
        and dir_roc >= -0.01
        and dir_rsi >= 55
        and dir_rsi <= 72
        and ADX14 >= 0
        and CHOP14 <= 62
        and ATR14 / ATR96 <= 99
        and RVOL96 >= 0
        and dir_cmf >= -0.30
        and eff96 >= 0

    long_entry =
        direction > 0
        and low <= EMA21 * 1.01
        and close > EMA21
        and close > open

    short_entry =
        direction < 0
        and high >= EMA21 * 0.99
        and close < EMA21
        and close < open

    raw_signal = direction where base and (long_entry or short_entry), else 0
    base_signal = suppress_adjacent_same_bar_signals(raw_signal)

    filtered_signal = base_signal where dir_htf >= 0.5, else 0
    final_signal = suppress_adjacent_same_bar_signals(filtered_signal)

    return final_signal
```

```text
function simulate_or_manage_trade(frame, signal_i, side):
    entry_i = signal_i + 1
    atr_signal = ATR14[signal_i]
    entry_price = open[entry_i] * (1 + side * 0.0001)

    initial_stop = entry_price - side * 0.5 * atr_signal
    target = entry_price + side * 99.0 * atr_signal

    for current_i from entry_i through min(last_i, entry_i + 576):
        offset = current_i - entry_i

        if side > 0:
            previous_peak = entry_price when offset == 0 else max(high[entry_i : current_i])
            stop_level = max(initial_stop, previous_peak - 0.75 * ATR14[current_i])
            stop_hit = low[current_i] <= stop_level
            target_hit = high[current_i] >= target
        else:
            previous_trough = entry_price when offset == 0 else min(low[entry_i : current_i])
            stop_level = min(initial_stop, previous_trough + 0.75 * ATR14[current_i])
            stop_hit = high[current_i] >= stop_level
            target_hit = low[current_i] <= target

        if offset < 6:
            stop_hit = false
            target_hit = false

        if stop_hit:
            raw_exit = stop_level
            reason = "stop"
            break
        if target_hit:
            raw_exit = target
            reason = "target"
            break

    if no event:
        raw_exit = close[end_i]
        reason = "time"

    exit_price = raw_exit * (1 - side * 0.0001)
    net_ret_1x = side * (exit_price / entry_price - 1) - 0.0008
```

## 回测验收目标

使用本研究批次中的本地数据湖。完整切片从本地第一根 HYPE 5m K 线附近开始，约为 `2025-05-30 10:30 UTC`；forward 切片从 `2026-06-01 00:00 UTC` 开始，到报告中使用的最新本地 K 线附近结束，约为 `2026-06-23 04:20 UTC`。

实现应在很小的浮点误差范围内复现这些数值：

| 指标 | 期望值 |
| --- | ---: |
| `signal_count` | `4658` |
| `trade_count` | `2515` |
| `full_trades` | `2515` |
| `full_equity_multiple` | `823.1920x` |
| `full_annualized_multiple` | `548.6654x` |
| `full_win_rate` | `57.4553%` |
| `full_payoff_ratio` | `2.7948` |
| `full_profit_factor` | `3.7742` |
| `full_max_dd` | `-6.8470%` |
| `full_avg_trade` | `0.2723%` |
| `full_avg_win` | `0.6449%` |
| `full_avg_loss_abs` | `0.2307%` |
| `full_worst_trade` | `-1.4665%` |
| `full_best_trade` | `43.9813%` |
| `min_slice_win_rate` | `56.2310%` |
| `min_slice_payoff_ratio` | `2.4333` |
| `min_slice_annualized_multiple` | `137.9127x` |
| `worst_slice_max_dd` | `-6.8470%` |
| `forward_2026_06_01_latest_trades` | `237` |
| `forward_2026_06_01_latest_win_rate` | `57.8059%` |
| `forward_2026_06_01_latest_payoff_ratio` | `2.9632` |
| `forward_2026_06_01_latest_profit_factor` | `4.0596` |
| `forward_2026_06_01_latest_max_dd` | `-4.3910%` |

切片指标：

| 切片 | 交易数 | 权益 | 年化 | 胜率 | Payoff | PF | 最大回撤 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| full | `2515` | `823.1920x` | `548.6654x` | `57.4553%` | `2.7948` | `3.7742` | `-6.8470%` |
| 2025-05-30 to 2025-09-01 | `622` | `3.9358x` | `210.3229x` | `56.9132%` | `2.4333` | `3.2142` | `-5.6419%` |
| 2025-09-01 to 2025-12-01 | `658` | `7.5215x` | `3290.4834x` | `56.2310%` | `3.0765` | `3.9524` | `-5.1414%` |
| 2025-12-01 to 2026-03-01 | `391` | `3.8497x` | `237.6081x` | `60.8696%` | `2.9505` | `4.5897` | `-6.8470%` |
| 2026-03-01 to 2026-06-01 | `607` | `3.4588x` | `137.9127x` | `57.0016%` | `2.6145` | `3.4659` | `-5.4184%` |
| 2026-06-01 to latest | `237` | `2.0884x` | `184639.4738x` | `57.8059%` | `2.9632` | `4.0596` | `-4.3910%` |

如果实现无法在同一份 K 线数据上匹配 `signal_count=4658` 和 `trade_count=2515`，不得进入实盘交易。

## 实盘试运行验收规则

使用实盘试运行指标判断实现是否像研究结果一样运行，不要用年化收益做判断。

最低试运行样本：

```text
300 到 500 笔已关闭交易
```

至少 `300` 笔交易后的暂停条件：

```text
net win rate < 54%
and payoff ratio < 2.0
```

额外预警条件：

```text
profit factor < 1.5
actual average slippage > 2 * research slippage assumption
long side and short side both not profitable over a meaningful sample
more than one unreconciled order-state error
any position not protected after it becomes trailing-stop eligible
```

不要用最开始几十笔交易判断策略。完整样本期望胜率约为 `57%`，因此连续亏损簇是正常现象。

## 实现检查清单

- 只基于已收盘 K 线计算指标。
- 使用与 pandas 兼容的 `adjust=false` EWM 语义，或完全等价的递归实现。
- 在进场形态之前应用所有基础过滤。
- 在最终 HTF 过滤前后都应用相邻同方向 K 线信号抑制。
- 使用 `dir_htf >= 0.5` 作为最终过滤。
- 只在已收盘 K 线信号后的下一根 K 线进场。
- 强制同一时间只持有一个仓位。
- 实盘模式下使用实际成交价计算止损。
- 使用信号 K 线 ATR14 计算初始止损和目标。
- 使用当前已收盘 K 线 ATR14 更新移动止损。
- 为某根 K 线计算移动止损价位时，计算 previous peak/trough 要排除该 K 线自身的 high/low。
- 进场后的前 6 根 K 线禁用策略退出。
- 同一根 K 线同时触发止损和目标时，止损优先。
- 使用 reduce-only 退出订单。
- 每次订单动作前后都持久化状态。
- 每个循环和每次重启都对账交易所持仓和未成交订单。
- 如果数据连续性、持仓状态或订单状态不干净，停止开新仓。

## 参考研究产物

- 主 ledger：`../hype-5m-pullback-trail-core-ledger.md`
- V2 combo 报告：`../notes/hype-5m-pullback-trail-v2-combo-test-2026-06-23.md`
- V1/R05732 ablation：`../ablations/hype-5m-r05732-strategy-ablation-2026-06-23.md`
- V2 搜索脚本：`research/hype/5m-pullback-trail/scripts/test_hype_5m_r05732_v2_combos.py`
- 信号实现来源：`research/hype/5m-pullback-trail/scripts/research_hype_5m_indicator_search.py`
- Actual-path MAE/backtest 执行来源：`research/hype/5m-pullback-trail/scripts/ablate_hype_5m_r05732.py`
- V2 ranking 报告：`artifacts/hype_5m_r05732_v2_combo_test_ranking.csv`
- V2 slice 报告：`artifacts/hype_5m_r05732_v2_combo_test_slices.csv`
