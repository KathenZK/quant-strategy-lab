# HYPE-15M-TB-MII-ENS V2 Live-Executable 审计 2026-07-09

Family：`HYPE-15M-Trend-Breakout-Multi-Indicator-Ensemble`（alias：`HYPE-15M-TB-MII-ENS`）

Version：`V2`

审计结论：`FAILED / NO-GO / not dry-run / not live-ready`

## 先读结论

`HYPE-15M-TB-MII-ENS-V2` 目前**没有通过 live-executable 验证**。研究侧组合回测和 Python 复现门禁已经通过，但执行侧缺口是硬 blocker：当前本地 runner 没有 V2 组合 kind、没有 `HYPE-EMA-TB-V39` trend-breakout runner、`quant-runner` 里的 `hype_mii` 仍是 `HYPE-15M-MII-V1.3 / min_rvol96=1.0`，也没有组合层全局单仓、V39 优先、V1.4 强平让位、preempt 原子换仓、V2 重启恢复与 kill switch 实现。

因此当前状态维持：

```text
HYPE-15M-TB-MII-ENS-V2:
live validation spec draft / live-executable FAILED / NO-GO / not promoted / not dry-run / not live-ready
```

本文不是上线批准；它是一次负向 live-executable 审计。下一步必须先实现 runner replay，并对拍标准数据湖的 `291` 笔、V39 `107` 笔、V1.4 `184` 笔、`preempted_by_v39=3`，再讨论 shadow/dry-run。

## 审计范围

本次审计覆盖：

- V2 live validation spec：[`hype-15m-tb-mii-ens-v2-live-validation-spec-not-live-ready-2026-07-09.md`](../live-specs/hype-15m-tb-mii-ens-v2-live-validation-spec-not-live-ready-2026-07-09.md)。
- V2 组合回测报告：[`hype-15m-tb-mii-ensemble-v39-v14-combination-backtest-2026-07-09.md`](../notes/hype-15m-tb-mii-ensemble-v39-v14-combination-backtest-2026-07-09.md)。
- V2 周度/近期审计：[`hype-15m-tb-mii-ens-v2-weekly-trade-audit-2026-07-09.md`](../notes/hype-15m-tb-mii-ens-v2-weekly-trade-audit-2026-07-09.md)。
- Python 组合状态机：[`research_hype_15m_tb_mii_ensemble_backtest.py`](../scripts/research_hype_15m_tb_mii_ensemble_backtest.py)。
- 本地 `quant-runner` 静态实现检查：[`/Users/ZK/OpenCode/quant-runner`](file:///Users/ZK/OpenCode/quant-runner)。
- 本地 V35 runner 静态实现检查：[`/Users/ZK/OpenCode/hype-trend`](file:///Users/ZK/OpenCode/hype-trend)。

保留的静态检查摘要：[`hype_15m_tb_mii_ens_v2_live_executable_static_audit_2026-07-09.md`](../artifacts/hype_15m_tb_mii_ens_v2_live_executable_static_audit_2026-07-09.md)。

本次**没有**连接交易所、没有读取或输出任何密钥、没有操作阿里云服务、没有启动/停止任何 live service。

## 结果总览

| 门禁 | 结果 | 说明 |
| --- | --- | --- |
| 数据质量 gate | `PASS` | 标准数据湖 missing bar / duplicate / invalid OHLC / critical null / raw-normalized mismatch 全 `0`。 |
| Python 研究 replay gate | `PASS` | V39 canonical 零差；V1.4 链路逐笔一致；V2 主口径 `291` 笔、preempt `3` 次。 |
| 母腿 live spec 完整性 | `PARTIAL` | V39 与 V1.4 都有 live validation spec，但均未形成可直接运行的 V2 runner。 |
| `quant-runner` V2 strategy kind | `FAIL` | 未发现 `hype_tb_mii_ensemble` / `HypeTbMii`。 |
| `quant-runner` V39 trend-breakout kind | `FAIL` | 未发现 `hype_ema_tb` / `HypeEmaTb`；现有的是 `hype_ema_x`，不是 trend-breakout。 |
| `quant-runner` MII V1.4 | `FAIL` | 现有 `hype_mii` 默认 `strategy_id=HYPE-15M-MII-V1.3`、`min_rvol96=1.0`；V2 需要 V1.4 的 `0.85`。 |
| 全局单仓 / 组合仲裁 | `FAIL` | 未发现组合层 `global_position_limit=1` 或 V39/V1.4 共享状态机。 |
| V1.4 preempt 原子强平让位 | `FAIL` | 研究脚本有 open 价强平假设，runner 没有“取消保护单 -> reduce-only 平仓 -> 确认 flat -> 开 V39”的实现证据。 |
| 保护单与订单时序 | `PARTIAL / FAIL for V2` | `quant-runner` 单策略 bracket 路径有保护单能力，但 V2 组合层未实现，不能视作通过。 |
| 重启恢复 | `FAIL` | 未发现 V2 `active_leg / preempt_in_progress / exchange_order_ids` 状态恢复实现。 |
| funding / 成本统一 | `FAIL` | V39 腿研究计 funding；MII 腿研究未计 funding，V2 live 侧还没有统一记账验证。 |
| kill switch / notional cap | `FAIL` | 未发现 V2 专属日亏损、单笔 notional、连续错误、手动全平等风控实现。 |

静态检查计数：`PASS=3`、`PARTIAL=1`、`FAIL=12`。

## 已通过部分

### 1. 研究数据与 Python 组合门禁

V2 回测报告记录：

- 标准数据湖 `38,765` 根已闭合 `15m` K，至 `2026-07-08T05:30Z`。
- missing bar / duplicate / invalid OHLC / critical null / raw-normalized mismatch 全 `0`。
- V39 腿与 canonical 引擎逐 K 权益曲线最大差 `0.00e+00`。
- V1.4 engine 与 MII 主账一致；组合单仓选择链与 MII canonical `selected_trades_live` 逐笔一致。

这些说明：**研究侧回放没有明显未来函数或链路拼接错误**。

### 2. 组合层研究状态机清晰

Python 组合脚本中 `run_account()` 已明确顺序：

1. V39 pending exit 按 open 出场。
2. V1.4 open 型 exit 按 open 出场。
3. V39 持仓计 funding。
4. V39 K+2 入场；若 V1.4 持仓且 `preempt=true`，先按 open 价记录 `preempted_by_v39`，再开 V39。
5. V39 intrabar TP/SL 或 close mark。
6. 全局空仓时才允许 V1.4 K+1 入场。
7. V1.4 bracket / timeout 出场或 close mark。

这可以作为 runner replay 的目标规格，但它不是 live 可执行证明。

## 失败 blocker

### Blocker 1：没有 V2 runner kind

`quant-runner` 的 `StrategyKindName` 只有：

```text
HypePullback
HypeMii
HypeCandleCount
HypeEmaX
```

未发现：

```text
HypeTbMii
hype_tb_mii_ensemble
```

因此 `V2` 当前无法作为独立 strategy instance 被配置、启动、replay 或 dry-run。

### Blocker 2：没有 V39 trend-breakout runner

`V2` 的趋势腿是 `HYPE-EMA-Trend-Breakout-V39`，不是 `HYPE-EMA-X`。当前 `quant-runner` 未发现 `hype_ema_tb` / `HypeEmaTb`。现有本地 [`hype-trend`](file:///Users/ZK/OpenCode/hype-trend) 是 V35 单腿 runner，代码和文档均指向 `V35Engine`，不是 V39，也不是组合。

这意味着 V2 不能用现有 runner 直接复现 V39 腿，更不能做 V39 优先仲裁。

### Blocker 3：MII runner 仍是 V1.3，不是 V1.4

`quant-runner` 的 `hype_mii` 默认配置仍是：

```text
strategy_id = "HYPE-15M-MII-V1.3"
min_rvol96 = 1.0
```

V2 要求：

```text
HYPE-15M-MII-V1.4
min_rvol96 = 0.85
```

即使只跑 MII 腿，当前 runner 默认也不是 V2 所需的 V1.4。

### Blocker 4：preempt 在研究中可写，live 中未实现

研究脚本中的 preempt 是理想化动作：

```text
V1.4 持仓
V39 entry due
按当前 open 记录 V1.4 preempt exit
立即开 V39
```

live 必须变成可验证的交易所流程：

```text
pause signals
cancel V1.4 reduce-only TP/SL
submit reduce-only market close
confirm exchange position flat
record preempted_by_v39
submit V39 entry
arm V39 TP/SL
```

当前没有 V2 runner，也就没有这个原子流程、失败处理或重启恢复。未确认 flat 就开 V39 是硬禁止项。

### Blocker 5：组合状态恢复不存在

V2 至少需要保存和恢复：

```text
active_leg
entry_signal_ts
entry_ts
direction
quantity
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

现有 `quant-runner` 的通用单策略状态不能证明覆盖 V2 的 `active_leg` 与 `preempt_in_progress`。没有这层恢复，断电/重启/网络异常后无法安全判断是继续 V1.4、继续 V39、完成 preempt，还是 fail-closed。

### Blocker 6：保护单能力不是组合能力

`quant-runner` 单策略 bracket 路径已有一些有价值的通用能力：

- 入场后 arm TP/SL。
- 保护单失败时尝试 emergency market reduce。
- 可查询保护单成交。
- local flat 但 exchange 有 open orders 时会报错。

但这只证明平台有部分单策略 bracket 执行基础，不证明 V2 通过。V2 还需要：

- V39 与 V1.4 共享一个全局仓位状态。
- preempt 时先撤 V1.4 保护单再只减仓。
- V39 入场后重新按 V39 entry ATR arm 新保护单。
- 失败时不允许开第二条腿。

这些没有实现证据。

### Blocker 7：MII funding 未统一

研究口径中：

- V39 腿计入 Binance funding。
- V1.4 / MII 腿未计 funding。

V2 live 必须使用真实 funding 与手续费入账。未完成前，不能把研究净收益当作可执行收益，也不能用回测收益直接推 live 风险。

### Blocker 8：缺少 V2 风控与 kill switch

V2 单账户全时段可能使用 `2.5x-3.0x` 名义暴露。live pilot 前至少需要：

- 单笔 notional cap。
- 日亏损停止新开仓。
- 连续错误停止策略。
- 手动暂停新开仓。
- 手动全平。
- missing-bar / stale candle fail-closed。
- DingTalk 或等价告警覆盖 preempt、保护单失败、unexpected position、重启恢复。

当前没有 V2 专属实现证据。

## 结论与状态

本次 live-executable 验证结果：

```text
FAILED
```

允许继续做：

- runner 设计。
- V2 strategy kind 实现。
- 标准数据湖 replay 对拍。
- shadow / dry-run 设计。

不允许做：

- 直接真金 live。
- 直接替换 V35 live。
- 与 V35 live 同账户同 symbol 并行真单。
- 把 V2 标记为 `dry-run handoff`、`candidate`、`paper-live` 或 `live`。

## 进入 dry-run 前的最低修复清单

1. 在 runner 中新增 `hype_tb_mii_ensemble` 或等价 V2 strategy kind。
2. 实现 V39 trend-breakout 腿，或把 `hype-trend` V35 单腿 runner 扩展到 V39 并通过 V39 replay 对拍。
3. 实现 / 参数化 MII V1.4：`strategy_id=HYPE-15M-MII-V1.4`、`min_rvol96=0.85`。
4. 实现组合全局单仓状态机：同一账户同时最多一笔仓位。
5. 实现 V39 优先和 V1.4 preempt 原子换仓。
6. 实现 V2 state schema 和重启恢复。
7. 实现 V2 kill switch、notional cap、日亏损限制和告警。
8. 标准数据湖 replay 对拍：`291` 笔、V39 `107`、V1.4 `184`、`preempted_by_v39=3`、权益曲线误差在验收容差内。
9. Recent closed candles shadow/dry-run 至少覆盖多个 V39 与 V1.4 信号，输出 fill-vs-open 偏差和订单事件差异报告。

## 证据链接

- V2 live validation spec：[`hype-15m-tb-mii-ens-v2-live-validation-spec-not-live-ready-2026-07-09.md`](../live-specs/hype-15m-tb-mii-ens-v2-live-validation-spec-not-live-ready-2026-07-09.md)
- V2 组合回测报告：[`hype-15m-tb-mii-ensemble-v39-v14-combination-backtest-2026-07-09.md`](../notes/hype-15m-tb-mii-ensemble-v39-v14-combination-backtest-2026-07-09.md)
- V2 周度审计：[`hype-15m-tb-mii-ens-v2-weekly-trade-audit-2026-07-09.md`](../notes/hype-15m-tb-mii-ens-v2-weekly-trade-audit-2026-07-09.md)
- 静态检查摘要：[`hype_15m_tb_mii_ens_v2_live_executable_static_audit_2026-07-09.md`](../artifacts/hype_15m_tb_mii_ens_v2_live_executable_static_audit_2026-07-09.md)
- V39 live spec：[`../../15m-ema-trend-breakout/live-specs/hype-ema-tb-v39-live-spec-not-live-ready-2026-07-09.md`](../../15m-ema-trend-breakout/live-specs/hype-ema-tb-v39-live-spec-not-live-ready-2026-07-09.md)
- V1.4 live validation spec：[`../../15m-multi-indicator-intraday/live-specs/hype-15m-mii-v1-4-live-validation-spec-not-live-ready-2026-07-09.md`](../../15m-multi-indicator-intraday/live-specs/hype-15m-mii-v1-4-live-validation-spec-not-live-ready-2026-07-09.md)
