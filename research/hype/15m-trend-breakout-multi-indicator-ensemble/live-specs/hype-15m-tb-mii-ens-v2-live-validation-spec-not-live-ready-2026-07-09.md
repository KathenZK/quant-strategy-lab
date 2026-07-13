---
spec_role: lab_handoff
strategy_id: HYPE-15M-TB-MII-ENS-V2
family_id: HYPE-15M-TB-MII-ENS
runner_kind: hype_tb_mii_ensemble
spec_status: active
peer_spec: crates/quant-runner/src/runner/strategies/hype_tb_mii_ensemble/HYPE-15M-TB-MII-ENS-V2-SPEC.md
manifest_instance_ids:
  - hype-tb-mii-ens-dry-run
  - hype-tb-mii-ens-live
approval_level_max: dry_run
---

# HYPE-15M-TB-MII-ENS V2 Runtime Validation Spec（dry-run active）

规格 id：`HYPE-15M-TB-MII-ENS-V2-LIVE-VALIDATION-SPEC-2026-07-09`

Family：`HYPE-15M-Trend-Breakout-Multi-Indicator-Ensemble`（alias：`HYPE-15M-TB-MII-ENS`）

Version：`V2`

Status：`dry-run active / replay parity PASS / live disabled / not live-ready`

## 先读结论

本文档现用于描述已实现的 replay 与连续 dry-run runtime；它不是实盘批准书，
live 实例仍保持 disabled。

历史说明：2026-07-09 的首次 live-executable 静态审计曾因 runner、
preempt、恢复和 kill switch 未实现而失败；这些代码缺口后来已关闭。
该历史报告不再描述当前实现状态，但真实订单故障注入、funding 和 live 审批
仍是 blocker。详见
[`../diagnostics/hype-15m-tb-mii-ens-v2-live-executable-audit-2026-07-09.md`](../diagnostics/hype-15m-tb-mii-ens-v2-live-executable-audit-2026-07-09.md)。

`V2` 的定义是：

```text
V2 = HYPE-EMA-TB-V39 + HYPE-15M-MII-V1.4
账户结构 = single_v39_priority_k1
仲裁 = 全局单仓；V39 优先；V1.4 持仓时若 V39 入场信号到达，强平 V1.4 后让位给 V39
```

当前已经在实盘运行过的 `V35` 是 `HYPE-EMA-Trend-Breakout-V35` 单腿 runner。`V2` 不是在 V35 runner 上改参数即可运行：它需要新增组合状态机、MII V1.4 腿、全局单仓仲裁、preempt 换仓原子性、双母策略指标/路径对拍和组合层重启恢复。

进入任何真金 live 前，必须先完成本文的 replay / dry-run / shadow validation 门禁。若只是想“实盘看看”，建议顺序是：

1. 实现 runner 但 `enabled=false`。
2. 用标准数据湖 replay 对拍 Python 组合脚本。
3. 用 Binance recent closed candles 做 shadow/dry-run，不下真实单。
4. 通过风控、恢复、保护单、preempt 审计后，再由用户显式批准小资金 live pilot。

## 统一 execution / venue 契约（2026-07-12 代码迁移）

本节只同步 runner 执行架构，不改 V39/V1.4 参数、组合仲裁或 replay 定义：

- dry-run 与 live 共用唯一 execution 状态机：稳定 client ID、submit 前持久化、
  `pending/tracked`、按 fill 建仓、保护单、兄弟单撤销、reconcile、fail-closed
  与 platform ledger。
- V39 与 MII 的 entry/exit、timeout、保护单，以及 V39 优先的
  `preempt close -> confirm flat -> open V39` 都必须通过同一订单生命周期。
- live venue 是 Binance REST + User Data Stream；dry-run venue 是实例独立的
  `state/<instance>/simulated_venue.json`。dry-run preempt 也要经过显式 cancel、
  close fill、flat reconcile，再允许新 entry。
- `platform.execution.enabled` 和 live V1 fallback 已删除；旧 executor 不得用于
  bypass。
- strict replay/parity 保持隔离，不读取或改写 simulated/live venue state；
  既有 `291` 笔 trade-path parity PASS 不因本次迁移改变。
- 统一 execution 已于 `2026-07-13T04:25Z` 部署到 dry-run service；本实例 flat、
  health=`ok`，没有新增 TB-MII fill。promotion、parity 与 live-readiness
  状态全部不变。实现补记见
  [runner implementation tracking](../runner-tracking/hype-15m-tb-mii-ens-v2-runner-implementation-smoke-2026-07-09.md)。
- 稳定性补充契约（Runner `e69589f`，已于 `2026-07-13 21:02 CST`
  部署 dry-run）：transient dependency 只关闭新入场，
  不能清除或绕过 preempt/execution fail-closed，也不得停止已有风险维护；单 group
  故障不得终止兄弟策略。

## 身份与边界

| 项 | 值 |
| --- | --- |
| Full family name | `HYPE-15M-Trend-Breakout-Multi-Indicator-Ensemble` |
| Alias | `HYPE-15M-TB-MII-ENS` |
| Version | `V2` |
| Trend leg | `HYPE-EMA-Trend-Breakout-V39` |
| Reversal leg | `HYPE-15M-Multi-Indicator-Intraday-V1.4` |
| Account mode | 单账户、全局最多一笔仓位 |
| Arbitration | V39 优先；V1.4 可被 V39 preempt |
| Exchange | Binance |
| Market | USD-M perpetual |
| Raw exchange symbol | `HYPEUSDT` |
| CCXT symbol | `HYPE/USDT:USDT` |
| Timeframe | `15m` |
| Timezone | UTC |
| Candle requirement | 只使用已闭合 K |
| Current V35 live repo | [`/Users/ZK/OpenCode/hype-trend`](file:///Users/ZK/OpenCode/hype-trend) |
| Current V35 service | `hype-trend-binance-live` |
| Expected V2 runner | 新 runner / 新 strategy kind；不得直接复用 V35 service 配置上线 |
| Proposed V2 service name | `hype-tb-mii-ens-v2-binance-dry-run`，live pilot 前另建 `hype-tb-mii-ens-v2-binance-live` |
| Core ledger | [`../hype-15m-tb-mii-ens-core-ledger.md`](../hype-15m-tb-mii-ens-core-ledger.md) |
| Combo backtest report | [`../notes/hype-15m-tb-mii-ensemble-v39-v14-combination-backtest-2026-07-09.md`](../notes/hype-15m-tb-mii-ensemble-v39-v14-combination-backtest-2026-07-09.md) |
| Weekly / recent audit | [`../notes/hype-15m-tb-mii-ens-v2-weekly-trade-audit-2026-07-09.md`](../notes/hype-15m-tb-mii-ens-v2-weekly-trade-audit-2026-07-09.md) |

不要用裸 `V2` 判断策略身份；本文的 `V2` 只属于 `HYPE-15M-TB-MII-ENS` 组合家族，不是 `HYPE-EMA-TB` 或 `HYPE-15M-MII` 母家族的版本号。

## 状态与 blocker

当前状态保持：

```text
V2 dry-run active / replay parity PASS / live disabled / not live-ready
```

进入 runner dry-run 前至少需要完成：

- 新增 V2 runner 或 strategy kind，不能让现有 V35 live service 同时管理同一 Binance 账户 / HYPEUSDT 仓位。
- V39 腿实现与 [`HYPE-EMA-TB-V39 live spec`](../../15m-ema-trend-breakout/live-specs/hype-ema-tb-v39-live-spec-not-live-ready-2026-07-09.md) 对齐。
- V1.4 腿实现与 [`HYPE-15M-MII-V1.4 live validation spec`](../../15m-multi-indicator-intraday/live-specs/hype-15m-mii-v1-4-live-validation-spec-not-live-ready-2026-07-09.md) 对齐。
- 组合层 replay 对拍：`single_v39_priority_k1` 的逐 K 状态、逐笔路径、preempt 次数、权益曲线与 Python 研究脚本一致。
- live-executable 审计：真实下单时序、保护单、preempt 强平让位、重启恢复、missing-bar fail-closed、交易所对账、kill switch。
- V1.4 腿 funding 回放或 live 侧真实 funding 记账解释；研究回测中 MII 腿 funding 未计入。
- 小资金 pilot 前完成 dry-run 或 shadow 至少覆盖多个 V39 与 V1.4 信号，并产出差异报告。

## 与现有 V35 实盘的切换边界

当前 V35 live runner 是单腿 `HYPE-EMA-Trend-Breakout-V35`。V2 上线验证时必须遵守：

- 不允许 V35 live service 与 V2 live service 在同一个 Binance 账户、同一个 `HYPE/USDT:USDT` 上同时下真实单。
- 若 V2 进入 live pilot，必须先停 V35 service，或使用完全隔离的 Binance subaccount。
- 若 V2 只做 shadow/dry-run，可以与 V35 live 并行，但 V2 不得提交真实订单，也不得撤改 V35 的订单。
- V2 不能读取 V35 local state 后直接接管；必须从交易所真实 position、open orders 和自身 V2 state 重建。
- 任何切换窗口都必须先确认：交易所 HYPE 仓位、open orders、local state、SQLite/event log 一致；不一致时禁止启动 V2 live。

## 数据与质量要求

研究证据使用 Binance USD-M futures `HYPEUSDT` `15m` 标准 raw/normalized 数据湖：

| 项 | 值 |
| --- | --- |
| 数据窗口 | `2025-05-30T10:30:00Z` 至 `2026-07-08T05:30:00Z` |
| 已闭合 K 线 | `38,765` |
| 组合评估起点 | `2025-06-16T02:30:00Z` |
| quality gate | missing bar / duplicate / invalid OHLC / critical null / raw-normalized mismatch 全 `0` |
| funding | V39 腿计入；MII 腿研究回测未计 |

runner 最低输入字段：

```text
ts, open, high, low, close, volume, quote_volume, trade_count, vwap, is_closed
```

硬要求：

- `ts` 必须是 UTC，表示 `15m` K 线开盘时间。
- 只允许已闭合 K 参与信号、指标、MFE、timeout、V1.4 bracket 计算。
- 若最新 K 未闭合，必须丢弃后再计算。
- 缺 K、重复 K、非法 OHLC、关键字段空值、raw/normalized 不一致时，runner 必须 fail-closed：停止新开仓，已有仓位进入保护/只减仓模式。
- 启动建议预加载至少 `2500` 根已闭合 `15m` K，覆盖 V39 的 `ATR672/EMA384/1h` 特征和 V1.4 的 `ATR96/RVOL96/MACD/RSI`。

## 成本与资金费

研究回测成本口径：

| 腿 | 成本 | funding |
| --- | --- | --- |
| V39 | `0.00085` / fill，含手续费与 4 bps adverse slippage 合并口径 | included |
| V1.4 | fee `0.001` / fill + slippage `0.0004` / fill，round-trip `0.28%` | 未计 |

live runner 必须使用真实成交价、真实手续费和真实 funding 记账。研究成本只用于 replay 对拍与估算，不得作为 live PnL 事实源。

## V2 参数总表

### 组合层

| 参数 | 值 | 说明 |
| --- | --- | --- |
| `strategy_id` | `HYPE-15M-TB-MII-ENS-V2` | 事件、状态、订单前缀必须带组合版本 |
| `symbol` | `HYPE/USDT:USDT` | Binance USD-M HYPE 永续 |
| `timeframe` | `15m` | 固定 |
| `global_position_limit` | `1` | 全局最多一笔仓位 |
| `priority_leg` | `ema_tb_v39` | V39 优先 |
| `secondary_leg` | `mii_v14` | 只在 V39 空档开仓 |
| `preempt_secondary` | `true` | V39 入场时可强平 V1.4 |
| `same_bar_reentry_after_trend_exit` | `false` | V39 刚退出同根不重入 |
| `mii_entry_delay_bars` | `1` | V1.4 主口径 K+1 open |
| `trend_entry_delay_bars` | `2` | V39 K+2 open |
| `margin_mode` | `isolated` | 建议隔离 |
| `exchange_leverage` | `3` 或更高 | 必须覆盖 V39 `3.0x` 与 V1.4 `2.5x` 名义暴露 |
| `enabled` | `false` | 实现后默认关闭 |
| `mode` | `replay` / `dry_run` | live pilot 前不得直接 `live` |

### V39 腿

V39 参数以 [`HYPE-EMA-TB-V39 live spec`](../../15m-ema-trend-breakout/live-specs/hype-ema-tb-v39-live-spec-not-live-ready-2026-07-09.md) 为准。组合层必须至少锁定：

| 参数 | 值 |
| --- | ---: |
| `ema_fast` | `96` |
| `ema_slow` | `384` |
| `adx_window` | `28` |
| `atr_window` | `672` |
| `volume_window` | `192` |
| `long_adx_min` | `28.0` |
| `short_adx_min` | `36.0` |
| `long_vol_min` | `0.35` |
| `short_vol_min` | `0.50` |
| `short_use_h1_ema` | `false` |
| `long_target_atr_pct` | `0.020` |
| `short_target_atr_pct` | `0.022` |
| `max_allocation` | `3.0` |
| `take_profit_atr` | `5.0` |
| `hard_stop_atr` | `7.0` |
| `adx_exit` | `22.0` |
| `delayed_bars` | `3` |
| `disable_after_mfe_atr` | `1.5` |
| `max_hold_bars` | `384` |

### V1.4 腿

V1.4 参数以 [`HYPE-15M-MII-V1.4 live validation spec`](../../15m-multi-indicator-intraday/live-specs/hype-15m-mii-v1-4-live-validation-spec-not-live-ready-2026-07-09.md) 为准。组合层必须至少锁定：

| 参数 | 值 |
| --- | ---: |
| `rsi_window` | `7` |
| `rsi_long_cross` | `40.0` |
| `rsi_short_cross` | `60.0` |
| `macd_fast` | `12` |
| `macd_slow` | `26` |
| `macd_signal` | `9` |
| `min_atr_pct96` | `0.0075` |
| `max_atr_pct96` | `0.028` |
| `min_rvol96` | `0.85` |
| `exposure` | `2.5` |
| `tp_atr_mult` | `1.25` |
| `sl_atr_mult` | `5.0` |
| `timeout_bars` | `24` |
| `same_bar_priority` | `stop_first` |

## 组合状态机

V2 研究脚本的单账户循环顺序如下，runner replay 必须逐步对拍：

```text
for each closed/current execution bar i:
  1. 若 V39 有 pending indicator_exit / timeout，按本根 open 出场
  2. 若 V1.4 有 open-type exit（max_hold/gap），按本根 open 出场
  3. 若 V39 持仓，计入本 bar funding
  4. 检查 V39 K+2 入场：
       - 若 V1.4 正在持仓且 preempt=true：
           先强平 V1.4，记录 exit_reason=preempted_by_v39
           再开 V39
       - 若 preempt 失败，不得开 V39
  5. 若 V39 持仓，处理 intrabar TP/SL；否则按 close mark 并更新 MFE / indicator exit / timeout
  6. 若全局空仓且本根无 V39 入场，检查 V1.4 K+1 入场
  7. 若 V1.4 持仓，处理 bracket/timeout 出场；否则按 close mark-to-market
```

live runner 与研究脚本不同的地方必须显式处理：

- 研究脚本用 OHLC 模拟 intrabar TP/SL；live 必须使用 reduce-only 保护单或等价交易所风控。
- 研究脚本用 `open` 作为入场/部分出场价格；live 必须用真实成交均价，并记录相对目标 open 的 slippage。
- V1.4 preempt 在研究中按当前 open 强平；live 中必须先取消 V1.4 保护单、提交 reduce-only market close、确认成交后，才允许开 V39。
- 若 preempt close 未确认、部分成交、被拒绝或交易所状态不一致，必须 fail-closed，不得裸开 V39。

## 订单与保护单规范

### 入场

- V39：信号 K0 close 确认，K2 open 目标入场；live 使用 market order 或受控 IOC/marketable order。
- V1.4：信号 K0 close 确认，K1 open 目标入场；live 使用 market order 或受控 IOC/marketable order。
- 入场前必须确认全局无仓、无未归属 open orders、local state 与交易所状态一致。
- 订单 quantity 按 `account_equity * allocation / fill_price` 估算，必须经过 tick/step/min-notional 校正。

### 保护单

入场成交确认后立即放置 reduce-only TP/SL：

- V39：固定 `5ATR` TP、`7ATR` hard SL，基于真实 entry fill price 和 entry ATR。
- V1.4：固定 `1.25 * ATR96%` TP、`5.0 * ATR96%` SL，基于真实 entry fill price 和信号 K ATR96%。
- 任一保护单挂单失败，必须进入 fail-closed：撤销另一腿保护单，emergency reduce 或停止新风险。
- live 中同一根 K 同时触发 TP/SL 的研究 `stop_first` 只用于 replay；真实成交以交易所先成交订单为准，但 audit 必须记录顺序。

### V1.4 强平让位

preempt 必须是原子流程：

```text
V39 entry due at current bar
if active_leg == mii_v14:
  pause new signals
  cancel MII reduce-only TP/SL orders
  submit reduce-only market close for MII remaining position
  wait until exchange position is flat or lower than dust threshold
  record exit_reason = preempted_by_v39
  only then submit V39 entry
```

禁止：

- 未确认 V1.4 已平仓就开 V39。
- 用非 reduce-only close 让账户可能反向开仓。
- preempt 失败后继续响应本根其它信号。
- 在手动仓位或未知 open orders 存在时执行 preempt。

## 状态与重启恢复

V2 runner state 至少保存：

```text
strategy_id
last_processed_bar_ts
active_leg: none | ema_tb_v39 | mii_v14
entry_signal_ts
entry_ts
entry_bar_index
direction
entry_price
quantity
allocation_or_exposure
entry_atr_or_atr_pct
tp_price
sl_price
timeout_bar
v39_weak_bars
v39_mfe_atr
v39_pending_exit
mii_available_bar
exchange_order_ids
preempt_in_progress
```

重启流程：

1. 读取 local state。
2. 拉交易所真实 position 与 open orders。
3. 若 local state 为空但交易所有仓，进入 `unexpected_position`，停止新开仓并告警。
4. 若 local state 有仓但交易所无仓，按交易所事实同步退出，记录 `exchange_exit_synced`。
5. 若保护单缺失或数量不匹配，尝试恢复一次；失败则 fail-closed。
6. 若 `preempt_in_progress=true`，先恢复/完成只减仓流程，不允许直接开新仓。
7. 从最近已闭合 K 恢复指标状态，禁止补假 K。

## 风控与 kill switch

V2 live pilot 前必须实现：

- 手动暂停新开仓：不影响已有保护单。
- 手动全平：取消保护单后 reduce-only market close。
- 日内亏损限制：达到阈值后停止新开仓，只允许减仓。
- 单笔最大 notional 限制：小资金 pilot 必须有硬上限，不能只依赖 `2.5x/3.0x`。
- 连续错误限制：连续 N 次数据、订单、通知、状态恢复错误后停止策略。
- missing-bar fail-closed：缺 K 或 stale candle 时停止新开仓。
- DingTalk 或等价告警：启动、停机、开仓、出场、保护单失败、preempt、重启恢复、unexpected position、kill switch。

建议 pilot 阶段使用独立 subaccount 和极小 notional；不要直接继承 V35 当前 live 资金规模。

## 预期研究指标

标准数据湖至 `2026-07-08T05:30:00Z`，组合评估窗口从 `2025-06-16T02:30:00Z` 起：

| 口径 | 总收益 | 最大回撤 | Sharpe | 交易数 | 胜率 | preempt |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `single_v39_priority_k1` | `+68192.54%` | `-28.01%` | `5.79` | `291` | `82.82%` | `3` |
| 最近 `6m` | `+3841.84%` | `-22.05%` | - | `137` | `83.21%` | `2` |
| 最近 `3m` | `+324.62%` | `-21.90%` | - | `72` | `80.56%` | `1` |

腿分布：

- 全样本：`291` 笔 = V39 `107` + V1.4 `184`。
- 过去一年：`274` 笔 = V39 `104` + V1.4 `170`，胜率 `83.21%`。
- 最近 `3m`：V39 `35` 笔，胜率 `77.14%`；V1.4 `37` 笔，胜率 `83.78%`。

这些是 replay 对拍目标，不是 live 收益承诺。

## Runner 配置

V2 runner 已实现，生产 dry-run 实例为 `hype-tb-mii-ens-dry-run`。
以下配置仍只用于说明身份；live 必须继续由 manifest/lock 门禁控制。

```toml
[[strategies]]
name = "hype-tb-mii-ens-dry-run"
enabled = true
group = "dryrun"
kind = "hype_tb_mii_ensemble"
mode = "dry_run"
symbol = "HYPE/USDT:USDT"
timeframe = "15m"
account_id = "dryrun"
state_dir = "/home/admin/quant-runner/state/hype-tb-mii-ens-dry-run"
leverage = 3
margin_mode = "isolated"
warmup_bars = 2500
live_confirm = false

[strategies.hype_tb_mii_ensemble]
strategy_id = "HYPE-15M-TB-MII-ENS-V2"
global_position_limit = 1
priority_leg = "ema_tb_v39"
secondary_leg = "mii_v14"
preempt_secondary = true

[strategies.hype_tb_mii_ensemble.ema_tb_v39]
entry_delay_bars = 2
ema_fast = 96
ema_slow = 384
adx_window = 28
atr_window = 672
volume_window = 192
long_adx_min = 28.0
short_adx_min = 36.0
long_vol_min = 0.35
short_vol_min = 0.50
short_use_h1_ema = false
long_target_atr_pct = 0.020
short_target_atr_pct = 0.022
max_allocation = 3.0
take_profit_atr = 5.0
hard_stop_atr = 7.0
adx_exit = 22.0
delayed_bars = 3
disable_after_mfe_atr = 1.5
max_hold_bars = 384

[strategies.hype_tb_mii_ensemble.mii_v14]
entry_delay_bars = 1
rsi_window = 7
rsi_long_cross = 40.0
rsi_short_cross = 60.0
macd_fast = 12
macd_slow = 26
macd_signal = 9
min_atr_pct96 = 0.0075
max_atr_pct96 = 0.028
min_rvol96 = 0.85
exposure = 2.5
tp_atr_mult = 1.25
sl_atr_mult = 5.0
timeout_bars = 24
same_bar_priority = "stop_first"
```

若选择在现有 [`hype-trend`](file:///Users/ZK/OpenCode/hype-trend) repo 扩展，而不是在 `quant-runner` 新增 kind，也必须保留同等字段、状态机和 replay 验收；不能只通过 `.env.live` 覆盖 V35 参数。

## 验证门禁

### 1. 数据质量 gate

- 标准数据湖全窗口：gap / duplicate / invalid OHLC / critical null / raw-normalized mismatch 全 `0`。
- Recent Binance API：记录拉取时间、首尾时间、row count、是否丢弃未闭合 K、gap/duplicate/null/invalid OHLC。
- 任何数据 blocker 出现时，不得继续做信号或下单验证。

### 2. 母腿指标与信号 gate

V39 必须对拍：

- `ATR672`、`EMA96/384`、`ADX28/+DI/-DI`、`volume_surge192`、1h shifted features。
- long/short signal boolean 序列。
- K+2 入场、TP/SL、indicator exit、timeout、funding。

V1.4 必须对拍：

- `RSI7`、`MACD histogram`、`ATR96%`、`RVOL96`。
- raw RSI cross、过滤后 candidate、K+1 入场。
- bracket、timeout、stop-first、单仓链。

### 3. 组合 replay gate

用 [`research_hype_15m_tb_mii_ensemble_backtest.py`](../scripts/research_hype_15m_tb_mii_ensemble_backtest.py) 的 `--trend v39 --mii v14` 输出作为目标，对拍：

- 全样本 `single_v39_priority_k1` 交易数 `291`。
- V39 `107` 笔、V1.4 `184` 笔。
- `preempted_by_v39` 共 `3` 次。
- 全样本收益、回撤、胜率与研究报告一致，容差需在验证报告中声明。
- 最近 `6m`、`3m` 交易数、胜率、收益、回撤与 [`V2 近期审计 CSV`](../artifacts/hype_15m_tb_mii_ens_v2_recent_6m_3m_trade_audit_2026-07-09.csv) 一致。

### 4. live-executable gate

必须通过：

- 入场 market order 与 reduce-only TP/SL 保护单原子性审计。
- 保护单拒绝、部分成交、取消失败、连接中断、重启后的恢复审计。
- preempt 流程：取消 V1.4 保护单、只减仓平 V1.4、确认 flat、再开 V39。
- 交易所 precision、min notional、tick/step size、杠杆、保证金模式检查。
- 真实手续费、funding、成交滑点入账。
- missing-bar / stale candle fail-closed。
- kill switch 和告警链路。

### 5. shadow / dry-run gate

建议至少输出：

- 最近 2 至 4 周 shadow/dry-run 事件日志。
- 每根闭合 K 的信号评估记录。
- runner fill proxy 相对研究 K+1/K+2 open 的偏差。
- 每笔信号与研究 replay 的 entry/exit/reason 差异。
- V35 live 并行期间，确认 V2 shadow 未提交任何真实订单。

### 6. 小资金 live pilot gate

只有满足以下条件后才允许讨论：

- 用户明确批准真金 pilot。
- V35 live 已停止，或 V2 使用独立 subaccount。
- 单笔 notional、日亏损、连续错误、最大持仓时间、手动 kill switch 全部生效。
- 首次 pilot 不得用回测 `2.5x/3.0x` 对大本金直接满额；必须有额外 notional cap。

## 禁止项

- 禁止把本文解释为 live approval。
- 禁止在未完成 replay/dry-run 对拍前把 V2 标记为 `dry-run handoff`、`paper-live`、`candidate` 或 `live`。
- 禁止 V35 live service 与 V2 live service 同账户同 symbol 同时真单运行。
- 禁止 preempt 未确认平仓就开 V39。
- 禁止使用未闭合 K 生成信号或更新 stop/TP。
- 禁止在保护单失败时继续裸仓运行。
- 禁止把 V1.4A 或任何 TP/SL 变体混入 V2；V2 固定使用 V1.4 baseline。

## 证据链接

- 组合主账：[`../hype-15m-tb-mii-ens-core-ledger.md`](../hype-15m-tb-mii-ens-core-ledger.md)
- 组合 decision log：[`../decision-log.md`](../decision-log.md)
- V2 组合回测报告：[`../notes/hype-15m-tb-mii-ensemble-v39-v14-combination-backtest-2026-07-09.md`](../notes/hype-15m-tb-mii-ensemble-v39-v14-combination-backtest-2026-07-09.md)
- V2 周度与近期审计：[`../notes/hype-15m-tb-mii-ens-v2-weekly-trade-audit-2026-07-09.md`](../notes/hype-15m-tb-mii-ens-v2-weekly-trade-audit-2026-07-09.md)
- V2 live-executable 审计（失败）：[`../diagnostics/hype-15m-tb-mii-ens-v2-live-executable-audit-2026-07-09.md`](../diagnostics/hype-15m-tb-mii-ens-v2-live-executable-audit-2026-07-09.md)
- V2 live-executable 静态检查摘要：[`../artifacts/hype_15m_tb_mii_ens_v2_live_executable_static_audit_2026-07-09.md`](../artifacts/hype_15m_tb_mii_ens_v2_live_executable_static_audit_2026-07-09.md)
- V2 周度 CSV：[`../artifacts/hype_15m_tb_mii_ens_v2_single_v39_priority_k1_weekly_trades_1y_2026-07-09.csv`](../artifacts/hype_15m_tb_mii_ens_v2_single_v39_priority_k1_weekly_trades_1y_2026-07-09.csv)
- V2 6m/3m CSV：[`../artifacts/hype_15m_tb_mii_ens_v2_recent_6m_3m_trade_audit_2026-07-09.csv`](../artifacts/hype_15m_tb_mii_ens_v2_recent_6m_3m_trade_audit_2026-07-09.csv)
- 组合回测脚本：[`../scripts/research_hype_15m_tb_mii_ensemble_backtest.py`](../scripts/research_hype_15m_tb_mii_ensemble_backtest.py)
- V39 live spec：[`../../15m-ema-trend-breakout/live-specs/hype-ema-tb-v39-live-spec-not-live-ready-2026-07-09.md`](../../15m-ema-trend-breakout/live-specs/hype-ema-tb-v39-live-spec-not-live-ready-2026-07-09.md)
- V1.4 live validation spec：[`../../15m-multi-indicator-intraday/live-specs/hype-15m-mii-v1-4-live-validation-spec-not-live-ready-2026-07-09.md`](../../15m-multi-indicator-intraday/live-specs/hype-15m-mii-v1-4-live-validation-spec-not-live-ready-2026-07-09.md)

## 最终状态建议

本文完成的是 `V2 registered diagnostic -> live validation spec draft` 的规格导出，不代表通过 live-executable 审计。

建议状态仍为：

```text
HYPE-15M-TB-MII-ENS-V2: dry-run active / replay parity PASS / live disabled / not live-ready
```

只有 runner 实现、replay 对拍、shadow/dry-run、订单时序审计和 kill-switch 验证全部完成后，才允许讨论小资金 live pilot。
