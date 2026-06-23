# HYPE-EMA-TB-V35 可复现参数说明（实盘交付版）

本文档对应研究台账 **HYPE 趋势突破族 V35**，目标是让任何人（或 AI）仅凭本文档独立复现回测和实盘逻辑。

```text
版本链：V30 -> V31(K2 open 延迟入场) -> V32(去冷却) -> V33(live-realistic 成交口径)
V34 = V33 + target ATR 提高到 0.020/0.018 + 浮盈 1.5ATR 后关闭指标退出 + 硬止损收紧到 7ATR
V35 = V34 仅放宽 timeout：最大持仓 192 根(48h) -> 384 根(96h)，其余完全不变
```

注意：不要和 `HYPE-CC-V35` 混用，那是另一个策略（10/8 K线计数信号）；本文档的 V35 是 `HYPE-EMA-TB-V35`，属于 15m EMA96/384 趋势突破族。

回测已按 live-realistic 口径修正（无前视：信号收盘确认、入场 ATR 用上一根完成 K、指标退出下一根 open 成交、禁止同 K 平仓再开仓）。

## 0. 实盘风险须知（先读）

```text
1. V35 是在同一份样本上消融选优后的组合，+6474% 是样本内最优数字，必然高估。
2. sizing(target ATR) 不产生 alpha，只等比放大盈亏；100 笔中 47 笔顶格 3x 杠杆。
3. MFE 1.5ATR / SL 7ATR 是 Binance 特化参数：HL 上回撤反而变差（-36.2%）。
4. 单笔最差亏损 -14%（含杠杆）；回测止损按精确价格成交，实盘插针滑点会更差。
5. 回测最大回撤 -23.49% 由 1 笔满杠杆止损(-14%) 叠加下一笔持仓浮亏构成，
   全样本最大连续亏损仅 2 笔；实盘心理预期按 1~2 笔连续止损 + 浮亏即 -25% 准备。
6. 实盘建议先降 sizing（见第 12 节），冻结参数，小资金跑 1~3 个月对照回测。
```

## 1. 参数总表

```yaml
strategy_id: hype_v35
symbol: HYPE/USDT:USDT
timeframe: 15m

data:
  ohlcv_exchange: binance
  market_type: perp
  funding_exchange: binance
  backtest_window: 2025-05-30 ~ 2026-06-01 03:00 UTC
  warmup_min_bars: 1600

execution:                      # live-realistic 口径
  signal_bar: K0 (15m 收盘确认)
  entry_execution: K2 open      # 跳过完整的 K1，第二根 K 开盘价入场
  entry_atr_source: 入场 K 的上一根已完成 K (K1) 的 ATR672
  stop_take_execution: 持仓 K 内按 high/low 触发，止损优先于止盈
  indicator_timeout_exit: 收盘确认后，下一根 K open 成交
  same_bar_reentry: 禁止（平仓后最早下一根 K 才能再入场）

features:
  ema_fast: 96                  # 15m
  ema_slow: 384                 # 15m
  adx_window: 28                # 15m, Wilder ewm
  volume_window: 192            # 15m 滚动均量
  atr_window: 672               # 15m, TR 简单滚动均值
  one_hour_adx_window: 21
  one_hour_ema_fast: 24
  one_hour_ema_slow: 96
  one_hour_alignment: 15m resample(1h, label=left, closed=left) -> 指标 shift(1) -> ffill 到 15m

entry:
  long:
    ema_spread_min: 0.0         # EMA96/EMA384 - 1 > 0
    adx_min: 28
    volume_surge_min: 0.25
    one_hour_confirm: 1h_adx21 > 18 且 1h_plus_di > 1h_minus_di
  short:
    ema_spread_max: 0.0         # EMA96/EMA384 - 1 < 0
    adx_min: 36
    volume_surge_min: 0.50
    one_hour_confirm: 1h_EMA24/1h_EMA96 - 1 < 0
  conflict: 多空信号同时成立则不入场
  use_di_entry_filter: false

sizing:
  long_target_atr_pct: 0.020
  short_target_atr_pct: 0.018
  max_allocation: 3.0
  formula: allocation = min(3.0, target / entry_atr_pct)
  use_drawdown_scale: false

exits:
  take_profit_atr: 5.0          # 固定 entry ATR，开仓后不变
  hard_stop_atr: 7.0            # 固定 entry ATR，开仓后不变
  indicator_exit:
    type: adx_only
    adx_exit: 22
    delayed_bars: 3             # 连续 3 根 15m 收盘 ADX < 22
    disable_after_mfe_atr: 1.5  # 浮盈峰值达到 1.5 entry ATR 后永久关闭本笔指标退出
  max_hold_bars: 384            # 96 小时 timeout 兜底（V35 唯一改动；样本内 0 触发）
  cooldown_bars: 0              # 无冷却，平仓后下一根 K 即可再入

costs:
  trade_cost_rate: 0.00085      # 每次成交 equity *= 1 - 0.00085 * allocation，开/平各一次
  funding: true                 # 持仓期间每根 15m K 按 funding_rate 结算
```

## 2. 数据口径

| 项目 | 值 |
|---|---|
| 主交易所 | Binance `HYPE/USDT:USDT` 永续 |
| K线周期 | `15m`，字段 `open/high/low/close/volume` |
| Funding | Binance funding rate，对齐 15m 索引，缺失填 0 |
| 预热 | 至少 `1600` 根 15m K（约 17 天）再开始交易 |
| 1h 数据 | 由 15m resample 得到，不要直接拉 1h K 线（避免口径差异） |

## 3. 指标计算

### 3.1 EMA 与 spread

```text
ema_n = close.ewm(span=n, adjust=False, min_periods=n).mean()
ema_spread = EMA96 / EMA384 - 1            # 15m
h1_ema_spread = 1h_EMA24 / 1h_EMA96 - 1    # 1h, 计算后 shift(1)
```

### 3.2 ATR（绝对值，非百分比）

```text
true_range = max(high - low, abs(high - prev_close), abs(low - prev_close))
ATR672 = true_range.rolling(672, min_periods=672).mean()
```

### 3.3 ADX / DI（Wilder）

```text
up_move = high.diff(); down_move = -low.diff()
plus_dm  = up_move   if up_move > down_move and up_move > 0 else 0
minus_dm = down_move if down_move > up_move and down_move > 0 else 0

atr_w    = ewm(true_range, alpha=1/window, adjust=False, min_periods=window)
plus_di  = 100 * ewm(plus_dm,  alpha=1/window) / atr_w
minus_di = 100 * ewm(minus_dm, alpha=1/window) / atr_w
dx  = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
adx = ewm(dx, alpha=1/window)

15m 用 window=28；1h 用 window=21
```

### 3.4 成交量放大

```text
volume_surge = volume / volume.rolling(192, min_periods=192).mean() - 1
```

### 3.5 1h 指标对齐（防前视，必须严格遵守）

```text
1. one_hour = 15m.resample("1h", label="left", closed="left") 聚合 OHLCV
2. 在 1h 上计算 adx21 / plus_di / minus_di / ema_spread(24,96)
3. 全部 shift(1)（只用已完成的上一根 1h K）
4. reindex 到 15m 索引，method="ffill"
```

## 4. 信号规则（在每根 15m K 收盘后计算）

```text
long_signal[t] =
      ema_spread[t] > 0
  and adx28[t] >= 28
  and volume_surge[t] >= 0.25
  and h1_adx21[t] > 18
  and h1_plus_di[t] > h1_minus_di[t]

short_signal[t] =
      ema_spread[t] < 0
  and adx28[t] >= 36
  and volume_surge[t] >= 0.50
  and h1_ema_spread[t] < 0

同时成立 -> 不入场
```

## 5. 入场执行（K2 open，延迟 2 根）

信号 K 记为 K0，则：

```text
K0 收盘：信号确认
K1     ：完整跳过（不做任何事）
K2 open：市价入场

entry_price   = open[K2]
entry_atr     = ATR672[K1]          # 上一根已完成 K 的 ATR（绝对值）
entry_atr_pct = entry_atr / entry_price
```

入场条件：当前无持仓、本根 K 没有刚执行过平仓、entry_atr 有效（非 NaN 且 > 0）。

## 6. 仓位

```text
多单：allocation = min(3.0, 0.020 / entry_atr_pct)
空单：allocation = min(3.0, 0.018 / entry_atr_pct)
```

allocation 是相对账户权益的名义杠杆倍数。回测中约 47% 的交易触顶 3.0x。

## 7. 止盈止损（固定 entry ATR，持仓 K 内触发）

```text
多单：take = entry_price + 5.0 * entry_atr
      stop = entry_price - 7.0 * entry_atr
      当根 low <= stop -> 按 stop 价平仓（止损优先）
      否则 high >= take -> 按 take 价平仓

空单：take = entry_price - 5.0 * entry_atr
      stop = entry_price + 7.0 * entry_atr
      当根 high >= stop -> 按 stop 价平仓（止损优先）
      否则 low <= take -> 按 take 价平仓
```

```text
注意：入场那根 K 本身的 high/low 也参与 TP/SL 判定。
实盘实现：开仓后立即挂 reduce-only 的止盈限价单和止损单。
```

## 8. 指标退出（ADX only，收盘确认后下一根 open 成交）

```text
每根持仓 K 收盘后：
  mfe_atr = 多单 (最高 high - entry) / entry_atr 的历史峰值
            空单 (entry - 最低 low) / entry_atr 的历史峰值

  if mfe_atr >= 1.5:
      本笔交易永久关闭指标退出（已关闭则不再恢复）

  if 指标退出未关闭 and adx28 < 22:
      weak_bars += 1
  else:
      weak_bars = 0

  if 指标退出未关闭 and weak_bars >= 3:
      在下一根 K open 平仓（reason = indicator_exit）
```

## 9. Timeout 与再入场

```text
持仓 >= 384 根 15m K（96 小时）：在下一根 K open 平仓（reason = timeout）
冷却：无（cooldown_bars = 0）
约束：平仓发生的那根 K 不允许再开新仓，最早下一根 K 的 open 才能再入场
```

```text
说明：timeout 只是兜底，硬止损/止盈/指标退出全程有效。
回测样本内 384 口径 timeout 0 触发，最长持仓 50 小时；
V34 的 192 口径会错平 2 笔差 5~7 根 K 就止盈的慢趋势单，这是 V35 唯一的改动来源。
```

## 10. PnL 与费用

```text
每笔交易 pnl = ((exit_price - entry_price) / entry_price * direction) * allocation
开仓时：equity *= 1 - 0.00085 * allocation
平仓时：equity *= 1 + pnl - 0.00085 * allocation
持仓期间每根 15m K：equity *= 1 - direction * allocation * funding_rate[t]
```

## 11. 回测执行伪代码（必须按此顺序）

```python
for each 15m bar i (after warmup):
    # 1. 执行上一根收盘排队的指标退出 / timeout，按 open[i] 成交
    if position and pending_exit:
        close_position(price=open[i], reason=pending_exit)
        exited_this_bar = True

    # 2. funding 结算（仍持仓时）
    if position and funding_rate[i] != 0:
        equity *= 1 - direction * allocation * funding_rate[i]

    # 3. 入场：用 K(i-2) 的信号，本根 open 成交
    if not position and not exited_this_bar:
        if long_signal[i-2] and not short_signal[i-2]:   direction = +1
        elif short_signal[i-2] and not long_signal[i-2]: direction = -1
        if direction:
            entry_atr = ATR672[i-1]
            entry_price = open[i]
            allocation = min(3.0, target / (entry_atr / entry_price))
            equity *= 1 - 0.00085 * allocation

    # 4. 持仓管理（含入场当根）
    if position:
        update mfe_atr using high[i] / low[i]
        if hit hard stop (7 ATR):    close at stop price
        elif hit take profit (5 ATR): close at take price
        else:
            if mfe_atr < 1.5 and adx28[i] < 22: weak_bars += 1
            else: weak_bars = 0
            if mfe_atr < 1.5 and weak_bars >= 3: pending_exit = "indicator_exit"
            if not pending_exit and hold_bars >= 384: pending_exit = "timeout"
```

## 12. 基准回测结果（验收标准）

复现实现后，回测结果应与下表一致（同一数据窗口 2025-05-30 ~ 2026-06-01 03:00 UTC，warmup 1600 根）：

| 数据源 | 收益 | 最大回撤 | Sharpe | 交易数 | 胜率 | 退出结构(TP/指标/SL/timeout) |
|---|---:|---:|---:|---:|---:|---:|
| Binance | `+6474.19%` | `-23.49%` | `4.94` | `100` | `80.0%` | `77 / 9 / 14 / 0` |
| Hyperliquid (HYPE/USDC:USDC) | `+543.17%` | `-36.24%` | `2.78` | `82` | `68.3%` | `56 / 7 / 19 / 0` |
| OKX | `+945.83%` | `-30.76%` | `2.90` | `104` | `68.3%` | `70 / 15 / 19 / 0` |

V34（timeout 192）对照：Binance `+5840.03% / -23.89% / 4.83`；V35 三家同向改善。

### 推荐实盘降杠杆档位（信号完全相同，仅 sizing 不同，Binance full）

| sizing (long/short) | 收益 | 最大回撤 | Sharpe | 单笔最差 |
|---|---:|---:|---:|---:|
| 0.012 / 0.010（保守，推荐起步） | `+1312.14%` | `-15.59%` | `4.59` | `-8.4%` |
| 0.014 / 0.012（折中） | `+2076.32%` | `-17.91%` | `4.65` | `-9.8%` |
| 0.016 / 0.014 | `+3215.83%` | `-19.14%` | `4.77` | `-11.2%` |
| 0.020 / 0.018（V35 原版） | `+6474.19%` | `-23.49%` | `4.94` | `-14.0%` |

```text
实盘期望管理：不要以 Binance +6474% 为预期。
更合理的锚是跨交易所最弱口径（HL +543%）再打折，
或保守 sizing 档（0.012/0.010 -> +1312%）的一半以下。
```

## 13. 实盘实现注意事项

```text
1. 信号必须用已收盘的 15m K 计算；当前未收盘 K 的任何数据都不能参与。
2. 1h 指标必须用 15m resample + shift(1)，不要直接订阅 1h K 线流。
3. 入场用 K2 开盘市价单；TP/SL 入场后立即挂 reduce-only 条件单。
4. 同根 K 内 TP 和 SL 都可能触发时按 SL 处理（回测假设保守，实盘以先触发为准）。
5. 指标退出 / timeout 是收盘信号，在下一根 K 开盘执行，不要收盘瞬间市价平仓。
6. 8.5 bps 单边成本假设 = taker 4.5bps + 滑点 4bps；资金量大需重估 HYPE 盘口深度。
7. ATR672 / EMA384 / volume 192 等长窗口指标启动前必须有 >= 1600 根 15m 历史 K。
8. 跨交易所部署：Hyperliquid 用 HYPE/USDC:USDC；HL 上建议退出结构回退到
   V33 版（disable_after_mfe_atr=2.0, hard_stop_atr=9.0），V34 的退出参数在 HL 上回撤更差。
```

## 14. AI 实盘实现强制检查清单

下面这段是给实现 agent / 同事 code review 用的硬约束。只要缺任意一条，就不应切 `live`。

```text
1. 决策时序
   - 每根 15m K 收盘后再计算信号。
   - 入场必须用 K0 信号、跳过完整 K1、K2 open 执行。
   - entry ATR 必须取 K2 入场前一根已完成 K（K1）的 ATR672。
   - 指标退出 / timeout 只能在收盘确认，下一根 K open 执行。

2. 订单保护
   - 入场市价单成交后，必须先确认交易所实际成交均价和成交数量。
   - TP/SL 价格必须以实际成交均价为锚：
     take = fill_price ± 5 * entry_atr
     stop = fill_price ∓ 7 * entry_atr
   - 必须先挂 closePosition 止损单，再挂 reduce-only 止盈单。
   - 任一保护单挂单失败，立即 reduce-only 市价平仓，不允许裸仓继续持有。
   - 每轮持仓对账时必须检查 TP + SL 挂单是否仍在；缺失则补挂，补挂失败则立即平仓。

3. 幂等与单实例
   - runner 必须有单实例锁，禁止两个进程同时跑同一子账户。
   - 订单必须带确定性 clientOrderId（例如 strategy + bar + side），避免重启重放时重复下单。
   - last_processed_bar 必须持久化；重启后不能重复处理已经完成的一根 K。

4. 状态恢复
   - 交易所仓位是最终真相；本地状态与交易所不一致时，必须 fail closed。
   - 本地认为空仓但交易所有仓位：立即撤保护单并 reduce-only 市价平仓。
   - 本地认为有仓但交易所无仓：视为 TP/SL 已成交，撤残留单并清本地仓位。

5. 行情与数据
   - 必须检查最新已收盘 K 的新鲜度；API 返回旧 K 时跳过本轮，不交易。
   - 1h 特征必须由 15m 数据 resample + shift(1) + ffill 得到，不允许直接用未确认 1h K。
   - 至少加载 1600 根 15m 历史 K 后才允许交易。

6. Binance 实盘默认
   - 建议 isolated margin。
   - 子账户专用，不要和手动交易或其他策略混用。
   - 小额实盘建议先用 0.012 / 0.010 / cap 2.0 保守档；V35 原版 cap 3.0 在 Binance 上扛不住 2025-10-10 级 -41% 单根插针。
```

### 14.1 止损触发价口径

回测的 TP/SL 触发用的是 15m OHLCV 的 `high/low`，本质更接近合约成交价/last price。
实盘在 Binance 上可以有两种选择：

```text
更贴近回测：STOP_MARKET workingType = CONTRACT_PRICE
更抗插针/强平管理：STOP_MARKET workingType = MARK_PRICE
```

如果目标是逐笔最大化贴近研究回测，使用 `CONTRACT_PRICE`。如果目标是小额线上试跑并降低异常成交价影响，可以使用 `MARK_PRICE`，但这会与回测止损触发口径有轻微偏差。无论选择哪种，必须在实盘日志里记录 `workingType`，并在复盘时固定同一口径。
