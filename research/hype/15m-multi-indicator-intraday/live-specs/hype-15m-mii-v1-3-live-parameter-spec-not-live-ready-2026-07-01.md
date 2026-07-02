# HYPE-15M-MII-V1.3 实盘参数规格（非实盘批准）2026-07-01

Family：`HYPE-15M-Multi-Indicator-Intraday`（alias：`HYPE-15M-MII`）

Version：`HYPE-15M-MII-V1.3`

Runner kind：`hype_mii_v13`

Status：`runner implementation target / diagnostic observation only / not live-ready / not paper-live-ready`

## 先读结论

`HYPE-15M-MII-V1.3` 是 `HYPE-15M-MII-V1.2` 的固定 `2.5x` 权益暴露版本。它不改变 `V1.2` 的 alpha、过滤或 ATR bracket 出场，只改变 sizing：

- 入场：`RSI(7)` 反转信号 + `MACD(12,26,9)` 方向过滤 + `ATR96%` 波动过滤 + `RVOL96` 成交量过滤。
- 出场：用信号 K 已知的 `ATR96%` 设置一次性固定 bracket，`TP = 1.25 * ATR96%`，`SL = 5.0 * ATR96%`，最长 `24` 根 `15m` K。
- 暴露：固定 `2.5x` 权益暴露；在 `quant-runner` 中用 `exposure = 2.5` 控制下单名义规模，`leverage = 3` 只是 Binance 整数杠杆设置上限。

这份文件是参数导出和 runner 对齐规格，不是实盘批准书。当前仍缺资金费核算、盘口级 market/stop-market 滑点审计、真实订单延迟、runner 重启恢复、交易所对账、missing-bar fail-closed、kill switch 和指标对拍验收。不得把本版本标记为 `candidate`、`paper-live`、`dry-run handoff` 或 `live`。

## 身份与边界

| 项 | 值 |
| --- | --- |
| Full family name | `HYPE-15M-Multi-Indicator-Intraday` |
| Alias | `HYPE-15M-MII` |
| Version | `HYPE-15M-MII-V1.3` |
| Parent version | `HYPE-15M-MII-V1.2` |
| Exchange | `Binance` |
| Market | `USD-M perpetual` |
| CCXT symbol | `HYPE/USDT:USDT` |
| Raw exchange symbol | `HYPEUSDT` |
| Timeframe | `15m` |
| Timezone | UTC |
| Candle requirement | 只使用闭合 K 线 |
| Current runner repository | `/Users/ZK/OpenCode/quant-runner` |
| Runner strategy kind | `hype_mii_v13` |
| Runner strategy module | `crates/quant-runner/src/strategies/hype_mii_v13/mod.rs` |
| Research evidence | `research-notes/hype-15m-mii-v1-2-atr-dynamic-leverage-2026-07-01.md` |
| Core ledger | `hype-15m-mii-core-ledger.md` |

`V1.3` 不属于 `HYPE-EMA-Crossover`、`HYPE-EMA-Trend-Breakout`、`HYPE-Candle-Count-Reversal` 或 `HYPE-15M-Pullback-Trail`。不要用裸 `V1.3` 判断策略身份。

## 数据与质量要求

研究回测使用 Binance USD-M futures HYPEUSDT `15m` 标准 raw/normalized 数据湖：

- 覆盖：`2025-05-30T10:30:00+00:00` 到 `2026-06-26T04:00:00+00:00`。
- Rows：`37,607`。
- Data quality gate：`True`。
- 已检查问题：gap `0`、duplicate `0`、critical null `0`、invalid OHLC `0`、open bar `0`、raw/normalized mismatch `0`。

最低输入字段：

- `ts`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `is_closed`
- `exchange`
- `symbol`
- `market_type`
- `timeframe`
- `source`

实盘 runner 只能处理已闭合 K。若 Binance API 返回最近未闭合 K，必须丢弃未闭合 K 后再计算信号。

## 参数总表

### 市场与 runner

| 参数 | 值 | 说明 |
| --- | ---: | --- |
| `kind` | `hype_mii_v13` | `quant-runner` 策略类型。 |
| `strategy_id` | `HYPE-15M-MII-V1.3` | 事件、状态和订单前缀中使用的策略身份。 |
| `symbol` | `HYPE/USDT:USDT` | Binance USD-M HYPE 永续。 |
| `timeframe` | `15m` | 固定 15 分钟 K。 |
| `warmup_bars` | `2500` | runner 默认拉取闭合 K 数量；必须足够覆盖 `ATR96`、`RVOL96`、MACD warmup。 |
| `mode` | `dry_run` 或 `live` | 当前配置示例默认 `dry_run` 且 `enabled=false`。 |
| `cycle_delay_seconds` | `3.0` | 新 K 形成后等待 3 秒再处理，降低刚闭合数据未稳定的风险。 |
| `order_client_id_prefix` | `qrmii13-` | Binance client order id 前缀。 |

### 信号与过滤

| 参数 | 值 | 说明 |
| --- | ---: | --- |
| `side` | `both` | 多空双向。 |
| `rsi_window` | `7` | 反转信号使用 `RSI(7)`。 |
| `rsi_long_cross` | `40.0` | `RSI7` 从下向上穿越 `40` 触发多头候选。 |
| `rsi_short_cross` | `60.0` | `RSI7` 从上向下穿越 `60` 触发空头候选。 |
| `macd_fast` | `12` | MACD 快 EMA span。 |
| `macd_slow` | `26` | MACD 慢 EMA span。 |
| `macd_signal` | `9` | MACD signal EMA span。 |
| `min_dir_macd` | `0.0` | 方向化 `MACD histogram` 必须非负。 |
| `min_atr_pct96` | `0.0075` | 仅当 `ATR96% >= 0.75%` 时允许交易。 |
| `max_atr_pct96` | `0.028` | 仅当 `ATR96% <= 2.80%` 时允许交易。 |
| `min_rvol96` | `1.0` | 仅当 `RVOL96 >= 1.0` 时允许交易。 |
| `h1_confirm` | `false` | 不启用 1h 方向确认。 |
| `rsi14_band` | `false` | 不启用 RSI14 区间过滤。 |
| `cooldown_bars` | `0` | 无额外冷却；但 runner 单仓状态会阻止重叠开仓。 |

### 出场与持仓

| 参数 | 值 | 说明 |
| --- | ---: | --- |
| `exit_kind` | `atr_fixed_bracket` | 入场时设置一次性固定 TP/SL。 |
| `atr_window_for_exit` | `96` | 使用信号 K 的 `ATR96%`。 |
| `tp_atr_mult` | `1.25` | 止盈距离为 `1.25 * ATR96%`。 |
| `sl_atr_mult` | `5.0` | 止损距离为 `5.0 * ATR96%`。 |
| `timeout_bars` | `24` | 最长持有 24 根 `15m` K，约 6 小时。 |
| `trailing` | `false` | 不移动 TP/SL。 |
| `same_bar_priority` | `stop_first` | 同一根 K 同时触发止盈止损时按止损优先。 |
| `timeout_exit` | `market_or_open_proxy` | 研究回测用 timeout open；live runner 超时应市价减仓。 |

### 暴露、成本与 Binance 设置

| 参数 | 值 | 说明 |
| --- | ---: | --- |
| `exposure` | `2.5` | 固定 `2.5x` 权益暴露，是下单名义规模倍数。 |
| `leverage` | `3` | Binance 交易所整数杠杆设置；不是策略收益缩放参数。 |
| `margin_mode` | `isolated` | 隔离保证金。 |
| `dry_run_notional_usdt` | `10.0` | dry-run 基准名义本金；实际订单量按 `notional * exposure / price` 估算。 |
| `live_notional_usdt` | `10.0` | live 基准名义本金；未审计前不得直接启用。 |
| `max_live_notional_usdt` | `25.0` | 单实例 live notional 上限。 |
| `fee_rate_per_fill` | `0.001` | 研究和 dry-run 估算手续费：每 fill `0.1000%`。 |
| `entry_slippage_rate` | `0.0004` | 研究和 dry-run 估算入场滑点：`4 bps`。 |
| `exit_slippage_rate` | `0.0004` | 研究和 dry-run 估算出场滑点：`4 bps`。 |
| `round_trip_cost` | `0.0028` | 一进一出合计成本：`0.28%`。 |
| `funding` | 未计入 | 永续资金费是 live 前 blocker。 |

## 指标定义

所有指标只能使用信号 K `t` 收盘时已经可见的数据。禁止使用入场 K 或未来 K 更新入场信号、过滤条件或 bracket。

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

研究规格目标口径为 Wilder 风格指数平滑：

```text
delta[t] = close[t] - close[t-1]
gain[t] = max(delta[t], 0)
loss[t] = max(-delta[t], 0)
avg_gain = EWM(gain, alpha=1/7, adjust=false, min_periods=7)
avg_loss = EWM(loss, alpha=1/7, adjust=false, min_periods=7)
RSI7 = 100 - 100 / (1 + avg_gain / avg_loss)
```

注意：当前 `quant-runner` 的 `indicators.rs` 中 `rsi()` 使用 rolling mean 计算平均涨跌，而不是 Wilder/EWM。上线前必须用同一段 HYPE `15m` K 线对拍 Python 研究脚本与 runner 的 `RSI7`、信号数量、首批交易路径；若不一致，应先修正 runner 指标口径，再讨论实盘。

### MACD(12,26,9)

```text
ema12 = EWM(close, span=12, adjust=false, min_periods=12)
ema26 = EWM(close, span=26, adjust=false, min_periods=26)
macd = ema12 - ema26
macd_signal = EWM(macd, span=9, adjust=false, min_periods=9)
macd_hist = macd - macd_signal
```

方向过滤：

```text
long  requires macd_hist[t] >= 0
short requires macd_hist[t] <= 0
```

### ATR96%

```text
atr96[t] = rolling_mean(TR, window=96, min_periods=96)
atr_pct96[t] = atr96[t] / close[t]
```

### RVOL96

```text
rvol96[t] = volume[t] / rolling_mean(volume, window=96, min_periods=96)
```

## 信号逻辑

在闭合信号 K `t` 上计算：

```text
long_raw[t]  = RSI7[t] > 40 and RSI7[t-1] <= 40
short_raw[t] = RSI7[t] < 60 and RSI7[t-1] >= 60
```

候选方向：

```text
if long_raw[t]:
  direction = +1
if short_raw[t]:
  direction = -1
```

过滤：

```text
macd_filter = macd_hist[t] * direction >= 0
atr_filter = 0.0075 <= atr_pct96[t] <= 0.028
rvol_filter = rvol96[t] >= 1.0
candidate_entry = raw_signal and macd_filter and atr_filter and rvol_filter
```

若同一根 K 同时出现多空原始信号，必须视为实现异常或需要显式优先级；正常 RSI cross 逻辑下不应同根同时触发。

## Bracket 计算

使用信号 K `t` 已知的 `ATR96%`。不要使用入场后的高低点或后续 K 更新 bracket。

```text
dynamic_atr_pct = atr_pct96[t]
take_profit_pct = dynamic_atr_pct * 1.25
stop_pct = dynamic_atr_pct * 5.0
```

研究回测价格：

```text
entry_price = open[t + entry_delay_bars]
```

Live runner 价格：

```text
entry_price = actual_market_fill_price
```

目标价和止损价：

```text
if direction == +1:
  take_profit_price = entry_price * (1 + take_profit_pct)
  stop_price = entry_price * (1 - stop_pct)

if direction == -1:
  take_profit_price = entry_price * (1 - take_profit_pct)
  stop_price = entry_price * (1 + stop_pct)
```

## 执行时序

### 研究主口径

```text
entry_delay_bars = 1
entry_i = signal_i + 1
entry_ts = ts[entry_i]
entry_price = open[entry_i]
```

即闭合 K `t` 确认信号，下一根 `15m` K 的 open 入场。

### 延迟压力测试

```text
entry_delay_bars = 2
entry_i = signal_i + 2
```

`K+2` 只用于延迟压力测试，不是主执行承诺。

### Live runner 口径

`quant-runner` 的 live 行为不是严格等待下一根 K 的 `open` 成交，而是在最新闭合 K 被处理后，用当前合约价格估算、live 模式下用 market order 入场，并以实际成交均价计算 bracket。

这会与研究 K+1 open 回测存在系统性差异。实盘前必须至少完成：

- 研究 K+1 open 与 runner market-entry replay 的对比。
- K+2/K+3 或固定延迟成交压力测试。
- 市价单入场滑点和 stop-market 出场滑点审计。

## 单仓与状态机

规则：

- 同一策略实例同一时间只能有一笔仓位。
- 若 `state.position` 非空，不允许响应新信号。
- 开仓后记录 `signal_ts`、`entry_ts`、`entry_price`、`quantity`、`target_price`、`stop_price`、`timeout_bars`。
- dry-run 用 candle high/low 模拟 bracket 是否触发。
- live 模式必须同时挂 reduce-only TP 和 stop-market SL；若 bracket 任一腿挂单失败，必须撤销另一腿并 emergency reduce。
- timeout 到达后取消未成交 bracket，并用市价减仓。

同 K 冲突：

```text
if stop_hit and target_hit:
  exit_reason = both_hit_stop_first
  exit_price = stop_price
```

## 收益计算

研究回测按权益暴露缩放单笔净收益：

```text
raw_return = direction * (exit_price / entry_price - 1)
round_trip_cost = fee_per_fill + entry_slippage + fee_per_fill + exit_slippage
net_trade_return = exposure * (raw_return - round_trip_cost)
```

`V1.3`：

```text
exposure = 2.5
fee_per_fill = 0.001
entry_slippage = 0.0004
exit_slippage = 0.0004
round_trip_cost = 0.0028
```

资金费未计入，不能把研究净收益当成可实盘收益。

## quant-runner TOML 示例

以下为当前 `/Users/ZK/OpenCode/quant-runner/configs/strategies.toml` 中的参数形状。默认保持 `enabled = false`。

```toml
[[strategies]]
name = "hype-mii-v13-dry-run"
enabled = false
group = "dryrun"
kind = "hype_mii_v13"
mode = "dry_run"
symbol = "HYPE/USDT:USDT"
timeframe = "15m"
account_id = "dryrun"
state_dir = "state/hype-mii-v13-dry-run"

# Binance leverage must be an integer; exposure controls order notional sizing.
leverage = 3
exposure = 2.5
margin_mode = "isolated"
warmup_bars = 2500
dry_run_notional_usdt = 10.0
live_notional_usdt = 10.0
max_live_notional_usdt = 25.0
cycle_delay_seconds = 3.0
live_confirm = false
order_client_id_prefix = "qrmii13-"

[strategies.hype_mii_v13]
strategy_id = "HYPE-15M-MII-V1.3"
exchange = "binance"
symbol = "HYPE/USDT:USDT"
timeframe = "15m"
rsi_window = 7
rsi_long_cross = 40.0
rsi_short_cross = 60.0
macd_fast = 12
macd_slow = 26
macd_signal = 9
min_atr_pct96 = 0.0075
max_atr_pct96 = 0.028
min_rvol96 = 1.0
tp_atr_mult = 1.25
sl_atr_mult = 5.0
timeout_bars = 24
fee_rate_per_fill = 0.001
entry_slippage_rate = 0.0004
exit_slippage_rate = 0.0004
```

若要切到 live，至少还需要：

```toml
mode = "live"
live_confirm = true
account_id = "<live-account-id>"
```

但在本 spec 的状态下不允许直接启用 live。

## 伪代码

```text
for each newly closed 15m candle t:
  load candles and verify continuity
  compute RSI7, MACD(12,26,9), ATR96%, RVOL96 using only closed candles

  if current_position_exists:
    maintain bracket / timeout / exchange reconciliation
    return

  long_raw = RSI7[t] > 40 and RSI7[t-1] <= 40
  short_raw = RSI7[t] < 60 and RSI7[t-1] >= 60

  if long_raw:
    side = +1
  else if short_raw:
    side = -1
  else:
    return no_signal

  if not isfinite(macd_hist[t], atr_pct96[t], rvol96[t]):
    return no_signal

  if side == +1 and macd_hist[t] < 0:
    return no_signal
  if side == -1 and macd_hist[t] > 0:
    return no_signal
  if atr_pct96[t] < 0.0075 or atr_pct96[t] > 0.028:
    return no_signal
  if rvol96[t] < 1.0:
    return no_signal

  entry_price = current live fill price
  tp_pct = atr_pct96[t] * 1.25
  sl_pct = atr_pct96[t] * 5.0
  target_price = entry_price * (1 + side * tp_pct)
  stop_price = entry_price * (1 - side * sl_pct)
  quantity = base_notional_usdt * 2.5 / entry_price

  enter market
  arm reduce-only target and stop-market orders
  persist position state
```

## 回测参考结果

`V1.3` 是固定 `2.5x` sizing 结果，交易集合与 `V1.2` 相同。

| 入场 | 交易数 | 平均杠杆 | 总收益 | 年化 | 最大回撤 | 胜率 | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `K+1` | `184` | `2.500x` | `549.30%` | `472.15%` | `-22.01%` | `84.78%` | `2.179` |
| `K+2` | `189` | `2.500x` | `239.38%` | `212.47%` | `-41.89%` | `82.01%` | `1.612` |

解释：

- K+1 是研究主口径，不等于真实成交承诺。
- K+2 回撤扩大到 `-41.89%`，说明入场时点敏感性仍明显。
- `2.5x` 是 aggressive sizing diagnostic，不是推荐实盘杠杆。

## 实盘前硬性验收

本版本在以下全部完成前只能作为参数规格和 runner dry-run 准备材料：

- 指标对拍：Python 研究脚本与 `quant-runner` 的 `RSI7`、`MACD hist`、`ATR96%`、`RVOL96` 必须逐行或容差内一致。
- 信号对拍：同一数据窗口下，原始信号、过滤后信号、最终单仓交易数必须对齐或解释差异。
- 交易路径对拍：至少对齐前 `20` 笔 K+1 交易的 `signal_ts`、side、entry proxy、TP、SL、exit reason。
- Live-entry replay：用“信号后实际 market entry proxy”复核收益和回撤，不只看 K+1 open。
- 资金费回放：覆盖全部持仓跨 funding 时段的成本。
- 盘口/成交审计：market entry、reduce-only limit TP、stop-market SL 的 tick/盘口级滑点证据。
- 订单状态机：TP 与 SL 同时存在、单腿失败 emergency close、timeout 撤单减仓、重复下单幂等。
- 重启恢复：本地 state 与交易所 position/open orders 对账。
- Missing-bar fail-closed：K 线缺失、重复、时间不连续、API 异常时不得开新仓。
- Kill switch：最大亏损、最大连续亏损、最大持仓时间、最大 notional、手动停机都必须可验证。

## 明确禁止

- 不得把 `enabled` 改为 `true` 并长期无人值守运行，除非已完成上述验收。
- 不得把 `mode` 改为 `live`，除非另有独立 live-feasibility 审计记录批准。
- 不得将 `V1.3` 口头简称为 “live 策略” 或 “paper-live 交接版”。
- 不得因为 runner 已经有代码实现，就绕过资金费、滑点、状态恢复和交易所对账。

## 证据入口

- 主账：`../hype-15m-mii-core-ledger.md`
- `V1.2` 完整复现规格：`hype-15m-mii-v1-2-reproduction-spec-not-live-ready-2026-06-30.md`
- 杠杆诊断：`../research-notes/hype-15m-mii-v1-2-atr-dynamic-leverage-2026-07-01.md`
- 时间片复核：`../research-notes/hype-15m-mii-v1-2-window-slice-backtest-2026-06-30.md`
- 过滤消融：`../research-notes/hype-15m-mii-v1-2-atr-rvol-filter-ablation-2026-06-30.md`
