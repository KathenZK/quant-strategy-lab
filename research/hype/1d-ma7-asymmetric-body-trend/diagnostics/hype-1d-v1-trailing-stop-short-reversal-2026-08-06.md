# HYPE V1 多头追踪止损后反手空诊断

> 状态：`explore / diagnostic-only / not promoted / not live-ready`。这是已揭示历史上的规则变更诊断，不改写 V1。

## 结论

按[冻结合同](../specs/hype-1d-ma7-abt-trailing-stop-short-reversal-contract-2026-08-06.md)，V1 多头 trailing stop 后在下一根真实 `1h` open 反手做空，空单完整沿用 V1 原退出规则。该变体在 `0h UTC` 历史主路径符合预注册的“改善”定义：

- 成本后全期从 `+293.20%` 提高到 `+322.59%`，增加 `29.39pp`；
- `8 bps/fill` 压力从 `+289.25%` 提高到 `+316.37%`，增加 `27.12pp`；
- MDD 仅由 `-26.44%` 小幅变为 `-26.81%`；
- 新增 7 笔反手空，3 胜 4 负，合计净 PnL `+0.7194` 个初始权益单位。

但这不是可直接登记的新版本。改善几乎全部来自已被研究者看到的最近两次反手，早期样本无优势；额外延迟和 `12h` 相位下，变体均弱于原 V1。合理结论是：**该机制值得冻结后独立前瞻观察，但现有证据不足以替换 V1。**

## 执行口径

- 多头原 trailing stop 先成交并平仓，平多与开空分别计费；
- 小时 open 跳空触发时可在该 open 反手；小时内触发时在下一根 `1h` open 反手，避免猜测同一小时内路径先后；
- 反手当日剩余小时立即启用 short `1.5×ATR7` hard stop，并结算真实 event-time funding；
- 后续退出完整沿用 V1：`MA7 + 0.25×ATR7` 迟滞、MA7 转升、`4×ATR7` trailing、20 日上限与 5 日 cooldown；
- 手续费 `0.001/fill`，基准不利滑点 `4 bps/fill`，压力 `8 bps/fill`。

## 主要结果

| 窗口 / 检查 | V1 基准 | 反手变体 | 差值 |
| --- | ---: | ---: | ---: |
| 全期净收益 | `+293.20%` | `+322.59%` | `+29.39pp` |
| 全期 MDD | `-26.44%` | `-26.81%` | `-0.37pp` |
| 全期 Sharpe | `2.352` | `2.346` | `-0.006` |
| `8 bps` 净收益 | `+289.25%` | `+316.37%` | `+27.12pp` |
| prefit 净收益 | `+143.70%` | `+141.19%` | `-2.51pp` |
| 后 90 日 flat-start | `+61.35%` | `+75.21%` | `+13.87pp` |
| 额外延迟一天 | `+140.58%` | `+135.36%` | `-5.21pp` |
| `12h` 相位净收益 | `+28.97%` | `+14.50%` | `-14.46pp` |

全期交易从 13 笔增至 19 笔，short 从 5 笔增至 11 笔；turnover 从 `50.90x` 增至 `73.23x`，成本从初始权益的 `7.13%` 增至 `10.25%`。胜率从 `76.9%` 降至 `63.2%`，profit factor 从 `12.41` 降至 `8.53`，说明改善不是普遍提高每笔质量，而是少数新增空单的收益集中。

## 新增空单归因

- 7 笔新增反手空中，5 笔在下一日 open 即被原 V1 MA7 退出规则关闭；
- prefit 的 5 笔新增空合计净 PnL 约 `-0.0012`，基本没有历史优势；
- 后 90 日的 2 笔新增空均盈利；其中 `2026-07-11` 至 `2026-07-30` 的一笔在全路径贡献 `+0.6705`，约占全部新增空净 PnL 的 `93%`；
- 所有新增空都未触发 short hard/trailing stop，主要由 MA7 迟滞/斜率退出或 terminal flatten 结束。

因此，“改善”高度依赖用户已经观察到的 2026 年 7 月下跌，属于 post-reveal 机制发现。`12h` 相位仍为正，但相对基准少 `14.46pp`；相位按治理规则只作为检查项，不过这里清楚提示增量优势不稳定。

## BTC/ETH 共享参数适用性

BTC/ETH 共享参数的多头配置为 `hard_stop_atr=0`、`trail_atr=0`、`max_hold_days=0`，没有 protective/trailing stop 触发。本轮不为它事后新增另一套多头 trailing，因此该路线是“不适用”，不是通过或失败。

## 决策

1. 不把该规则静默并入 V1，也不凭本次历史结果登记 V2；
2. 保留为一个明确的候选机制，若继续则与 V1 并行做独立 prospective shadow observation；
3. 前瞻期间冻结反手触发和 V1 short exit，不因单笔结果调整参数；在积累足够新增反手事件前不讨论 promotion。

## 证据

- [机器摘要](../artifacts/hype_1d_v1_trailing_stop_short_reversal_2026-08-06_summary.json)
- [指标与压力](../artifacts/hype_1d_v1_trailing_stop_short_reversal_2026-08-06_metrics.csv)
- [逐笔交易](../artifacts/hype_1d_v1_trailing_stop_short_reversal_2026-08-06_trades.csv)
- [近期切片](../artifacts/hype_1d_v1_trailing_stop_short_reversal_2026-08-06_recent.csv)
- [相位检查](../artifacts/hype_1d_v1_trailing_stop_short_reversal_2026-08-06_phase.csv)
- [审计脚本](../scripts/audit_hype_v1_trailing_stop_short_reversal.py)
