# HYPE V3 强制反手确认修正

> 日期：2026-08-07。结论：`MA_ONLY`修复了MA7上方反手并提高主路径历史表现，但仍有3笔一日反手；用户随后将其登记为V4，登记不代表promotion。

## 修正

- `V3_CONTROL`：trailing平多后无条件反手short。
- `MA_ONLY`：拟反手的真实`1h` open必须低于上一完整UTC日MA7，否则保持flat。
- `MA_AND_SLOPE`：在`MA_ONLY`上再要求V3自然short的`2d`向下slope达到`0.02×ATR7`。

三者的自然多空参数、V3 short `0.75×ATR7`迟滞、保护、成本和执行时序完全相同。

## 主结果

Binance USD-M `HYPEUSDT` perpetual，accepted `1h`聚合UTC日K，`2025-05-31`至`2026-07-30`，约`1x`，手续费`0.001/fill`、不利滑点`4 bps/fill`、真实event-time funding。

| 变体 | 净收益 | MDD | Sharpe | PF | 交易 | 反手/拒绝 | 一日反手 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| V3 control | +350.85% | -26.81% | 2.436 | 8.836 | 19 | 7 / 0 | 5 |
| `MA_ONLY` | **+411.23%** | -26.81% | **2.669** | 13.516 | 17 | 5 / 2 | 3 |
| `MA_AND_SLOPE` | +335.18% | **-26.44%** | 2.476 | **13.681** | 13 | 1 / 6 | **0** |

`MA_ONLY`拒绝的正是MA7上方开空且亏损的R-S02与R-S12，因此全期相对V3提高`60.38`个百分点。该改善具有明确机制理由，但也完全来自已经看到的两笔亏损，不能当作clean OOS。

## 逐笔影响

`MA_ONLY`保留5笔反手：

- 2025-07-17：`-0.99%`，1日，slope exit；
- 2025-09-20：`+17.59%`，11日；
- 2026-03-22：`-0.50%`，1日，slope exit；
- 2026-06-04：`+1.42%`，1日，slope exit；
- 2026-07-11：`+18.86%`，19日。

所有反手成交均在当时可知MA7下方，价格位置缺陷已修复；但3/5仍只持有1日，说明“MA7下方”只能解决错误方向，不能完全解决入场与slope exit冲突。

`MA_AND_SLOPE`只保留2026-07-11一笔`+18.86%`反手，完全消除一日反手；代价是过滤掉2025-09-20的`+17.59%`盈利交易，主路径低于V3。

## 稳健性

| 检查 | V3 | `MA_ONLY` | `MA_AND_SLOPE` |
| --- | ---: | ---: | ---: |
| `8 bps` | +344.23% | **+404.59%** | +330.85% |
| 额外延迟一天 | +104.25% | +109.85% | **+143.60%** |
| `12h`日界 | +35.33% | +35.33% | **+74.47%** |
| 最后90日flat-start | +75.21% | +75.21% | +72.77% |
| 最新延伸至2026-08-06 | +339.92% | **+398.84%** | +324.63% |

- 12个90日滚动窗口：三者均12/12为正；`MA_ONLY`中位`+37.02%`、最差`+15.02%`，优于V3的`+36.80% / +4.22%`。
- 23个有效日界相位：V3为22正、中位`+47.75%`；`MA_ONLY`为21正、中位`+38.35%`；`MA_AND_SLOPE`为21正、中位`+26.47%`。相位不是硬门禁，但两个修正版都没有在全相位上普遍优于V3。

## 已知漏空：2025-06-17至06-19

首笔long于6月13日trailing退出，拟反手价`38.734`高于当时可知MA7 `38.096`，因此`MA_ONLY`正确拒绝并转flat。V4不保留“等以后跌到MA7下再开空”的pending状态。

6月17日首次形成自然short reclaim：收盘`39.968 < MA7-0.1×ATR7`，前收`41.918 >= 前MA7 41.446`；但`2d`向下slope为`-0.0277`，未达到`+0.02`，所以不开空。6月18–19日slope已转为`+0.1597 / +0.2028`并通过，但前一日收盘早已在MA7下方，不再满足reclaim事件，仍不会开空。

因此图中6月19日不开空不是cooldown，也不是价格仍在MA7上，而是V4只修正强制反手确认，没有增加“cross后等待slope确认再延迟入场”的armed/pending状态。

## 决定

1. `MA_ONLY`是本轮更符合用户最低要求的修正：反手成交必须在MA7下方，主路径、压力、延迟与滚动未恶化；用户于2026-08-07将其登记为V4。
2. 它尚未完整解决快速退出或cross后延迟确认；若继续研究，下一问题应隔离“反手short是否沿用slope exit”或“是否增加pending确认”，不能在已揭示历史上同时搜索多个新阈值。
3. `MA_AND_SLOPE`作为一致性控制保留，但过度压缩反手覆盖，不作为首选。
4. V3继续保留；V4状态为`registered / not promoted / not live-ready`。

## 证据

- [冻结合同](../specs/hype-1d-ma7-abt-v3-forced-reversal-confirmation-contract-2026-08-07.md)
- [机器摘要](../artifacts/hype_1d_v3_reversal_confirmation_2026-08-07_summary.json)
- [指标与压力](../artifacts/hype_1d_v3_reversal_confirmation_2026-08-07_metrics.csv)
- [近期切片](../artifacts/hype_1d_v3_reversal_confirmation_2026-08-07_recent.csv)
- [90日滚动](../artifacts/hype_1d_v3_reversal_confirmation_2026-08-07_rolling_90d.csv)
- [24相位](../artifacts/hype_1d_v3_reversal_confirmation_2026-08-07_phase24.csv)
- [`MA_ONLY`交易](../artifacts/hype_1d_v3_reversal_confirmation_2026-08-07_ma_only_trades.csv)
- [`MA_ONLY`完整交易路径HTML](../artifacts/hype_1d_ma7_abt_v3_ma_only_reversal_trade_path_2026-08-07.html)
- [审计脚本](../scripts/audit_hype_1d_ma7_abt_v3_forced_reversal_confirmation.py)
- [绘图脚本](../scripts/render_hype_1d_ma7_abt_v3_ma_only_reversal_trade_path.py)
- [V4规格](../specs/hype-1d-ma7-abt-v4-spec.md)
