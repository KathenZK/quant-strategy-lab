# HYPE-15M-MII-V1.2 完整复现规格（非实盘批准）2026-06-30

Family：`HYPE-15M-Multi-Indicator-Intraday`（alias：`HYPE-15M-MII`）

Version：`HYPE-15M-MII-V1.2`

Implementation label：`clean_rsi7_40_60_atrmin75_rvol1_h10_rsi14b0_tp120_sl360_hold16_x2 + atr96_tp1p25x_sl5x_hold24`

Status：`diagnostic observation only / not live-ready / not paper-live-ready`

## 先读结论

这份文件的目的，是让同事或另一个 AI 能完整复现 `HYPE-15M-MII-V1.2` 的研究回测与状态机。它不是实盘批准书，也不是 paper-live handoff。

`V1.2` 沿用 `V1.1` 的入场信号与过滤，把固定百分比出场从 `TP=1.20% / SL=3.60% / hold=16` 改为入场时按信号 K 已知 `ATR96%` 设置一次性固定 bracket：

- `TP = 1.25 * ATR96%`
- `SL = 5.0 * ATR96%`
- `max_hold_bars = 24`

核心风险：`V1.2` 仍缺资金费、盘口级 stop-market 滑点、真实订单延迟、runner 重启恢复、交易所对账、missing-bar fail-closed 和 kill switch。任何实现都只能用于研究复现或极小额人工观察前的审计准备，不能标记为 `candidate`、`paper-live`、`dry-run`、`handoff` 或 `live`。

## 数据口径

| 项 | 值 |
| --- | --- |
| Exchange | `Binance` |
| Market | `USD-M perpetual` |
| Symbol | `HYPE/USDT:USDT` |
| Raw exchange symbol | `HYPEUSDT` |
| Timeframe | `15m` |
| Timezone | UTC |
| Candle requirement | 只使用闭合 K 线 |
| Research data path | `data/raw/ohlcv/exchange=binance/market_type=perp/timeframe=15m/date=*/symbol=hype_usdt_usdt.parquet` |
| Normalized data path | `data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m/date=*/symbol=hype_usdt_usdt.parquet` |
| Backtest sample | `2025-05-30T10:30:00+00:00` 到 `2026-06-26T04:00:00+00:00` |
| Rows | `37,607` |
| Data quality gate | `True` |
| Known data issues in retained evidence | gap `0`，duplicate `0`，critical null `0`，invalid OHLC `0`，raw/normalized mismatch `0` |

最低字段要求：

- `ts`
- `exchange`
- `symbol`
- `market_type`
- `timeframe`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `quote_volume`
- `trade_count`
- `vwap`
- `is_closed`
- `source`

## 成本与暴露

| 参数 | 值 | 说明 |
| --- | ---: | --- |
| `exposure` | `2.0` | 回测权益暴露 `2x`。这是收益缩放，不等同于已审计的交易所保证金设置。 |
| `commission_per_fill` | `0.001` | 每次成交手续费 `0.1000%`。 |
| `slippage_per_fill` | `0.0004` | 每次成交固定滑点 `0.0400%`。 |
| `round_trip_cost` | `0.0028` | 一进一出合计成本 `0.2800%`。 |
| `funding` | 未计入 | 永续资金费是实盘前 blocker。 |

单笔净收益计算：

```text
raw_return = direction * (exit_price / entry_price - 1)
net_trade_return = exposure * (raw_return - round_trip_cost)
net_trade_return_pct = net_trade_return * 100
```

其中 `direction = +1` 表示多头，`direction = -1` 表示空头。

## 指标定义

所有指标只能使用信号 K 收盘时已经可见的数据。禁止使用入场 K 或未来 K 的 high/low/close 更新入场信号或 bracket。

### True Range

```text
previous_close[t] = close[t-1]
TR[t] = max(
  high[t] - low[t],
  abs(high[t] - previous_close[t]),
  abs(low[t] - previous_close[t])
)
```

### RSI(7)

使用 Wilder 风格指数平滑：

```text
delta[t] = close[t] - close[t-1]
gain[t] = max(delta[t], 0)
loss[t] = max(-delta[t], 0)
avg_gain = EWM(gain, alpha=1/7, adjust=false, min_periods=7)
avg_loss = EWM(loss, alpha=1/7, adjust=false, min_periods=7)
RS = avg_gain / avg_loss
RSI7 = 100 - 100 / (1 + RS)
```

### MACD(12,26,9)

```text
ema12 = EWM(close, span=12, adjust=false, min_periods=12)
ema26 = EWM(close, span=26, adjust=false, min_periods=26)
macd = ema12 - ema26
macd_signal = EWM(macd, span=9, adjust=false, min_periods=9)
macd_hist = macd - macd_signal
```

`V1.2` 使用方向化 MACD histogram 过滤：

```text
dir_macd = macd_hist[t] * direction
filter pass if dir_macd >= 0
```

等价理解：

- 做多时要求 `macd_hist[t] >= 0`
- 做空时要求 `macd_hist[t] <= 0`

### ATR96%

`ATR96` 使用 `TR` 的 96 根简单滚动均值，不是 EWM：

```text
atr96[t] = rolling_mean(TR, window=96, min_periods=96)
atr_pct96[t] = atr96[t] / close[t]
```

### RVOL96

```text
rvol96[t] = volume[t] / rolling_mean(volume, window=96, min_periods=96)
```

## 入场参数

| 参数 | 值 | 说明 |
| --- | ---: | --- |
| `side` | `both` | 多空双向。 |
| `rsi_window` | `7` | 使用 `RSI(7)` 产生反转信号。 |
| `rsi_low` | `40.0` | 多头触发阈值。 |
| `rsi_high` | `60.0` | 空头触发阈值。 |
| `macd_fast` | `12` | MACD 快 EMA。 |
| `macd_slow` | `26` | MACD 慢 EMA。 |
| `macd_signal` | `9` | MACD signal EMA。 |
| `min_dir_macd` | `0.0` | 方向化 MACD histogram 必须非负。 |
| `min_atr_pct96` | `0.0075` | 只在 `ATR96% >= 0.75%` 时交易。 |
| `max_atr_pct96` | `0.028` | 只在 `ATR96% <= 2.80%` 时交易。 |
| `min_rvol96` | `1.0` | 只在 `RVOL96 >= 1.0` 时交易。 |
| `h1_confirm` | `false` | 不启用 1h 方向确认。 |
| `rsi14_band` | `false` | 不启用 RSI14 区间过滤。 |
| `cooldown_bars` | `0` | 无额外冷却，但单仓不重叠规则仍生效。 |

## 入场信号

在闭合信号 K `t` 上计算：

```text
long_signal[t]  = RSI7[t] > 40 and RSI7[t-1] <= 40
short_signal[t] = RSI7[t] < 60 and RSI7[t-1] >= 60
```

候选方向：

```text
if long_signal[t]:  direction = +1
if short_signal[t]: direction = -1
```

过滤条件：

```text
macd_filter = macd_hist[t] * direction >= 0
atr_filter = 0.0075 <= atr_pct96[t] <= 0.028
rvol_filter = rvol96[t] >= 1.0
candidate_entry = raw_signal and macd_filter and atr_filter and rvol_filter
```

若多空信号同一根 K 同时出现，必须按实现中的 signal stream 顺序处理；正常 RSI cross 逻辑下几乎不会同根同时触发。

## 出场参数（V1.2 核心）

| 参数 | 值 | 说明 |
| --- | ---: | --- |
| `exit_kind` | `atr_fixed_bracket` | 入场时按 ATR 设置一次性固定 TP/SL。 |
| `atr_window_for_exit` | `96` | 使用信号 K `t` 已知的 `ATR96%`。 |
| `tp_atr_mult` | `1.25` | 止盈距离为 `1.25 * ATR96%`。 |
| `sl_atr_mult` | `5.0` | 止损距离为 `5.0 * ATR96%`。 |
| `max_hold_bars` | `24` | 最长持有 24 根 15m K，即约 6 小时。 |
| `trailing` | `false` | 不移动止盈止损。 |

入场时：

```text
dynamic_atr_pct = atr_pct96[t]       # 注意：t 是信号 K，不是入场 K
take_profit_pct = dynamic_atr_pct * 1.25
stop_pct = dynamic_atr_pct * 5.0
```

价格：

```text
entry_price = open[t + entry_delay_bars]

if direction == +1:
  take_profit_price = entry_price * (1 + take_profit_pct)
  stop_price = entry_price * (1 - stop_pct)

if direction == -1:
  take_profit_price = entry_price * (1 - take_profit_pct)
  stop_price = entry_price * (1 + stop_pct)
```

## 执行时序

### 主口径

```text
entry_delay_bars = 1
entry_i = signal_i + 1
entry_ts = ts[entry_i]
entry_price = open[entry_i]
```

也就是闭合 K `t` 确认信号，下一根 `15m` K 的 open 入场。

### 压力口径

```text
entry_delay_bars = 2
entry_i = signal_i + 2
```

`K+2` 只用于延迟压力测试，不是主执行承诺。

### 单仓不重叠

策略同一时间只允许一笔仓位。候选交易按 entry index 排序后筛选：

```text
available_i = -1

for trade in candidate_trades:
  if trade.entry_i < available_i:
    skip
  if filters fail:
    skip
  accept trade

  if exit_reason in {"max_hold", "stop_gap", "take_profit_gap", "trailing_gap"}:
    intrabar_delay = 0
  else:
    intrabar_delay = 1

  available_i = trade.exit_i + cooldown_bars + intrabar_delay
```

含义：

- 如果上一单在某根 K 的 open 退出，可以同一根 open 先平后开。
- 如果上一单在盘中 TP/SL 退出，不允许回到该根 K 的 open 开下一单；最早下一根 K。

## 出场判定顺序

对每笔持仓，从 `entry_i` 遍历到 `forced_exit_i - 1`。`forced_exit_i = min(entry_i + max_hold_bars, n - 1)`。

### 多头

每根持仓 K `i` 上按以下顺序：

```text
open_price = open[i]
high_price = high[i]
low_price = low[i]

if open_price <= stop_price:
  exit_i = i
  exit_price = open_price
  exit_reason = "stop_gap"
  exit

if open_price >= take_profit_price:
  exit_i = i
  exit_price = take_profit_price
  exit_reason = "take_profit_gap"
  exit

if low_price <= stop_price:
  exit_i = i
  exit_price = stop_price
  exit_reason = "stop_loss"
  exit

if high_price >= take_profit_price:
  exit_i = i
  exit_price = take_profit_price
  exit_reason = "take_profit"
  exit
```

### 空头

每根持仓 K `i` 上按以下顺序：

```text
open_price = open[i]
high_price = high[i]
low_price = low[i]

if open_price >= stop_price:
  exit_i = i
  exit_price = open_price
  exit_reason = "stop_gap"
  exit

if open_price <= take_profit_price:
  exit_i = i
  exit_price = take_profit_price
  exit_reason = "take_profit_gap"
  exit

if high_price >= stop_price:
  exit_i = i
  exit_price = stop_price
  exit_reason = "stop_loss"
  exit

if low_price <= take_profit_price:
  exit_i = i
  exit_price = take_profit_price
  exit_reason = "take_profit"
  exit
```

说明：

- 同一根 K 同时触发 TP/SL 时，因检查顺序先 stop 后 target，按 stop-first。
- open 跳过 stop 时按 open 退出，比按 stop 价更保守。
- open 跳过 take-profit 时仍按 take-profit price 计入，不按更优 open 价格给额外收益。

### Timeout

若到 `forced_exit_i` 前没有触发 TP/SL：

```text
exit_i = forced_exit_i
exit_price = open[forced_exit_i]
exit_reason = "max_hold"
```

timeout 不能先读取 `forced_exit_i` 这根 K 的 high/low 再回到 open 成交。

## 伪代码

```python
for each closed candle t:
    compute RSI7[t], MACD_hist[t], ATR96_pct[t], RVOL96[t]

    direction = 0
    if RSI7[t] > 40 and RSI7[t - 1] <= 40:
        direction = +1
    elif RSI7[t] < 60 and RSI7[t - 1] >= 60:
        direction = -1
    else:
        continue

    if MACD_hist[t] * direction < 0:
        continue
    if not (0.0075 <= ATR96_pct[t] <= 0.028):
        continue
    if RVOL96[t] < 1.0:
        continue

    entry_i = t + 1
    if entry_i >= len(candles) - 1:
        continue

    atr_at_signal = ATR96_pct[t]
    take_profit_pct = atr_at_signal * 1.25
    stop_pct = atr_at_signal * 5.0
    entry_price = open[entry_i]

    if direction == +1:
        take_profit_price = entry_price * (1 + take_profit_pct)
        stop_price = entry_price * (1 - stop_pct)
    else:
        take_profit_price = entry_price * (1 - take_profit_pct)
        stop_price = entry_price * (1 + stop_pct)

    forced_exit_i = min(entry_i + 24, len(candles) - 1)
    exit_i = forced_exit_i
    exit_price = open[forced_exit_i]
    exit_reason = "max_hold"

    for i in range(entry_i, forced_exit_i):
        if direction == +1:
            if open[i] <= stop_price:
                exit_i, exit_price, exit_reason = i, open[i], "stop_gap"
                break
            if open[i] >= take_profit_price:
                exit_i, exit_price, exit_reason = i, take_profit_price, "take_profit_gap"
                break
            if low[i] <= stop_price:
                exit_i, exit_price, exit_reason = i, stop_price, "stop_loss"
                break
            if high[i] >= take_profit_price:
                exit_i, exit_price, exit_reason = i, take_profit_price, "take_profit"
                break
        else:
            if open[i] >= stop_price:
                exit_i, exit_price, exit_reason = i, open[i], "stop_gap"
                break
            if open[i] <= take_profit_price:
                exit_i, exit_price, exit_reason = i, take_profit_price, "take_profit_gap"
                break
            if high[i] >= stop_price:
                exit_i, exit_price, exit_reason = i, stop_price, "stop_loss"
                break
            if low[i] <= take_profit_price:
                exit_i, exit_price, exit_reason = i, take_profit_price, "take_profit"
                break

    raw_return = direction * (exit_price / entry_price - 1)
    net_return = 2.0 * (raw_return - 0.0028)
```

实现时还必须套用“单仓不重叠”筛选器，不能简单把所有候选信号并行计算后全收。

## 回测验收指标

在标准数据湖、上述成本和单仓规则下，复现实现应接近以下结果。

### 固定窗口

| 入场 | 窗口 | 交易数 | 总收益 | 年化 | 最大回撤 | 胜率 | PF | Sharpe |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `K+1` | `最近1周` | `0` | `0.00%` | `0.00%` | `0.00%` | `0.00%` | `0.000` | `0.00` |
| `K+1` | `最近1月` | `18` | `16.83%` | `564.64%` | `-13.24%` | `88.89%` | `1.987` | `3.84` |
| `K+1` | `最近3月` | `31` | `30.47%` | `194.28%` | `-13.24%` | `90.32%` | `2.060` | `3.03` |
| `K+1` | `最近6月` | `74` | `87.80%` | `254.21%` | `-15.21%` | `85.14%` | `2.089` | `3.55` |
| `K+1` | `最近1年` | `165` | `247.78%` | `248.07%` | `-17.74%` | `83.64%` | `2.032` | `3.67` |
| `K+1` | `全样本` | `184` | `355.78%` | `311.35%` | `-17.74%` | `84.78%` | `2.179` | `4.13` |
| `K+2` | `最近1月` | `19` | `15.05%` | `451.33%` | `-15.65%` | `89.47%` | `1.786` | `3.23` |
| `K+2` | `最近3月` | `32` | `28.48%` | `176.50%` | `-15.65%` | `90.62%` | `1.920` | `2.73` |
| `K+2` | `最近6月` | `75` | `56.47%` | `145.57%` | `-15.65%` | `81.33%` | `1.655` | `2.38` |
| `K+2` | `最近1年` | `167` | `163.96%` | `164.14%` | `-34.81%` | `82.04%` | `1.704` | `2.67` |
| `K+2` | `全样本` | `189` | `172.87%` | `154.96%` | `-34.81%` | `82.01%` | `1.612` | `2.46` |

Sharpe/Sortino 在本研究中使用交易净收益序列年化，净收益已包含 `2x` 暴露、手续费和滑点；资金费未计入。

### 出场原因验收

| 标签 | 入场 | take_profit | stop_loss | gap stop | max_hold |
| --- | --- | ---: | ---: | ---: | ---: |
| `atr96_tp1p25x_sl5x_hold24` | `K+1` | `153` | `7` | `0` | `24` |
| `atr96_tp1p25x_sl5x_hold24` | `K+2` | `152` | `9` | `0` | `28` |

### 滚动与随机切片风险

- `30d` 滚动：K+1 `40/52` 个正收益切片，中位总收益 `7.94%`，最差 `-10.68%`；K+2 `34/52` 个正收益切片，中位 `10.15%`，最差 `-29.03%`。
- `90d` 滚动：K+1 `43/44` 个正收益切片，中位 `38.49%`，最差 `-7.07%`；K+2 `38/44` 个正收益切片，中位 `21.34%`，最差 `-6.94%`。
- `180d` 滚动：K+1 `31/31` 个正收益切片，中位 `111.57%`，最差 `55.84%`；K+2 `29/31` 个正收益切片，中位 `54.56%`，最差 `-4.01%`。

## 实盘前必须补的模块

下列项目未完成，任何“实盘看一下”都必须先把这些缺口作为显式风险暴露给操作方：

1. 资金费回放：按 Binance funding timestamps 对持仓逐笔扣/收 funding。
2. tick/盘口级 stop-market 滑点：不能只用 15m OHLC 假设 stop 成交。
3. 交易所规则：tick size、step size、min notional、quantity rounding、reduce-only、position mode。
4. 订单原子性：入场成交后如何立刻设置 reduce-only TP/SL，部分成交如何处理。
5. 重启恢复：启动时以交易所真实持仓和 open orders 为准，不能只信本地状态。
6. 对账：signal、order、fill、fee、slippage、position、equity 全链路落库。
7. missing-bar fail-closed：缺 K、延迟 K、时钟漂移时禁止开新仓。
8. kill switch：日损、连续亏损、最大回撤、API 错误、订单拒绝、异常滑点、人工急停。
9. 小额观察额度：若用户仍要人工观察，必须在策略外定义最大名义本金和最大可亏损金额。

## 非复现依赖：仓库证据入口

- 主账：`../hype-15m-mii-core-ledger.md`
- ATR bracket 搜索报告：`../notes/hype-15m-mii-v1-2-atr-bracket-exit-2026-06-30.md`
- V1.2 窗口/滚动/随机切片：`../notes/hype-15m-mii-v1-2-window-slice-backtest-2026-06-30.md`
- V1.2 ATR bracket 脚本：`../scripts/research_hype_15m_mii_v1_2_atr_bracket_exit.py`
- V1.2 时间片脚本：`../scripts/research_hype_15m_mii_v1_2_window_slice_backtest.py`
- ATR bracket JSON：`../artifacts/hype_15m_mii_v1_2_atr_bracket_exit_2026-06-30.json`
- 时间片 JSON：`../artifacts/hype_15m_mii_v1_2_window_slice_backtest_2026-06-30.json`

## 允许和禁止的状态标签

允许：

- `diagnostic observation`
- `research replay`
- `manual audit preparation`

禁止：

- `live`
- `paper-live`
- `dry-run candidate`
- `handoff`
- `production candidate`
- `approved strategy`
