# HYPE V4 局部修复逐步诊断

> 日期：2026-08-07。结论：全局状态机继续失败后，保留V4主体、只增加“short reclaim有限等待 + anti-chase + 原V4 opposite reclaim handoff”的局部候选同时保留2025-06 short与后续long，全期`+426.21%`；但MDD、PF、延迟和相位中位弱于V4，只建议冻结后观察，不登记V5。

## 固定口径

- Binance USD-M `HYPEUSDT` perpetual；accepted真实`1h`聚合UTC日K；
- 历史主路径`2025-05-31`至`2026-07-30 UTC`；
- 约`1x`固定数量、单仓、手续费`0.001/fill`、不利滑点`4 bps/fill`、真实funding；
- V4自然reclaim、全部退出、`MA_ONLY` trailing反手、long 2日/short 5日cooldown均保留；
- 最近切片仅作审计；所有结果均为post-reveal，不是clean OOS。

合同：[第一轮有限pending](../specs/hype-1d-ma7-abt-v4-finite-reclaim-pending-contract-2026-08-07.md) · [第二轮质量与handoff](../specs/hype-1d-ma7-abt-v4-pending-quality-handoff-contract-2026-08-07.md)。

## 第一步：short有限等待

| 变体 | 净收益 | MDD | 交易 | 延迟确认 | 相位正数 |
|---|---:|---:|---:|---:|---:|
| `V4_CONTROL` | `+411.23%` | `-26.81%` | 17 | 0 | `21/23` |
| `SHORT_PENDING_1D` | `+110.73%` | `-30.27%` | 21 | 5 | `16/23` |
| `SHORT_PENDING_2D` | `+70.27%` | `-34.63%` | 23 | 11 | `14/23` |

`1d`确实把6月17日fresh reclaim保留至6月18日slope确认，于6月19日open建立short并赚`+7.23%`。但它还接受4个延迟short，其中过度偏离MA7的交易反复止损或占用仓位；6月short退出当天又因V4同open禁入错过原6月28日long。`2d`进一步增加低质量交易，不采纳。

## 第二步：long有限等待

| 变体 | 净收益 | MDD | 交易 | 延迟确认 |
|---|---:|---:|---:|---:|
| `LONG_PENDING_1D` | `+216.12%` | `-36.47%` | 22 | 5 |
| `LONG_PENDING_2D` | `+164.91%` | `-36.47%` | 24 | 6 |

新增long多数是保护退出或迟滞退出，且会占用原short路径；long侧没有显示出需要复制short pending修复的证据。多空组合的主收益只剩`+26.68%`至`+58.85%`，全部未通过冻结门槛。

## 第三步：short anti-chase

延迟short确认除保留原`0.25×ATR7`下限外，再要求距离MA7不超过`0.75×ATR7`。该上限拒绝：

- 2025-08-19：`1.142×ATR7`；
- 2026-04-20：`1.056×ATR7`；
- 2026-05-12：`1.196×ATR7`。

这些正是第一轮中产生明显亏损和仓位冲突的追空。`SP1_CAP_075`恢复到`+331.94%`、MDD`-29.25%`、19笔、23相位21正，但仍因6月short退出后未重开V4 long而低于控制。

## 第四步：仅对delayed仓位handoff

handoff只适用于由延迟pending建立的仓位，并且退出当日相反方向的**原V4 fresh reclaim + slope + buffer**也必须通过；protective stop、普通V4仓位和持续regime均不能使用。

2025-06路径：

1. 6月17日fresh short reclaim，2日slope尚未确认；
2. 6月18日slope确认，距离MA7仅`0.316×ATR7`；
3. 6月19日open建立short；
4. 6月28日按原short slope exit平仓，short赚`+7.23%`；
5. 6月27日收盘原V4 long reclaim也通过，因此6月28日同open交接long；
6. long完整保留原V4路径，至7月17日保护退出，赚`+21.88%`。

这不是持续状态反手，而是两个独立V4级别事件在同一open的交接。

## 最佳局部候选

`SP1_CAP_075_HANDOFF`相对V4只新增3笔short：

- 2025-06-19：`+7.23%`；
- 2025-11-13：`-0.70%`；
- 2026-04-30：`-3.33%`。

除6月short外，V4原17笔路径全部保留；6月28日long通过1次handoff恢复。

| 检查 | V4 | 局部候选 |
|---|---:|---:|
| 主路径净收益 | `+411.23%` | `+426.21%` |
| MDD | `-26.81%` | `-29.25%` |
| Sharpe | `2.669` | `2.664` |
| PF | `13.516` | `10.221` |
| `8 bps` | `+404.59%` | `+418.14%` |
| 额外延迟1日 | `+109.85%` | `+101.07%` |
| `12h`日界 | `+35.33%` | `+28.21%` |
| 90日滚动正窗口 | `12/12` | `12/12` |
| 滚动中位 | `+37.02%` | `+34.70%` |
| 滚动最差 | `+15.02%` | `+20.42%` |
| 有效相位正收益 | `21/23` | `21/23` |
| 相位中位 | `+38.35%` | `+28.51%` |
| 相位最差 | `-14.97%` | `-23.08%` |

最近`1d/7d/1m`逐点与V4相同；`3m/6m/1y`为`+68.63%/+66.07%/+319.97%`，低于V4的`+75.21%/+71.80%/+337.52%`。最新延伸为`+413.46%`，高于V4同口径`+398.84%`。

## 裁决

1. 这轮达到了图中局部行为目标：补上6月short，没有丢掉6月28日long，并过滤3次明显追空；
2. 没有恢复“所有MA7侧别都交易”，也没有改写V4的普通入场/退出；
3. 候选通过预先冻结的MDD、延迟、`12h`、相位中位与相位正数底线；
4. 但历史净收益仅高`14.98pp`，同时MDD扩大`2.44pp`、PF下降、延迟与相位中位变差；它不是无条件优于V4；
5. anti-chase与handoff均在已揭示交易后提出，存在明显过拟合风险；不登记V5；
6. 若继续，下一步应冻结该候选并与V4并行prospective观察，不能再根据这425日微调`0.75`上限。

## 证据

- [第一轮审计脚本](../scripts/audit_hype_1d_ma7_abt_v4_finite_reclaim_pending.py)
- [第二轮审计脚本](../scripts/audit_hype_1d_ma7_abt_v4_pending_quality_handoff.py)
- [最佳候选交易路径HTML](../artifacts/hype_1d_ma7_abt_v4_pending_quality_handoff_trade_path_2026-08-07.html)
- [第一轮机器摘要](../artifacts/hype_1d_v4_finite_reclaim_pending_2026-08-07_summary.json)
- [第二轮机器摘要](../artifacts/hype_1d_v4_pending_quality_handoff_2026-08-07_summary.json)
- [第二轮分期/压力/延迟](../artifacts/hype_1d_v4_pending_quality_handoff_2026-08-07_metrics.csv)
- [第二轮近期切片](../artifacts/hype_1d_v4_pending_quality_handoff_2026-08-07_recent.csv)
- [第二轮90日滚动](../artifacts/hype_1d_v4_pending_quality_handoff_2026-08-07_rolling_90d.csv)
- [第二轮24相位](../artifacts/hype_1d_v4_pending_quality_handoff_2026-08-07_phase24.csv)
- [第二轮最新延伸](../artifacts/hype_1d_v4_pending_quality_handoff_2026-08-07_latest.csv)
