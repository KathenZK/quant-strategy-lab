---
spec_role: lab_handoff
strategy_id: HYPE-15M-MII-V1.4A
family_id: HYPE-15M-MII
runner_kind: hype_mii
spec_status: active
peer_spec: crates/quant-runner/src/runner/strategies/hype_mii/HYPE-15M-MII-V1.4A-DRY-RUN-SPEC.md
manifest_instance_ids:
  - hype-mii-dry-run
  - hype-mii-live
approval_level_max: dry_run
---

# HYPE-15M-MII-V1.4A Dry-Run Validation Spec（非实盘批准）2026-07-10

Family：`HYPE-15M-Multi-Indicator-Intraday`（alias：`HYPE-15M-MII`）

Version：`HYPE-15M-MII-V1.4A`

Parent version：`HYPE-15M-MII-V1.4`

Status：`user-requested dry-run validation spec / not live-ready`

## 先读结论

这份文件是给 `HYPE-15M-MII-V1.4A` 跑 dry run 用的交接规格，不是 live 批准书。`V1.4A` 继承 `V1.4` 的入场、过滤、成本和 `2.5x` 权益暴露，只修改 ATR bracket 出场：

```text
tp_atr_mult: 1.25 -> 1.40
sl_atr_mult: 5.0 -> 3.0
```

`V1.4A` 的定位是近期窗口 TP/SL 观察变体。它 recent API K+1 最近 `90d/30d` 表现优于 `V1.4 baseline`，但全样本 K+1 明显弱于 `V1.4 baseline`，最近 `7d/72h/24h` 仍然 `0` 笔。因此它适合小额 dry-run / shadow 验证，不应直接替换 live 或当作 `V1.4 baseline`。

[`/Users/ZK/OpenCode/quant-runner`](file:///Users/ZK/OpenCode/quant-runner) 的 `hype_mii` 当前代码默认值固定为：

```text
min_rvol96 = 0.85
tp_atr_mult = 1.40
sl_atr_mult = 3.0
strategy_id = HYPE-15M-MII-V1.4A
```

不要只改显示名称，不改实际策略参数。

## 统一 execution / venue 契约（2026-07-12 代码迁移）

本节只同步 runner 执行架构，不修改 V1.4A 的 RSI/MACD/ATR/RVOL、`2.5x`
exposure、固定 bracket、timeout 或成本口径：

- dry-run 与 live 共用唯一 execution 状态机：稳定 client ID、submit 前持久化、
  `pending/tracked`、按 fill 建仓、保护单、兄弟单撤销、timeout exit、reconcile、
  fail-closed 和 platform ledger。
- live venue 是 Binance REST + User Data Stream；dry-run venue 是实例独立的
  `state/<instance>/simulated_venue.json`。dry-run 也必须通过 symbol-explicit
  order/fill/protection/exit 生命周期，不能直接写策略 position。
- `platform.execution.enabled` 和 live V1 fallback 已删除；V1.4A 仍只允许
  `mode=dry_run`，统一 execution 不是 live approval。
- strict replay/parity 与 venue/runtime 隔离，不读写模拟 venue 状态；本次迁移不应
  改变既有 replay 结果或 `PENDING` parity 状态。
- 当前仅完成代码迁移，尚未部署、未重启线上；promotion 与 live-readiness 不变。

实现状态见
[runner tracking](../runner-tracking/hype-15m-mii-runner-2026-07-10.md)。

## 身份与边界

| 项 | 值 |
| --- | --- |
| Full family name | `HYPE-15M-Multi-Indicator-Intraday` |
| Alias | `HYPE-15M-MII` |
| Version | `HYPE-15M-MII-V1.4A` |
| Parent | `HYPE-15M-MII-V1.4` |
| Exchange | `Binance` |
| Market | `USD-M perpetual` |
| Raw exchange symbol | `HYPEUSDT` |
| CCXT symbol | `HYPE/USDT:USDT` |
| Timeframe | `15m` |
| Timezone | UTC |
| Candle requirement | 只使用已闭合 K |
| Runner repository | [`/Users/ZK/OpenCode/quant-runner`](file:///Users/ZK/OpenCode/quant-runner) |
| Expected runner kind | `hype_mii`，代码默认参数固定为 V1.4A |
| Intended use | dry-run / shadow validation |
| Live status | not live-ready |
| Core ledger | [`../hype-15m-mii-core-ledger.md`](../hype-15m-mii-core-ledger.md) |
| Parameter spec | [`../specs/hype-15m-mii-v1-4a-parameter-spec-not-live-ready-2026-07-09.md`](../specs/hype-15m-mii-v1-4a-parameter-spec-not-live-ready-2026-07-09.md) |
| Main evidence | [`../notes/hype-15m-mii-v1-4-tp-sl-neighborhood-2026-07-09.md`](../notes/hype-15m-mii-v1-4-tp-sl-neighborhood-2026-07-09.md) |

不要用裸 `V1.4A` 判断策略身份；它只在 `HYPE-15M-MII` 家族内有效。`V1.4A` 不是 `V1.4 baseline`，也不是 `HYPE-EMA-Crossover`、`HYPE-EMA-Trend-Breakout`、`HYPE-Candle-Count-Reversal` 或 `HYPE-15M-Pullback-Trail` 的版本。

## Dry-Run 参数总表

### 市场与 runner

| 参数 | 值 | 说明 |
| --- | ---: | --- |
| `kind` | `hype_mii` | 当前代码默认参数固定为 V1.4A。 |
| internal `strategy_id` | `HYPE-15M-MII-V1.4A` | 由 runner 输出到日志和 ledger，不放进 TOML。 |
| `name` | `hype-mii-dry-run` | 实例名不带版本。 |
| `symbol` | `HYPE/USDT:USDT` | Binance USD-M HYPE 永续。 |
| `timeframe` | `15m` | 固定 15 分钟 K。 |
| `warmup_bars` | `2500` | 必须足够覆盖 `ATR96`、`RVOL96`、MACD 和 RSI warmup。 |
| `cycle_delay_seconds` | `3.0` | 新 K 闭合后等待再处理，降低数据未稳定风险。 |
| `mode` | `dry_run` | 本文件只允许 dry-run / shadow validation。 |
| `state_dir` | `/home/admin/quant-runner/state/hype-mii-dry-run` | 沿用既有路径；切换前 V1.3 从未开仓且没有持仓数据。 |

### 信号与过滤

| 参数 | 值 | 说明 |
| --- | ---: | --- |
| `side` | `both` | 多空双向。 |
| `rsi_window` | `7` | 使用 `RSI(7)` 反转。 |
| `rsi_long_cross` | `40.0` | `RSI7` 从下向上穿越 `40` 触发多头候选。 |
| `rsi_short_cross` | `60.0` | `RSI7` 从上向下穿越 `60` 触发空头候选。 |
| `macd_fast` | `12` | MACD 快 EMA span。 |
| `macd_slow` | `26` | MACD 慢 EMA span。 |
| `macd_signal` | `9` | MACD signal EMA span。 |
| `min_dir_macd` | `0.0` | 方向化 `MACD histogram` 必须非负。 |
| `min_atr_pct96` | `0.0075` | 仅当 `ATR96% >= 0.75%` 时允许交易。 |
| `max_atr_pct96` | `0.028` | 仅当 `ATR96% <= 2.80%` 时允许交易。 |
| `min_rvol96` | `0.85` | 沿用 `V1.4`；这是相对 `V1.3` 的入场变化。 |
| `h1_confirm` | `false` | 不启用 1h 方向确认。 |
| `rsi14_band` | `false` | 不启用 RSI14 区间过滤。 |
| `cooldown_bars` | `0` | 无额外冷却；单仓状态阻止重叠开仓。 |

### 出场、暴露与成本

| 参数 | 值 | 说明 |
| --- | ---: | --- |
| `exit_kind` | `atr_fixed_bracket` | 入场时设置一次性固定 TP/SL。 |
| `atr_window_for_exit` | `96` | 使用信号 K 的 `ATR96%`。 |
| `tp_atr_mult` | `1.40` | 止盈距离为 `1.40 * ATR96%`。 |
| `sl_atr_mult` | `3.0` | 止损距离为 `3.0 * ATR96%`。 |
| `timeout_bars` | `24` | 最长持有 24 根 `15m` K，约 6 小时。 |
| `trailing` | `false` | 不移动止损，不使用 trailing stop。 |
| `same_bar_priority` | `stop_first` | 同一根 K 同时触发止盈止损时按止损优先。 |
| `exposure` | `2.5` | 固定 `2.5x` 权益暴露；不是交易所整数杠杆。 |
| `leverage` | `3` | Binance 交易所整数杠杆设置建议；实际 sizing 由 `exposure` 控制。 |
| `margin_mode` | `isolated` | 隔离保证金。 |
| `dry_run_notional_usdt` | `10.0` | 建议沿用小额 dry-run notional。 |
| `fee_rate_per_fill` | `0.001` | Binance 研究成本：每 fill `0.1000%`。 |
| `slippage_per_fill` | `0.0004` | Binance 研究滑点：每 fill `4 bps`。 |
| `round_trip_cost` | `0.0028` | 一进一出合计成本：`0.28%`。 |
| `funding` | 未计入 | dry-run 观察中必须单独记录资金费影响。 |

## 建议 TOML 片段

策略版本和 alpha 参数不放进 TOML；`hype_mii` 当前代码默认值就是 V1.4A。

```toml
[[strategies]]
name = "hype-mii-dry-run"
enabled = true
group = "dryrun"
kind = "hype_mii"
mode = "dry_run"
symbol = "HYPE/USDT:USDT"
timeframe = "15m"
account_id = "dryrun"
state_dir = "/home/admin/quant-runner/state/hype-mii-dry-run"
leverage = 3
exposure = 2.5
margin_mode = "isolated"
warmup_bars = 2500
dry_run_notional_usdt = 10.0
live_confirm = false
```

dry-run 启动和 replay 输出必须打印内部 `strategy_id` 与完整参数快照。

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

验证时必须确认 Python 研究脚本与 runner 使用同一 RSI 口径。研究规格目标口径为 Wilder/EWM：

```text
delta[t] = close[t] - close[t-1]
gain[t] = max(delta[t], 0)
loss[t] = max(-delta[t], 0)
avg_gain = EWM(gain, alpha=1/7, adjust=false, min_periods=7)
avg_loss = EWM(loss, alpha=1/7, adjust=false, min_periods=7)
RSI7 = 100 - 100 / (1 + avg_gain / avg_loss)
```

已知风险：`quant-runner` 历史 `rsi()` 实现曾使用 rolling mean 口径而非 Wilder/EWM。dry-run 前必须把 `RSI7` 数值、raw cross 数量、最终信号和逐笔交易路径与 Python 研究脚本对拍。

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
long requires macd_hist[t] >= 0
short requires macd_hist[t] <= 0
```

### ATR96%

`ATR96` 是 96 根 `15m` K 的 true range 均值，约 24 小时窗口；不是 96 小时 ATR。

```text
atr96[t] = rolling_mean(TR, window=96, min_periods=96)
atr_pct96[t] = atr96[t] / close[t]
```

### RVOL96

```text
rvol96[t] = volume[t] / rolling_mean(volume, window=96, min_periods=96)
```

`V1.4A` 使用：

```text
rvol96[t] >= 0.85
```

## 信号逻辑

在闭合信号 K `t` 上计算：

```text
long_raw[t] = RSI7[t] > 40 and RSI7[t-1] <= 40
short_raw[t] = RSI7[t] < 60 and RSI7[t-1] >= 60
```

方向化过滤：

```text
direction = +1 for long_raw
direction = -1 for short_raw

macd_filter = macd_hist[t] * direction >= 0
atr_filter = 0.0075 <= atr_pct96[t] <= 0.028
rvol_filter = rvol96[t] >= 0.85

candidate_entry = raw_signal and macd_filter and atr_filter and rvol_filter
```

若同一根 K 同时出现多空 raw signal，必须视为实现异常或需要显式优先级；正常 RSI cross 逻辑下不应同根同时触发。

## Bracket 计算

Bracket 使用信号 K `t` 已知的 `ATR96%`。不要使用入场后任何高低点或未来 K 更新 bracket。

```text
dynamic_atr_pct = atr_pct96[t]
take_profit_pct = dynamic_atr_pct * 1.40
stop_pct = dynamic_atr_pct * 3.0
```

研究回测：

```text
entry_price = open[t + entry_delay_bars]
```

Dry-run runner：

```text
entry_price = dry-run fill proxy or actual paper fill model
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

### 研究主口径 K+1

```text
signal_i = index of closed candle t
entry_delay_bars = 1
entry_i = signal_i + 1
entry_ts = ts[entry_i]
entry_price = open[entry_i]
```

即闭合 K `t` 确认信号，下一根 `15m` K 的 open 入场。

### 延迟压力测试 K+2

```text
entry_delay_bars = 2
entry_i = signal_i + 2
```

`K+2` 用于延迟压力测试，不是主执行承诺。dry-run 验证报告必须同时输出 K+1 和 K+2 replay。

### Runner 口径

若 runner 在最新闭合 K 被处理后用 market/dry-run fill proxy 入场，则它不是严格研究 K+1 open。验证时必须单独记录：

- 信号 K close 时间。
- runner 实际触发时间。
- dry-run fill proxy。
- 相对 K+1 open 的偏差。
- bracket 是否用 dry-run fill proxy 计算。

## 单仓与状态机

规则：

- 同一策略实例同一时间只能有一笔仓位。
- 若 `state.position` 非空，不允许响应新信号。
- 开仓后记录 `signal_ts`、`entry_ts`、`entry_price`、`quantity`、`target_price`、`stop_price`、`timeout_bars`。
- dry-run/replay 可用 candle high/low 模拟 bracket 是否触发。
- timeout 到达后按 dry-run exit proxy 减仓。
- `V1.4A` 沿用 `hype-mii-dry-run` state_dir；切换前必须确认旧实例从未开仓且没有持仓数据。

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

`V1.4A` 成本参数：

```text
exposure = 2.5
fee_per_fill = 0.001
entry_slippage = 0.0004
exit_slippage = 0.0004
round_trip_cost = 0.0028
```

资金费未计入，不能把研究净收益当成可实盘收益。dry-run 期间应记录每笔持仓是否跨 funding timestamp。

## 预期回放指标

标准数据湖（`2025-05-30T10:30:00Z` 到 `2026-07-08T05:30:00Z`，quality gate `True`）：

| 入场 | 交易数 | 总收益 | 最大回撤 | 胜率 | Profit Factor | 最差单笔 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `K+1` | `235` | `584.90%` | `-32.85%` | `78.72%` | `1.735` | `-10.971%` |
| `K+2` | `238` | `637.85%` | `-34.58%` | `79.83%` | `1.749` | `-11.650%` |

Recent Binance API（2026-07-09 报告口径）：

| 入场 | 窗口 | 交易数 | 总收益 | 最大回撤 | 胜率 | Profit Factor | 最差单笔 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `K+1` | `最近90d` | `45` | `78.82%` | `-19.58%` | `84.44%` | `2.437` | `-9.108%` |
| `K+1` | `最近30d` | `15` | `27.09%` | `-8.64%` | `86.67%` | `3.842` | `-6.386%` |
| `K+2` | `最近90d` | `46` | `67.07%` | `-21.49%` | `82.61%` | `2.115` | `-9.108%` |
| `K+2` | `最近30d` | `15` | `19.30%` | `-8.69%` | `80.00%` | `2.673` | `-6.386%` |

Recent Binance API 最近 `24h/72h/7d`：`0` 笔。dry-run 刚启动后可能长时间无交易，不应被误判为 runner 故障；需同时观察信号漏斗。

## Dry-Run 启动前检查

启动前至少确认：

- runner 参数快照打印 `strategy_id=HYPE-15M-MII-V1.4A`。
- 参数快照打印 `min_rvol96=0.85`、`tp_atr_mult=1.40`、`sl_atr_mult=3.0`。
- 沿用 state_dir 前已确认旧实例从未开仓且当前无持仓。
- 已丢弃未闭合 K。
- warmup K 数足够。
- dry-run 下单 notional 小额。
- missing-bar 时 fail-closed，不允许开新仓。
- 指标、信号和逐笔路径至少用标准数据湖对拍一次。

## Dry-Run 观察报告最低字段

每日报告至少记录：

- runner commit / config hash。
- strategy_id 和完整参数快照。
- 数据窗口、最近闭合 K 时间、是否有缺 K。
- raw RSI cross 数量。
- ATR/RVOL/MACD 过滤后信号数量。
- 最终信号数量。
- 是否因已有持仓跳过信号。
- open position、entry、TP、SL、timeout。
- exit reason、gross return、cost estimate、net return。
- 与 Python replay 的差异。

## 禁止项

- 禁止把本文件解释为 live approval。
- 禁止把 `V1.4A` 当成 `V1.4 baseline`。
- 禁止只改策略名、不改 `min_rvol96/tp_atr_mult/sl_atr_mult`。
- 若旧 state 中存在持仓或交易生命周期数据，禁止直接复用；本次仅因旧实例从未开仓而沿用。
- 禁止使用未闭合 K 生成信号或更新 stop/TP。
- 禁止用未来 K 的 ATR、RVOL、MACD 或 RSI 修改入场决策。
- 禁止省略 Binance 成本；默认成本为手续费 `0.001`/fill、滑点 `4 bps`/fill。
- 禁止在未完成资金费、盘口级滑点、交易所对账、重启恢复和 kill switch 审计前切 live。

## 证据链接

- 主账：[`../hype-15m-mii-core-ledger.md`](../hype-15m-mii-core-ledger.md)
- 决策日志：[`../decision-log.md`](../decision-log.md)
- V1.4A 参数规格：[`../specs/hype-15m-mii-v1-4a-parameter-spec-not-live-ready-2026-07-09.md`](../specs/hype-15m-mii-v1-4a-parameter-spec-not-live-ready-2026-07-09.md)
- V1.4 参数规格：[`../specs/hype-15m-mii-v1-4-parameter-spec-not-live-ready-2026-07-08.md`](../specs/hype-15m-mii-v1-4-parameter-spec-not-live-ready-2026-07-08.md)
- V1.4 TP/SL 邻域搜索：[`../notes/hype-15m-mii-v1-4-tp-sl-neighborhood-2026-07-09.md`](../notes/hype-15m-mii-v1-4-tp-sl-neighborhood-2026-07-09.md)
- 标准数据湖 TP/SL 邻域 CSV：[`../artifacts/hype_15m_mii_v1_4_tp_sl_neighborhood_standard_2026-07-09.csv`](../artifacts/hype_15m_mii_v1_4_tp_sl_neighborhood_standard_2026-07-09.csv)
- Recent API TP/SL 邻域 CSV：[`../artifacts/hype_15m_mii_v1_4_tp_sl_neighborhood_recent_2026-07-09.csv`](../artifacts/hype_15m_mii_v1_4_tp_sl_neighborhood_recent_2026-07-09.csv)
